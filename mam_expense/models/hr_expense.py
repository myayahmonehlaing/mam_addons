# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError,ValidationError
from odoo import api, Command,fields, models, _


class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    expense_sheet_approval = fields.Boolean(string='Expense Report Approval',
                                             related='company_id.expense_sheet_approval')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'To Approve'),
        ('approve', 'Approved'),
        ('post', 'Posted'),
        ('done', 'Paid'),
        ('cancel', 'Refused')
    ], string='Status', index=True, readonly=True, tracking=True, copy=False, default='draft', required=True,
        help='Expense Report State')
    approver_ids = fields.One2many('hr.expense.approver', 'sheet_id', string="Approvers",compute='_compute_approver_ids', store=True,)
    user_status = fields.Selection([
        ('new', 'New'),
        ('submit', 'To Approve'),
        ('waiting', 'Waiting'),
        ('approve', 'Approved'),
        ('post', 'Posted'),
        ('done', 'Paid'),
        ('cancel', 'Refused')], compute="_compute_user_status")

    @api.depends('user_id')
    def _compute_approver_ids(self):
        for order in self:
            approver_id_vals = []
            if order.company_id.expense_sheet_approval:
                for approver in order.company_id.expense_approver_ids:
                    if approver.user_id.id not in order.approver_ids.user_id.ids:
                        approver_id_vals.append(Command.create({
                            'user_id': approver.user_id.id,
                            'status': 'new',
                        }))
            order.update({'approver_ids': approver_id_vals})

    @api.depends('approver_ids.status')
    def _compute_user_status(self):
        for sheet in self:
            sheet.user_status = sheet.approver_ids.filtered(lambda approver: approver.user_id == self.env.user).status


    def action_approval_submit(self):
        approvers = self.approver_ids
        if not approvers:
            raise UserError(_("You have to add at least one approver to submit expense request."))

        approvers = approvers.filtered(lambda a: a.status in ['new', 'submit', 'waiting'])

        approvers[1:].sudo().write({'status': 'waiting'})
        self.write({'state': 'submit'})
        approvers = approvers[0] if approvers and approvers[0].status != 'submit' else self.env[
            'hr.expense.approver']
        approvers._create_activity()
        approvers.sudo().write({'status': 'submit'})

    def _get_user_approval_activities(self, user):
        domain = [
            ('res_model', '=', 'hr.expense.sheet'),
            ('res_id', 'in', self.ids),
            ('activity_type_id', '=', self.env.ref('mam_expense.mail_activity_data_expense_approval').id),
            ('user_id', '=', user.id)
        ]
        activities = self.env['mail.activity'].search(domain)
        return activities


    def approve_approval_expense_sheets(self,approver=None):
        if not isinstance(approver, models.BaseModel):
            approver = self.mapped('approver_ids').filtered(
                lambda approver: approver.user_id == self.env.user
            )
        approver.write({'status': 'approve'})
        self.sudo()._update_next_approvers('submit', approver, only_next_approver=True)
        self.sudo()._get_user_approval_activities(user=self.env.user).action_feedback()

        status_lst = self.mapped('approver_ids.status')
        approvers = len(status_lst)
        result = {}
        if status_lst.count('approve') == approvers:
            responsible_id = self.user_id.id or self.env.user.id
            self.write({'state': 'approve', 'user_id': responsible_id})
        return result

    def _update_next_approvers(self, new_status, approver, only_next_approver, cancel_activities=False):
        approvers_updated = self.env['hr.expense.approver']

        current_approver = self.approver_ids & approver
        approvers_to_update = self.approver_ids.filtered(lambda a: a.status not in ['approve', 'refused'] and (a.id > current_approver.id))

        if only_next_approver and approvers_to_update:
            approvers_to_update = approvers_to_update[0]
        approvers_updated |= approvers_to_update

        approvers_updated.sudo().status = new_status
        if new_status == 'submit':
            approvers_updated._create_activity()
        if cancel_activities:
            approvers_updated.request_id._cancel_activities()

    def _do_refuse(self, reason,approver= None):

        if not isinstance(approver, models.BaseModel):
            approver = self.mapped('approver_ids').filtered(
                lambda approver: approver.user_id == self.env.user
            )
        if approver:
            approver.write({'status': 'cancel'})
            self.sudo()._get_user_approval_activities(user=self.env.user).action_feedback()
            self.write({'state': 'cancel'})
            subtype_id = self.env['ir.model.data']._xmlid_to_res_id('mail.mt_comment')
            for sheet in self:
                sheet.message_post_with_source(
                    'hr_expense.hr_expense_template_refuse_reason',
                    subtype_id=subtype_id,
                    render_values={'reason': reason, 'name': sheet.name},
                )
        self.activity_update()



    def action_reset_approval_expense_sheets(self):
        res = super().action_reset_approval_expense_sheets()
        self.approver_ids.write({'status': 'new'})
        self.activity_unlink(['mam_expense.mail_activity_data_expense_approval'])
        return res


class HrExpenseApprover(models.Model):
    _name = 'hr.expense.approver'
    _description = 'Expense Approver'

    company_id = fields.Many2one(
        string='Company', related='sheet_id.company_id',
        store=True, readonly=True, index=True)
    existing_sheet_user_ids = fields.Many2many('res.users', compute='_compute_existing_sheet_user_ids')
    user_id = fields.Many2one('res.users', string="User", required=True, check_company=True,
                              domain="[('id', 'not in', existing_sheet_user_ids)]")

    name = fields.Char(related='user_id.name')
    status = fields.Selection([
        ('new', 'New'),
        ('submit', 'To Approve'),
        ('waiting', 'Waiting'),
        ('approve', 'Approved'),
        ('post', 'Posted'),
        ('done', 'Paid'),
        ('cancel', 'Refused')
    ], string="Status", default="new", readonly=True)
    sheet_id = fields.Many2one('hr.expense.sheet', string="Expense Sheet", ondelete='cascade')


    @api.depends('sheet_id.user_id', 'sheet_id.approver_ids.user_id')
    def _compute_existing_sheet_user_ids(self):
        for approver in self:
            approver.existing_sheet_user_ids = self.mapped('sheet_id.approver_ids.user_id')._origin | self.sheet_id.user_id._origin


    def button_approve(self):
        self.sheet_id.button_approve(self)

    def action_refuse(self):
        self.sheet_id.action_refuse(self)

    def action_create_activity(self):
        self.write({'status': 'submit'})
        self._create_activity()

    def _create_activity(self):
        for approver in self:
            approver.sheet_id.activity_schedule(
                'mam_expense.mail_activity_data_expense_approval',
                user_id=approver.user_id.id)


