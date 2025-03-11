# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

class HrExpenseCompanyApprover(models.Model):
    """ Intermediate model between approval.category and res.users
        To know whether an approver for this category is required or not
    """
    _name = 'hr.expense.company.approver'
    _description = 'HR Expense Company Approver'
    _rec_name = 'user_id'
    _order = 'id'

    user_id = fields.Many2one('res.users', string='User', ondelete='cascade', required=True)
    company_id = fields.Many2one('res.company')
