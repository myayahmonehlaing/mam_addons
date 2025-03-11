# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class ResPartner(models.Model):
    _inherit = "res.partner"


    company_id = fields.Many2one(
        'res.company', 'Company', index=True,default=lambda self: self.env.company)
