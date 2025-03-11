# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError,ValidationError
from odoo import api, Command,fields, models, _


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    purchase_order_approval = fields.Boolean(string='Purchase Order Approval',related ='company_id.purchase_order_approval')
    approver_ids = fields.One2many('purchase.order.approver', 'order_id', string="Approvers", check_company=True,
                                   compute='_compute_approver_ids', store=True, )
    state = fields.Selection(selection_add=[('refused', 'Refused'), ('cancel',)])
    user_status = fields.Selection([
        ('new', 'New'),
        ('to approve', 'To Approve'),
        ('waiting', 'Waiting'),
        ('approve', 'Approved'),
        ('done', 'Locked'),
        ('refused', 'Refused'),
        ('cancel', 'Cancel')], compute="_compute_user_status")


    @api.depends('user_id')
    def _compute_approver_ids(self):
        for order in self:
            approver_id_vals = []
            if order.company_id.purchase_order_approval:
                for approver in order.company_id.purchase_approver_ids:
                    if approver.user_id.id not in order.approver_ids.user_id.ids:
                        approver_id_vals.append(Command.create({
                            'user_id': approver.user_id.id,
                            'status': 'new',
                        }))
            order.update({'approver_ids': approver_id_vals})

    @api.depends('approver_ids.status')
    def _compute_user_status(self):
        user = self.env.user
        for order in self:
            order.user_status = order.approver_ids.filtered(lambda r: r.user_id == user).status

    def _get_user_approval_activities(self, user):
        domain = [
            ('res_model', '=', 'purchase.order'),
            ('res_id', 'in', self.ids),
            ('activity_type_id', '=', self.env.ref('mam_purchase.mail_activity_data_approval').id),
            ('user_id', '=', user.id)
        ]
        activities = self.env['mail.activity'].search(domain)
        return activities



    def action_approve(self,approver=None):
        for order in self:
            if not isinstance(approver, models.BaseModel):
                approver = self.mapped('approver_ids').filtered(
                    lambda approver: approver.user_id == self.env.user
                )
            approver.write({'status': 'approve'})
            order.sudo()._update_next_approvers('to approve', approver, only_next_approver=True)
            order.sudo()._get_user_approval_activities(user=self.env.user).action_feedback()

            status_lst = order.mapped('approver_ids.status')
            approvers = len(status_lst)

            if status_lst.count('approve') == approvers:
                subject = order.name + ' has been approved'
                order.message_post_with_source('mam_purchase.purchase_template_approve',
                                              render_values={'name': order.name}, subject=subject)

                order.order_line._validate_analytic_distribution()
                order._add_supplier_to_product()
                # Deal with double validation process
                order.button_approve()
                try:
                    if order.requisition_id.type_id.exclusive == 'exclusive':
                        others_po = order.requisition_id.mapped('purchase_ids').filtered(lambda r: r.id != order.id)
                        others_po.button_cancel()
                        if order.state not in ['draft', 'sent', 'to approve']:
                            order.requisition_id.action_done()
                except:
                    pass
        if order.partner_id not in order.message_partner_ids:
           order.message_subscribe([order.partner_id.id])
        return True


    def _update_next_approvers(self, new_status, approver, only_next_approver, cancel_activities=False):
        approvers_updated = self.env['purchase.order.approver']

        current_approver = self.approver_ids & approver
        approvers_to_update = self.approver_ids.filtered(lambda a: a.status not in ['approve', 'refused'] and (a.id > current_approver.id))

        if only_next_approver and approvers_to_update:
            approvers_to_update = approvers_to_update[0]
        approvers_updated |= approvers_to_update

        approvers_updated.sudo().status = new_status
        if new_status == 'to approve':
            approvers_updated._create_activity()
        if cancel_activities:
            approvers_updated.request_id._cancel_activities()


    def request_approval(self,approver):
        approver._create_activity()
        approver.write({'status': 'to approve'})


    def action_submit(self):
        approvers = self.approver_ids
        if not approvers:
            raise UserError(_("You have to add at least one approver to submit your purchase request."))

        approvers = approvers.filtered(lambda a: a.status in ['new', 'to approve', 'waiting'])

        approvers[1:].sudo().write({'status': 'waiting'})
        self.write({'state': 'to approve'})
        approvers = approvers[0] if approvers and approvers[0].status != 'to approve' else self.env['purchase.order.approver']
        approvers._create_activity()
        approvers.sudo().write({'status': 'to approve'})


    def refuse_order(self,reason,force=False,approver=None,):
        if not isinstance(approver, models.BaseModel):
            approver = self.mapped('approver_ids').filtered(
                lambda approver: approver.user_id == self.env.user
            )
            draft_approver = self.mapped('approver_ids').filtered(
                lambda approver: approver.status in ('new', 'sent')
            )
            if draft_approver:
                draft_approver.write({'status': 'cancel'})

        if approver:
            approver.write({'status': 'refused'})
            self.sudo()._get_user_approval_activities(user=self.env.user).action_feedback()
            subject = self.name + ' has been refused'
            self.message_post_with_source('mam_purchase.purchase_template_refuse_reason',
                                   render_values={'reason': reason,'name': self.name}, subject=subject)
        self.write({'state': 'refused'})

    def button_draft(self):
        super(PurchaseOrder, self).button_draft()
        self.approver_ids.write({'status': 'new'})
        self.activity_unlink(['mam_purchase.mail_activity_data_approval'])
        return {}

    def button_cancel(self):
        super(PurchaseOrder, self).button_cancel()
        if self.approver_ids:
            self.approver_ids.write({'status': 'cancel'})
            self.activity_unlink(['mam_purchase.mail_activity_data_approval'])



class PurchaseApprover(models.Model):
    _name = 'purchase.order.approver'
    _description = 'Purchase Order Approver'
    _order = 'order_id,id'

    company_id = fields.Many2one(
        string='Company', related='order_id.company_id',
        store=True, readonly=True, index=True)
    user_id = fields.Many2one('res.users', string="User", check_company=True,required=True,
                              domain="[('id', 'not in', existing_order_user_ids)]")

    existing_order_user_ids = fields.Many2many('res.users', compute='_compute_existing_order_user_ids')


    name = fields.Char(related='user_id.name')
    status = fields.Selection([
        ('new', 'New'),
        ('to approve', 'To Approve'),
        ('waiting', 'Waiting'),
        ('approve', 'Approved'),
        ('done', 'Locked'),
        ('refused', 'Refused'),
        ('cancel', 'Cancel')
       ], string="Status", default="new", readonly=True)
    order_id = fields.Many2one('purchase.order', string="Purchase Order", ondelete='cascade')


    @api.depends('order_id.user_id', 'order_id.approver_ids.user_id')
    def _compute_existing_order_user_ids(self):
        for approver in self:
            approver.existing_order_user_ids = self.mapped('order_id.approver_ids.user_id')._origin

    def button_approve(self):
        self.order_id.button_approve(self)

    def action_create_activity(self):
        self.write({'status': 'to approve'})
        self._create_activity()

    def _create_activity(self):
        for approver in self:
            approver.order_id.activity_schedule(
                'mam_purchase.mail_activity_data_approval',
                user_id=approver.user_id.id)


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    allowed_product_ids = fields.Many2many("product.product", compute='_compute_allowed_product_ids', )


    @api.depends('order_id.picking_type_id','order_id.picking_type_id.warehouse_id'
        ,'order_id.picking_type_id.warehouse_id.region_id')
    def _compute_allowed_product_ids(self):
        for record in self:
            record.allowed_product_ids = self.env["product.product"].search(
                [('region_id', '=', record.order_id.picking_type_id.warehouse_id.region_id.id)])

    @api.constrains('product_id')
    def _check_product_id(self):
        for record in self:
            if not record.product_id in record.allowed_product_ids:
                raise ValidationError(_("Error ! You cannot save a purchase order with unallowed product."))


    @api.depends('invoice_lines.move_id.state', 'invoice_lines.quantity', 'qty_received', 'product_uom_qty',
                 'order_id.state')
    def _compute_qty_invoiced(self):
        for line in self:
            # compute qty_invoiced
            qty = 0.0
            for inv_line in line._get_invoice_lines():
                if inv_line.move_id.state not in ['cancel','refused'] or inv_line.move_id.payment_state == 'invoicing_legacy':
                    if inv_line.move_id.move_type == 'in_invoice':
                        qty += inv_line.product_uom_id._compute_quantity(inv_line.quantity, line.product_uom)
                    elif inv_line.move_id.move_type == 'in_refund':
                        qty -= inv_line.product_uom_id._compute_quantity(inv_line.quantity, line.product_uom)
            line.qty_invoiced = qty

            # compute qty_to_invoice
            if line.order_id.state in ['purchase', 'done']:
                if line.product_id.purchase_method == 'purchase':
                    line.qty_to_invoice = line.product_qty - line.qty_invoiced
                else:
                    line.qty_to_invoice = line.qty_received - line.qty_invoiced
            else:
                line.qty_to_invoice = 0
