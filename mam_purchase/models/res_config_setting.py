# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

class Company(models.Model):
    _inherit = 'res.company'

    purchase_order_approval = fields.Boolean(string='Purchase Order Approval (Customized)')
    purchase_approver_ids = fields.One2many('purchase.order.company.approver','company_id',string="Purchase Approvers")



class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    purchase_order_approval = fields.Boolean(related='company_id.purchase_order_approval',
                                            string='Purchase Order Approval (Customized)', readonly=False)
    purchase_approver_ids = fields.One2many('purchase.order.company.approver',related='company_id.purchase_approver_ids',readonly= False)

