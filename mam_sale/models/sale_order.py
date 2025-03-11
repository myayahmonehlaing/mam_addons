# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import fields, models,api,_
from odoo.exceptions import AccessDenied, UserError, ValidationError

class SaleOrder(models.Model):
    _inherit = "sale.order"

    region_id = fields.Many2one('mam.region', string='Region')

    def _compute_warehouse_id(self):
        return

    # @api.onchange('warehouse_id')
    # def _onchange_warehouse_id(self):
    #         self.region_id = self.warehouse_id.region_id.id


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    margin = fields.Float(
        "Margin", compute='_compute_margin',
        digits='Product Price', store=True, groups="mam_sale.group_sale_margin ", precompute=True)
    margin_percent = fields.Float(
        "Margin (%)", compute='_compute_margin', store=True, groups="mam_sale.group_sale_margin ", precompute=True)

    allowed_product_temp_ids = fields.Many2many("product.template", compute='_compute_allowed_product_temp_ids', )

    product_template_id = fields.Many2one(
        string="Product Template",
        comodel_name='product.template',
        compute=None,
        readonly=False,
        search=None,
        # previously related='product_id.product_tmpl_id'
        # not anymore since the field must be considered editable for product configurator logic
        # without modifying the related product_id when updated.
        domain=[('sale_ok', '=', True)])

    @api.depends('order_id.warehouse_id','order_id.warehouse_id.region_id')
    def _compute_allowed_product_temp_ids(self):
        for record in self:
            record.allowed_product_temp_ids = self.env["product.template"].search([('region_id', '=', record.warehouse_id.region_id.id)])


    @api.constrains('product_template_id')
    def _check_product_template_id(self):
        for record in self:
            if not record.product_template_id in record.allowed_product_temp_ids:
                raise ValidationError(_("Error ! You cannot save a  sale order with unallowed product."))

