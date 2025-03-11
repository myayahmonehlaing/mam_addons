# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

class PurchaseOrderCompanyApprover(models.Model):
    """ Intermediate model between approval.category and res.users
        To know whether an approver for this category is required or not
    """
    _name = 'purchase.order.company.approver'
    _description = 'Purchase Order Approver'
    _rec_name = 'user_id'
    _order = 'id'

    user_id = fields.Many2one('res.users', string='User', ondelete='cascade', required=True)
    company_id = fields.Many2one('res.company' ,default=lambda self: self.env.company)
