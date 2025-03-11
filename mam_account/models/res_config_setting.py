# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

class Company(models.Model):
    _inherit = 'res.company'

    bill_approval = fields.Boolean(string='Vendor Bill Approval')
    advance_approval = fields.Boolean(string='Employee Advance Approval')


    bill_approver_ids = fields.One2many('bill.company.approver','company_id',string="Bill Approvers")
    advance_approver_ids = fields.One2many('advance.company.approver', 'company_id', string="Employee Advance Approvers")



class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bill_approval = fields.Boolean(related='company_id.bill_approval',
                                            string='Vendor Bill Approval', readonly=False)
    advance_approval = fields.Boolean(related='company_id.advance_approval',
                                            string='Employee Advance Approval', readonly=False)

    bill_approver_ids = fields.One2many('bill.company.approver',related='company_id.bill_approver_ids',readonly= False)
    advance_approver_ids = fields.One2many('advance.company.approver', related='company_id.advance_approver_ids', readonly=False)



