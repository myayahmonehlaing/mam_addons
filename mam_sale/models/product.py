# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = "product.template"

    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse', store=True)
    company_id = fields.Many2one(
        'res.company', 'Company', index=True,default=lambda self: self.env.company)

    region_id = fields.Many2one('mam.region', string='Region')

class Product(models.Model):
    _inherit = "product.product"

    tmpl_warehouse_id = fields.Many2one('stock.warehouse', related='product_tmpl_id.warehouse_id', store=True)
    region_id = fields.Many2one('mam.region', string='Region', related='product_tmpl_id.region_id', store=True)
