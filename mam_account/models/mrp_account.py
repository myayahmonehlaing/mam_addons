# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json

from odoo import models, api, fields


class MrpBom(models.Model):
    _inherit = 'mrp.bom'


    @api.constrains('analytic_distribution')
    def _check_analytic(self):
        for record in self:
            record.with_context({'validate_analytic': False})._validate_distribution(**{
                'product': record.product_id.id,
                'company_id': record.company_id.id,
            })