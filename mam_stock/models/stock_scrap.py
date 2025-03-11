# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import SUPERUSER_ID, Command,_, api, fields, models
from odoo.exceptions import UserError, ValidationError


class StockScrap(models.Model):
    _inherit = "stock.scrap"

    allowed_product_ids = fields.Many2many("product.product", compute='_compute_allowed_product_ids')

    @api.depends('location_id', 'location_id.warehouse_id','location_id.warehouse_id.region_id')
    def _compute_allowed_product_ids(self):
        for record in self:
            record.allowed_product_ids = self.env["product.product"].search(
                [('region_id', '=', record.location_id.warehouse_id.region_id.id)])


    @api.constrains('product_id')
    def _check_product_id(self):
        for record in self:
            if not record.product_id in record.allowed_product_ids:
                raise ValidationError(_("Error ! You cannot save a scrap with unallowed product."))
