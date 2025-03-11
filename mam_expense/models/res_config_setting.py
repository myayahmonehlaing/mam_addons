# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

class Company(models.Model):
    _inherit = 'res.company'

    expense_sheet_approval = fields.Boolean(string='Expense Report Approval')
    expense_approver_ids = fields.One2many('hr.expense.company.approver','company_id',string="Expense Approvers")



class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    expense_sheet_approval = fields.Boolean(related='company_id.expense_sheet_approval',
                                            string='Expense Report Approval', readonly=False)
    expense_approver_ids = fields.One2many('hr.expense.company.approver',related='company_id.expense_approver_ids',readonly= False)

