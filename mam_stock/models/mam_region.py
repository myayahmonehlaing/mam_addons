# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class MamRegion(models.Model):
    _name = "mam.region"

    name = fields.Char("Name")
    company_id = fields.Many2one("res.company" , index=True,default=lambda self: self.env.company)