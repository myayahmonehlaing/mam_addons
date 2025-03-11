# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import defaultdict
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_is_zero

class StockLandedCost(models.Model):
    _inherit = 'stock.landed.cost'


    def button_validate(self):
        self._check_can_validate()
        cost_without_adjusment_lines = self.filtered(lambda c: not c.valuation_adjustment_lines)
        if cost_without_adjusment_lines:
            cost_without_adjusment_lines.compute_landed_cost()
        if not self._check_sum():
            raise UserError(_('Cost and adjustments lines do not match. You should maybe recompute the landed costs.'))

        for cost in self:
            cost = cost.with_company(cost.company_id)
            move = self.env['account.move']
            move_vals = {
                'journal_id': cost.account_journal_id.id,
                'date': cost.date,
                'ref': cost.name,
                'line_ids': [],
                'move_type': 'entry',
            }
            valuation_layer_ids = []
            cost_to_add_byproduct = defaultdict(lambda: 0.0)
            for line in cost.valuation_adjustment_lines.filtered(lambda line: line.move_id):
                remaining_qty = sum(line.move_id.stock_valuation_layer_ids.mapped('remaining_qty'))
                linked_layer = line.move_id.stock_valuation_layer_ids[:1]

                # Prorate the value at what's still in stock
                cost_to_add = (remaining_qty / line.move_id.quantity) * line.additional_landed_cost
                if not cost.company_id.currency_id.is_zero(cost_to_add):
                    valuation_layer = self.env['stock.valuation.layer'].create({
                        'value': cost_to_add,
                        'unit_cost': 0,
                        'quantity': 0,
                        'remaining_qty': 0,
                        'stock_valuation_layer_id': linked_layer.id,
                        'description': cost.name,
                        'stock_move_id': line.move_id.id,
                        'product_id': line.move_id.product_id.id,
                        'stock_landed_cost_id': cost.id,
                        'company_id': cost.company_id.id,
                        'date': cost.date,
                    })
                    linked_layer.remaining_value += cost_to_add
                    valuation_layer_ids.append(valuation_layer.id)
                # Update the AVCO/FIFO
                product = line.move_id.product_id
                if product.cost_method in ['average', 'fifo']:
                    cost_to_add_byproduct[product] += cost_to_add
                # Products with manual inventory valuation are ignored because they do not need to create journal entries.
                if product.valuation != "real_time":
                    continue
                # `remaining_qty` is negative if the move is out and delivered proudcts that were not
                # in stock.
                qty_out = 0
                if line.move_id._is_in():
                    qty_out = line.move_id.quantity - remaining_qty
                elif line.move_id._is_out():
                    qty_out = line.move_id.quantity
                move_vals['line_ids'] += line._create_accounting_entries(move, qty_out)

            # batch standard price computation avoid recompute quantity_svl at each iteration
            products = self.env['product.product'].browse(p.id for p in cost_to_add_byproduct.keys()).with_company(cost.company_id)
            for product in products:  # iterate on recordset to prefetch efficiently quantity_svl
                if not float_is_zero(product.quantity_svl, precision_rounding=product.uom_id.rounding):
                    product.sudo().with_context(disable_auto_svl=True).standard_price += cost_to_add_byproduct[product] / product.quantity_svl

            move_vals['stock_valuation_layer_ids'] = [(6, None, valuation_layer_ids)]
            # We will only create the accounting entry when there are defined lines (the lines will be those linked to products of real_time valuation category).
            cost_vals = {'state': 'done'}
            if move_vals.get("line_ids"):
                move = move.create(move_vals)
                cost_vals.update({'account_move_id': move.id})
            cost.write(cost_vals)
            if cost.account_move_id:
                move._post()
            cost.reconcile_landed_cost()
        return True