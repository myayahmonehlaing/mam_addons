# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api,Command, fields, models, _

class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    advance_id = fields.Many2one("account.move","Advance")
