# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

class BillCompanyApprover(models.Model):
    """ Intermediate model between approval.category and res.users
        To know whether an approver for this category is required or not
    """
    _name = 'bill.company.approver'
    _description = 'Bill Company Approver'
    _rec_name = 'user_id'
    _order = 'id'

    user_id = fields.Many2one('res.users', string='User', ondelete='cascade', required=True)
    company_id = fields.Many2one('res.company',default=lambda self: self.env.company)


class AdvanceCompanyApprover(models.Model):
    """ Intermediate model between approval.category and res.users
        To know whether an approver for this category is required or not
    """
    _name = 'advance.company.approver'
    _description = 'Advance Company Approver'
    _rec_name = 'user_id'
    _order = 'id'

    user_id = fields.Many2one('res.users', string='User', ondelete='cascade', required=True)
    company_id = fields.Many2one('res.company',default=lambda self: self.env.company)



class JournalCompanyApprover(models.Model):
    """ Intermediate model between approval.category and res.users
        To know whether an approver for this category is required or not
    """
    _name = 'journal.entry.company.approver'
    _description = 'Journal Entry Company Approver'
    _rec_name = 'user_id'
    _order = 'id'

    user_id = fields.Many2one('res.users', string='User', ondelete='cascade', required=True)
    company_id = fields.Many2one('res.company',default=lambda self: self.env.company)