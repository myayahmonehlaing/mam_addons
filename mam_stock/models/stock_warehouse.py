
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, tools, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    region_id = fields.Many2one('mam.region', string='Region')