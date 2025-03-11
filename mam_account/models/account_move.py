# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict
from odoo import api,Command, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError, RedirectWarning
from odoo.tools import (
    date_utils,
    email_re,
    email_split,
    float_compare,
    float_is_zero,
    float_repr,
    format_amount,
    format_date,
    formatLang,
    frozendict,
    get_lang,
    index_exists,
    is_html_empty,
)
from odoo.addons.account.models.account_move import AccountMove as AM



class AccountMove(models.Model):
    _inherit = "account.move"

    is_employee_advance = fields.Boolean("Is Advance",change_default=True,)
    bill_approval = fields.Boolean(related='company_id.bill_approval',
                                   string='Vendor Bill Approval', )
    advance_approval = fields.Boolean(related='company_id.advance_approval',
                                      string='Employee Advance Approval', )

    hr_expense_sheet_count = fields.Integer("Expense Sheet Count" , compute='_compute_hr_expense_sheet_count',)
    approver_ids = fields.One2many('account.move.approver', 'move_id', string="Approvers",
                                   compute='_compute_approver_ids', store=True, )
    user_status = fields.Selection([
        ('new', 'New'),
        ('to approve', 'To Approve'),
        ('waiting', 'Waiting'),
        ('approve', 'Approved'),
        ('refused', 'Refused'),
        ('cancel', 'Cancelled')], compute="_compute_user_status")

    state = fields.Selection(selection_add=[('to approve', 'To Approve'), ('approve', 'Approved'), ('posted',),
                                            ('refused', 'Refused'), ('cancel',)],
                             ondelete={'to approve': 'set default', 'approve': 'set default', 'refused': 'set default'})

    related_advance_id = fields.Many2one('account.move',string="Related Advance",domain=[('move_type', '=', 'in_invoice'),('is_employee_advance', '=', True)])

    @api.depends('user_id')
    def _compute_approver_ids(self):
        for move in self:
            approver_id_vals = []
            if move.move_type == "in_invoice" and move.is_employee_advance:
                for approver in move.company_id.advance_approver_ids:
                    if approver.user_id.id not in move.approver_ids.user_id.ids:
                        approver_id_vals.append(Command.create({
                            'user_id': approver.user_id.id,
                            'status': 'new',

                        }))
            elif move.move_type == "in_invoice" and not move.is_employee_advance:
                for approver in move.company_id.bill_approver_ids:
                    if approver.user_id.id not in move.approver_ids.user_id.ids:
                        approver_id_vals.append(Command.create({
                            'user_id': approver.user_id.id,
                            'status': 'new',

                        }))
            move.update({'approver_ids': approver_id_vals})

    @api.depends('approver_ids.status')
    def _compute_user_status(self):
        user = self.env.user
        for move in self:
            approvers = move.approver_ids.filtered(lambda r: r.user_id == user)
            if len(approvers) == 1:
                move.user_status = approvers.status
            else:
                move.user_status = "new"

    def action_submit(self):
        approvers = self.approver_ids
        if not approvers:
            raise UserError(_("You have to add at least one approver to submit your bill request."))

        approvers = approvers.filtered(lambda a: a.status in ['new', 'to approve', 'waiting'])

        approvers[1:].sudo().write({'status': 'waiting'})
        self.write({'state': 'to approve'})
        approvers = approvers[0] if approvers and approvers[0].status != 'to approve' else self.env[
            'account.move.approver']
        approvers._create_activity()
        approvers.sudo().write({'status': 'to approve'})

    def _get_user_approval_activities(self, user):
        if self.move_type == 'in_invoice' and not self.is_employee_advance:
            activity = 'mam_account.mail_activity_data_bill_approval'
        elif self.move_type == 'in_invoice' and self.is_employee_advance:
            activity = 'mam_account.mail_activity_data_advance_approval'
        else:
            activity = 'mam_account.mail_activity_data_journal_entry_approval'
        domain = [
            ('res_model', '=', 'account.move'),
            ('res_id', 'in', self.ids),
            ('activity_type_id', '=', self.env.ref(activity).id),
            ('user_id', '=', user.id)
        ]
        activities = self.env['mail.activity'].search(domain)
        return activities

    def get_approver(self):
        approver = self.mapped('approver_ids').filtered(lambda approver: approver.status == 'draft')
        if len(approver) > 1:
            return approver[0]
        else:
            return approver

    def button_approve(self, approver=None):
        if not isinstance(approver, models.BaseModel):
            approver = self.mapped('approver_ids').filtered(
                lambda approver: approver.user_id == self.env.user
            )
        approver.write({'status': 'approve'})
        self.sudo()._update_next_approvers('to approve', approver, only_next_approver=True)
        self.sudo()._get_user_approval_activities(user=self.env.user).action_feedback()

        status_lst = self.mapped('approver_ids.status')
        approvers = len(status_lst)
        result = {}
        if status_lst.count('approve') == approvers:
            type = 'bill'
            ref = _("( Ref - %s )") % self.ref if self.ref else ''
            name = self.name if not self.name == '/' else type.capitalize() + ' ' + ref
            subject = name + ' has been approved'
            self.message_post_with_source('mam_account.account_move_template_approve',
                                          render_values={'ref': self.ref, 'name': self.name, 'type': self.move_type},
                                          subject=subject)
            self.action_post()
        return result

    def _update_next_approvers(self, new_status, approver, only_next_approver, cancel_activities=False):
        approvers_updated = self.env['account.move.approver']

        current_approver = self.approver_ids & approver
        approvers_to_update = self.approver_ids.filtered(
            lambda a: a.status not in ['approve', 'refused'] and (a.id > current_approver.id))

        if only_next_approver and approvers_to_update:
            approvers_to_update = approvers_to_update[0]
        approvers_updated |= approvers_to_update

        approvers_updated.sudo().status = new_status
        if new_status == 'to approve':
            approvers_updated._create_activity()
        if cancel_activities:
            approvers_updated.request_id._cancel_activities()

    def _cancel_activities(self):
        approval_activity = self.env.ref('approvals.mail_activity_data_approval')
        activities = self.activity_ids.filtered(lambda a: a.activity_type_id == approval_activity)
        activities.unlink()

    def request_approval(self, approver):
        approver._create_activity()
        approver.write({'status': 'to approve'})

    def refuse_move(self, reason, force=False, approver=None, ):
        if not isinstance(approver, models.BaseModel):
            approver = self.mapped('approver_ids').filtered(
                lambda approver: approver.user_id == self.env.user
            )
            draft_approver = self.mapped('approver_ids').filtered(
                lambda approver: approver.status == 'draft'
            )
            if draft_approver:
                draft_approver.write({'status': 'cancel'})

        if approver:
            approver.write({'status': 'refused'})
            self.sudo()._get_user_approval_activities(user=self.env.user).action_feedback()
            type = 'bill'
            ref = _("( Ref - %s )") % self.ref if self.ref else ''
            name = self.name if not self.name == '/' else type.capitalize() + ' ' + ref
            subject = name + ' has been refused'

            self.message_post_with_source('mam_account.account_move_template_refuse_reason',
                                          render_values={'reason': reason, 'name': self.name, 'ref': self.ref,
                                                         'type': self.move_type}, subject=subject)

        self.write({'state': 'refused'})

    def button_draft(self):
        super(AccountMove, self).button_draft()
        self.approver_ids.write({'status': 'new'})
        if self.move_type == 'in_invoice' and not self.is_employee_advance:
            activity = 'mam_account.mail_activity_data_bill_approval'
        elif self.move_type == 'in_invoice' and self.is_employee_advance:
            activity = 'mam_account.mail_activity_data_advance_approval'
        else:
            activity = 'mam_account.mail_activity_data_journal_entry_approval'
        self.activity_unlink([activity])

    @api.constrains('approver_ids')
    def _check_approver_ids(self):
        for move in self:
            # make sure the approver_ids are unique per order
            if len(move.approver_ids) != len(move.approver_ids.user_id):
                raise UserError(_("You cannot assign the same approver multiple times on the same bill."))


    def _compute_hr_expense_sheet_count(self):
        for record in self:
            record.hr_expense_sheet_count = self.env['hr.expense.sheet'].search_count(
            [('advance_id', '=', record.id)])

    def _account_move_post(self, soft=True):
        """Post/Validate the documents.

        Posting the documents will give it a number, and check that the document is
        complete (some fields might not be required if not posted but are required
        otherwise).
        If the journal is locked with a hash table, it will be impossible to change
        some fields afterwards.

        :param soft (bool): if True, future documents are not immediately posted,
            but are set to be auto posted automatically at the set accounting date.
            Nothing will be performed on those documents before the accounting date.
        :return Model<account.move>: the documents that have been posted
        """

        # if not self.env.su and not self.env.user.has_group('account.group_account_invoice'):
        #     raise AccessError(_("You don't have the access rights to post an invoice."))
        for invoice in self.filtered(lambda move: move.is_invoice(include_receipts=True)):
            if (
                    invoice.quick_edit_mode
                    and invoice.quick_edit_total_amount
                    and invoice.currency_id.compare_amounts(invoice.quick_edit_total_amount, invoice.amount_total) != 0
            ):
                raise UserError(_(
                    "The current total is %s but the expected total is %s. In order to post the invoice/bill, "
                    "you can adjust its lines or the expected Total (tax inc.).",
                    formatLang(self.env, invoice.amount_total, currency_obj=invoice.currency_id),
                    formatLang(self.env, invoice.quick_edit_total_amount, currency_obj=invoice.currency_id),
                ))
            if invoice.partner_bank_id and not invoice.partner_bank_id.active:
                raise UserError(_(
                    "The recipient bank account linked to this invoice is archived.\n"
                    "So you cannot confirm the invoice."
                ))
            if float_compare(invoice.amount_total, 0.0, precision_rounding=invoice.currency_id.rounding) < 0:
                raise UserError(_(
                    "You cannot validate an invoice with a negative total amount. "
                    "You should create a credit note instead. "
                    "Use the action menu to transform it into a credit note or refund."
                ))

            if not invoice.partner_id:
                if invoice.is_sale_document():
                    raise UserError(
                        _("The field 'Customer' is required, please complete it to validate the Customer Invoice."))
                elif invoice.is_purchase_document():
                    raise UserError(
                        _("The field 'Vendor' is required, please complete it to validate the Vendor Bill."))

            # Handle case when the invoice_date is not set. In that case, the invoice_date is set at today and then,
            # lines are recomputed accordingly.
            if not invoice.invoice_date:
                if invoice.is_sale_document(include_receipts=True):
                    invoice.invoice_date = fields.Date.context_today(self)
                elif invoice.is_purchase_document(include_receipts=True):
                    raise UserError(_("The Bill/Refund date is required to validate this document."))

        for move in self:
            if move.state in ['posted', 'cancel']:
                raise UserError(_('The entry %s (id %s) must be in draft.', move.name, move.id))
            if not move.line_ids.filtered(lambda line: line.display_type not in ('line_section', 'line_note')):
                raise UserError(_('You need to add a line before posting.'))
            if not soft and move.auto_post != 'no' and move.date > fields.Date.context_today(self):
                date_msg = move.date.strftime(get_lang(self.env).date_format)
                raise UserError(_("This move is configured to be auto-posted on %s", date_msg))
            if not move.journal_id.active:
                raise UserError(_(
                    "You cannot post an entry in an archived journal (%(journal)s)",
                    journal=move.journal_id.display_name,
                ))
            if move.display_inactive_currency_warning:
                raise UserError(_(
                    "You cannot validate a document with an inactive currency: %s",
                    move.currency_id.name
                ))

            if move.line_ids.account_id.filtered(lambda account: account.deprecated) and not self._context.get(
                    'skip_account_deprecation_check'):
                raise UserError(_("A line of this move is using a deprecated account, you cannot post it."))

        if soft:
            future_moves = self.filtered(lambda move: move.date > fields.Date.context_today(self))
            for move in future_moves:
                if move.auto_post == 'no':
                    move.auto_post = 'at_date'
                msg = _('This move will be posted at the accounting date: %(date)s',
                        date=format_date(self.env, move.date))
                move.message_post(body=msg)
            to_post = self - future_moves
        else:
            to_post = self

        for move in to_post:
            affects_tax_report = move._affect_tax_report()
            lock_dates = move._get_violated_lock_dates(move.date, affects_tax_report)
            if lock_dates:
                move.date = move._get_accounting_date(move.invoice_date or move.date, affects_tax_report)

        # Create the analytic lines in batch is faster as it leads to less cache invalidation.
        to_post.line_ids._create_analytic_lines()

        # Trigger copying for recurring invoices
        to_post.filtered(lambda m: m.auto_post not in ('no', 'at_date'))._copy_recurring_entries()

        for invoice in to_post:
            # Fix inconsistencies that may occure if the OCR has been editing the invoice at the same time of a user. We force the
            # partner on the lines to be the same as the one on the move, because that's the only one the user can see/edit.
            wrong_lines = invoice.is_invoice() and invoice.line_ids.filtered(lambda aml:
                                                                             aml.partner_id != invoice.commercial_partner_id
                                                                             and aml.display_type not in (
                                                                             'line_note', 'line_section')
                                                                             )
            if wrong_lines:
                wrong_lines.write({'partner_id': invoice.commercial_partner_id.id})

        # reconcile if state is in draft and move has reversal_entry_id set
        draft_reverse_moves = to_post.filtered(
            lambda move: move.reversed_entry_id and move.reversed_entry_id.state == 'posted')

        to_post.write({
            'state': 'posted',
            'posted_before': True,
        })

        draft_reverse_moves.reversed_entry_id._reconcile_reversed_moves(draft_reverse_moves,
                                                                        self._context.get('move_reverse_cancel', False))
        to_post.line_ids._reconcile_marked()

        for invoice in to_post:
            invoice.message_subscribe([
                p.id
                for p in [invoice.partner_id]
                if p not in invoice.sudo().message_partner_ids
            ])

            if (
                    invoice.is_sale_document()
                    and invoice.journal_id.sale_activity_type_id
                    and (invoice.journal_id.sale_activity_user_id or invoice.invoice_user_id).id not in (
            self.env.ref('base.user_root').id, False)
            ):
                invoice.activity_schedule(
                    date_deadline=min((date for date in invoice.line_ids.mapped('date_maturity') if date),
                                      default=invoice.date),
                    activity_type_id=invoice.journal_id.sale_activity_type_id.id,
                    summary=invoice.journal_id.sale_activity_note,
                    user_id=invoice.journal_id.sale_activity_user_id.id or invoice.invoice_user_id.id,
                )

        customer_count, supplier_count = defaultdict(int), defaultdict(int)
        for invoice in to_post:
            if invoice.is_sale_document():
                customer_count[invoice.partner_id] += 1
            elif invoice.is_purchase_document():
                supplier_count[invoice.partner_id] += 1
            elif invoice.move_type == 'entry':
                sale_amls = invoice.line_ids.filtered(
                    lambda line: line.partner_id and line.account_id.account_type == 'asset_receivable')
                for partner in sale_amls.mapped('partner_id'):
                    customer_count[partner] += 1
                purchase_amls = invoice.line_ids.filtered(
                    lambda line: line.partner_id and line.account_id.account_type == 'liability_payable')
                for partner in purchase_amls.mapped('partner_id'):
                    supplier_count[partner] += 1
        for partner, count in customer_count.items():
            (partner | partner.commercial_partner_id)._increase_rank('customer_rank', count)
        for partner, count in supplier_count.items():
            (partner | partner.commercial_partner_id)._increase_rank('supplier_rank', count)

        # Trigger action for paid invoices if amount is zero
        to_post.filtered(
            lambda m: m.is_invoice(include_receipts=True) and m.currency_id.is_zero(m.amount_total)
        )._invoice_paid_hook()

        return to_post

AM._post = AccountMove._account_move_post


class AccountMoveApprover(models.Model):
    _name = 'account.move.approver'
    _description = 'Account Move Approver'
    _order = 'move_id,id'

    user_id = fields.Many2one('res.users', string="User", required=True, check_company=True,
                              domain="[('id', 'not in', existing_move_user_ids)]")
    existing_move_user_ids = fields.Many2many('res.users', compute='_compute_move_order_user_ids')
    name = fields.Char(related='user_id.name')
    status = fields.Selection([
        ('new', 'New'),
        ('to approve', 'To Approve'),
        ('waiting', 'Waiting'),
        ('approve', 'Approved'),
        ('refused', 'Refused'),
        ('cancel', 'Cancel'),
       ], string="Status", default="new", readonly=True)
    move_id = fields.Many2one('account.move', string="Bill", ondelete='cascade', check_company=True)

    company_id = fields.Many2one(
        string='Company', related='move_id.company_id',
        store=True, readonly=True, index=True)

    @api.depends('move_id.user_id', 'move_id.approver_ids.user_id')
    def _compute_move_order_user_ids(self):
        for approver in self:
            approver.existing_move_user_ids = self.mapped('move_id.approver_ids.user_id')._origin | self.move_id.user_id._origin


    def button_approve(self):
        self.move_id.button_approve(self)

    def action_create_activity(self):
        self.write({'status': 'to approve'})
        self._create_activity()

    def _create_activity(self):
        for approver in self:
            if approver.move_id.move_type == 'in_invoice' and not approver.move_id.is_employee_advance:
                activity = 'mam_account.mail_activity_data_bill_approval'
            elif approver.move_id.move_type == 'in_invoice' and approver.move_id.is_employee_advance:
                activity = 'mam_account.mail_activity_data_advance_approval'        
            approver.move_id.activity_schedule(
                  activity,user_id=approver.user_id.id,summary=approver.move_id.ref)

    @api.ondelete(at_uninstall=False)
    def _unlink_to_approve(self):
        for approver in self:
            if approver.status in ['to approve', 'waiting','approve']:
                raise UserError(_('You cannot delete waiting or approved user.'))

