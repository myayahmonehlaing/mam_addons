# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from collections import Counter, defaultdict
from odoo.osv import expression
from odoo import _, api, fields, tools, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import OrderedSet, groupby
from odoo.tools import float_compare, float_is_zero, format_list,float_round
from odoo.tools.misc import format_datetime


class StockMove(models.Model):
    _inherit = "stock.move"

    product_id = fields.Many2one(
        'product.product', 'Product',
        check_company=True,
        domain="[('type', 'in', ['product', 'consu'])]", index=True, required=True)

    allowed_product_ids = fields.Many2many("product.product", compute='_compute_allowed_product_ids')

    @api.depends('picking_id.picking_type_id', 'picking_id.picking_type_id.warehouse_id'
        , 'picking_id.picking_type_id.warehouse_id.region_id')
    def _compute_allowed_product_ids(self):
        for record in self:
            record.allowed_product_ids = self.env["product.product"].search(
                [('region_id', '=', record.picking_id.picking_type_id.warehouse_id.region_id.id)])

    @api.constrains('product_id')
    def _check_product_id(self):
        for record in self:
            if record.picking_id and not record.product_id in record.allowed_product_ids:
                raise ValidationError(_("Error ! You cannot save a picking with unallowed product."))

    def _action_done(self, cancel_backorder=False):

        res = super(StockMove, self)._action_done(cancel_backorder=cancel_backorder)
        date = self._context.get('force_period_date', fields.Datetime.now())
        for move in self:
            move.write({'date': date})
        return res

    def _action_confirm(self, merge=False, merge_into=False):
        moves = super(StockMove, self)._action_confirm(merge=merge, merge_into=merge_into)
        return moves


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _action_done(self):
        """ This method is called during a move's `action_done`. It'll actually move a quant from
        the source location to the destination location, and unreserve if needed in the source
        location.

        This method is intended to be called on all the move lines of a move. This method is not
        intended to be called when editing a `done` move (that's what the override of `write` here
        is done.
        """

        # First, we loop over all the move lines to do a preliminary check: `quantity` should not
        # be negative and, according to the presence of a picking type or a linked inventory
        # adjustment, enforce some rules on the `lot_id` field. If `quantity` is null, we unlink
        # the line. It is mandatory in order to free the reservation and correctly apply
        # `action_done` on the next move lines.
        ml_ids_tracked_without_lot = OrderedSet()
        ml_ids_to_delete = OrderedSet()
        ml_ids_to_create_lot = OrderedSet()
        ml_ids_to_check = defaultdict(OrderedSet)

        for ml in self:
            # Check here if `ml.quantity` respects the rounding of `ml.product_uom_id`.
            uom_qty = float_round(ml.quantity, precision_rounding=ml.product_uom_id.rounding, rounding_method='HALF-UP')
            precision_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
            quantity = float_round(ml.quantity, precision_digits=precision_digits, rounding_method='HALF-UP')
            if float_compare(uom_qty, quantity, precision_digits=precision_digits) != 0:
                raise UserError(_('The quantity done for the product "%(product)s" doesn\'t respect the rounding precision '
                                  'defined on the unit of measure "%(unit)s". Please change the quantity done or the '
                                  'rounding precision of your unit of measure.',
                                  product=ml.product_id.display_name, unit=ml.product_uom_id.name))

            qty_done_float_compared = float_compare(ml.quantity, 0, precision_rounding=ml.product_uom_id.rounding)
            if qty_done_float_compared > 0:
                if ml.product_id.tracking == 'none':
                    continue
                picking_type_id = ml.move_id.picking_type_id
                if not picking_type_id and not ml.is_inventory and not ml.lot_id:
                    ml_ids_tracked_without_lot.add(ml.id)
                    continue
                if not picking_type_id or ml.lot_id or (not picking_type_id.use_create_lots and not picking_type_id.use_existing_lots):
                    # If the user disabled both `use_create_lots` and `use_existing_lots`
                    # checkboxes on the picking type, he's allowed to enter tracked
                    # products without a `lot_id`.
                    continue
                if picking_type_id.use_create_lots:
                    ml_ids_to_check[(ml.product_id, ml.company_id)].add(ml.id)
                else:
                    ml_ids_tracked_without_lot.add(ml.id)

            elif qty_done_float_compared < 0:
                raise UserError(_('No negative quantities allowed'))
            elif not ml.is_inventory:
                ml_ids_to_delete.add(ml.id)

        for (product, company), mls in ml_ids_to_check.items():
            mls = self.env['stock.move.line'].browse(mls)
            lots = self.env['stock.lot'].search([
                '|', ('company_id', '=', False), ('company_id', '=', ml.company_id.id),
                ('product_id', '=', product.id),
                ('name', 'in', mls.mapped('lot_name')),
            ])
            lots = {lot.name: lot for lot in lots}
            for ml in mls:
                lot = lots.get(ml.lot_name)
                if lot:
                    ml.lot_id = lot.id
                elif ml.lot_name:
                    ml_ids_to_create_lot.add(ml.id)
                else:
                    ml_ids_tracked_without_lot.add(ml.id)

        if ml_ids_tracked_without_lot:
            mls_tracked_without_lot = self.env['stock.move.line'].browse(ml_ids_tracked_without_lot)
            products_list = "\n".join(f"- {product_name}" for product_name in mls_tracked_without_lot.mapped("product_id.display_name"))
            raise UserError(
                _(
                    "You need to supply a Lot/Serial Number for product:\n%(products)s",
                    products=products_list,
                ),
            )
        if ml_ids_to_create_lot:
            self.env['stock.move.line'].browse(ml_ids_to_create_lot)._create_and_assign_production_lot()

        mls_to_delete = self.env['stock.move.line'].browse(ml_ids_to_delete)
        mls_to_delete.unlink()

        mls_todo = (self - mls_to_delete)
        mls_todo._check_company()

        # Now, we can actually move the quant.
        ml_ids_to_ignore = OrderedSet()
        quants_cache = self.env['stock.quant']._get_quants_by_products_locations(
            mls_todo.product_id, mls_todo.location_id | mls_todo.location_dest_id,
            extra_domain=['|', ('lot_id', 'in', mls_todo.lot_id.ids), ('lot_id', '=', False)])

        for ml in mls_todo.with_context(quants_cache=quants_cache):
            # if this move line is force assigned, unreserve elsewhere if needed
            ml._synchronize_quant(-ml.quantity_product_uom, ml.location_id, action="reserved")
            available_qty, in_date = ml._synchronize_quant(-ml.quantity_product_uom, ml.location_id)
            ml._synchronize_quant(ml.quantity_product_uom, ml.location_dest_id, package=ml.result_package_id, in_date=in_date)
            if available_qty < 0:
                ml._free_reservation(
                    ml.product_id, ml.location_id,
                    abs(available_qty), lot_id=ml.lot_id, package_id=ml.package_id,
                    owner_id=ml.owner_id, ml_ids_to_ignore=ml_ids_to_ignore)
            ml_ids_to_ignore.add(ml.id)
        # Reset the reserved quantity as we just moved it to the destination location.
        date = self._context.get('force_period_date', fields.Datetime.now())
        mls_todo.write({
            'date': date,
        })


class StockQuant(models.Model):
    _inherit = "stock.quant"

    @api.model
    def _get_inventory_fields_write(self):
        """ Returns a list of fields user can edit when editing a quant in `inventory_mode`."""
        res = super()._get_inventory_fields_write()
        res += ['in_date']
        return res

    def create(self, vals):
        date = self._context.get('force_period_date', fields.Datetime.now())
        if (type(vals) == list):
            for val in vals:
                val['in_date'] = date
        else:
            vals.update({'in_date': date})
        return super().create(vals)


class StockValuationLayer(models.Model):
    _inherit = "stock.valuation.layer"
    _order = 'date, id'

    date = fields.Datetime('Inventory Date', )

    def create(self, vals):
        date = self._context.get('force_period_date', fields.Datetime.now())
        if type(vals) is list:
            for val in vals:
                val.update({'date': date})
        return super().create(vals)


class StockScrap(models.Model):
    _inherit = 'stock.scrap'

    date_done = fields.Datetime('Date', readonly=False)

    def do_scrap(self):
        self._check_company()
        for scrap in self:
            date = scrap.date_done if scrap.date_done else fields.Datetime.now()
            scrap.name = self.env['ir.sequence'].next_by_code('stock.scrap') or _('New')
            move = self.env['stock.move'].create(scrap._prepare_move_values())
            # master: replace context by cancel_backorder
            move.with_context(force_period_date=date, is_scrap=True)._action_done()
            scrap.write({'state': 'done'})
            scrap.date_done = date
            if scrap.should_replenish:
                scrap.do_replenish()
        return True


class StockQuantityHistory(models.TransientModel):
    _inherit = 'stock.quantity.history'

    def open_at_date(self):
        active_model = self.env.context.get('active_model')
        if active_model == 'stock.valuation.layer':
            action = self.env["ir.actions.actions"]._for_xml_id("stock_account.stock_valuation_layer_action")
            # views may not exist in stable => use auto-created ones in this case
            action['views'] = [
                (self.env.ref('stock_account.stock_valuation_layer_valuation_at_date_tree_inherited').id, 'list'),
                (self.env.ref('stock_account.stock_valuation_layer_form').id, 'form'),
                (self.env.ref('stock_account.stock_valuation_layer_pivot').id, 'pivot'),
                (self.env.ref('stock_account.stock_valuation_layer_graph').id, 'graph')]
            action['domain'] = [('date', '<=', self.inventory_datetime), ('product_id.is_storable', '=', 'product')]
            action['display_name'] = format_datetime(self.env, self.inventory_datetime)
            action['context'] = "{}"
            return action
        return super(StockQuantityHistory, self).open_at_date()


class StockValuationLayerRevaluation(models.TransientModel):
    _inherit = 'stock.valuation.layer.revaluation'

    def action_validate_revaluation(self):
        """ Adjust the valuation of layers `self.adjusted_layer_ids` for
        `self.product_id` in `self.company_id`, or the entire stock for that
        product if no layers are specified (all layers with positive remaining
        quantity).

        - Change the standard price with the new valuation by product unit.
        - Create a manual stock valuation layer with the `added_value` of `self`.
        - Distribute the `added_value` on the remaining_value of the layers
        - If the Inventory Valuation of the product category is automated, create
        related account move.
        """
        self.ensure_one()
        if self.currency_id.is_zero(self.added_value):
            raise UserError(_("The added value doesn't have any impact on the stock valuation"))

        product_id = self.product_id.with_company(self.company_id)
        lot_id = self.lot_id.with_company(self.company_id)

        remaining_domain = [
            ('product_id', '=', product_id.id),
            ('remaining_qty', '>', 0),
            ('company_id', '=', self.company_id.id),
        ]
        if lot_id:
            remaining_domain.append(('lot_id', '=', lot_id.id))
        layers_with_qty = self.env['stock.valuation.layer'].search(remaining_domain)
        adjusted_layers = self.adjusted_layer_ids or layers_with_qty

        description = _("Manual Stock Valuation: %s.", self.reason or _("No Reason Given"))
        # Update the stardard price in case of AVCO/FIFO
        cost_method = product_id.categ_id.property_cost_method
        if cost_method in ['average', 'fifo']:
            previous_cost = lot_id.standard_price if lot_id else product_id.standard_price
            total_product_qty = sum(layers_with_qty.mapped('remaining_qty'))
            if lot_id:
                lot_id.with_context(disable_auto_svl=True).standard_price += self.added_value / total_product_qty
            product_id.with_context(disable_auto_svl=True).standard_price += self.added_value / product_id.quantity_svl
            if self.lot_id:
                description += _(
                    " lot/serial number cost updated from %(previous)s to %(new_cost)s.",
                    previous=previous_cost,
                    new_cost=lot_id.standard_price
                )
            else:
                description += _(
                    " Product cost updated from %(previous)s to %(new_cost)s.",
                    previous=previous_cost,
                    new_cost=product_id.standard_price
                )

        revaluation_svl_vals = {
            'company_id': self.company_id.id,
            'product_id': product_id.id,
            'description': description,
            'value': self.added_value,
            'lot_id': self.lot_id.id,
            'quantity': 0,
            'date': self.date,
        }

        qty_by_lots = defaultdict(float)

        remaining_qty = sum(adjusted_layers.mapped('remaining_qty'))
        remaining_value = self.added_value
        remaining_value_unit_cost = self.currency_id.round(remaining_value / remaining_qty)

        # adjust all layers by the unit value change per unit, except the last layer which gets
        # whatever is left. This avoids rounding issues e.g. $10 on 3 products => 3.33, 3.33, 3.34
        for svl in adjusted_layers:
            if product_id.lot_valuated and not lot_id:
                qty_by_lots[svl.lot_id.id] += svl.remaining_qty
            if float_is_zero(svl.remaining_qty - remaining_qty, precision_rounding=self.product_id.uom_id.rounding):
                taken_remaining_value = remaining_value
            else:
                taken_remaining_value = remaining_value_unit_cost * svl.remaining_qty
            if float_compare(svl.remaining_value + taken_remaining_value, 0,
                             precision_rounding=self.product_id.uom_id.rounding) < 0:
                raise UserError(
                    _('The value of a stock valuation layer cannot be negative. Landed cost could be use to correct a specific transfer.'))

            svl.remaining_value += taken_remaining_value
            remaining_value -= taken_remaining_value
            remaining_qty -= svl.remaining_qty

        previous_value_svl = self.current_value_svl

        if qty_by_lots:
            vals = revaluation_svl_vals.copy()
            total_qty = sum(adjusted_layers.mapped('remaining_qty'))
            revaluation_svl_vals = []
            for lot, qty in qty_by_lots.items():
                value = self.added_value * qty / total_qty
                revaluation_svl_vals.append(
                    dict(vals, value=value, lot_id=lot)
                )

        revaluation_svl = self.env['stock.valuation.layer'].create(revaluation_svl_vals)

        # If the Inventory Valuation of the product category is automated, create related account move.
        if self.property_valuation != 'real_time':
            return True

        accounts = product_id.product_tmpl_id.get_product_accounts()

        if self.added_value < 0:
            debit_account_id = self.account_id.id
            credit_account_id = accounts.get('stock_valuation') and accounts['stock_valuation'].id
        else:
            debit_account_id = accounts.get('stock_valuation') and accounts['stock_valuation'].id
            credit_account_id = self.account_id.id

        move_description = _(
            '%(user)s changed stock valuation from  %(previous)s to %(new_value)s - %(product)s\n%(reason)s',
            user=self.env.user.name,
            previous=previous_value_svl,
            new_value=previous_value_svl + self.added_value,
            product=product_id.display_name,
            reason=description,
            )

        if self.adjusted_layer_ids:
            adjusted_layer_descriptions = [f"{layer.reference} (id: {layer.id})" for layer in self.adjusted_layer_ids]
            move_description += _("\nAffected valuation layers: %s", format_list(self.env, adjusted_layer_descriptions))

        move_vals = [{
            'journal_id': self.account_journal_id.id or accounts['stock_journal'].id,
            'company_id': self.company_id.id,
            'ref': _("Revaluation of %s", product_id.display_name),
            'stock_valuation_layer_ids': [(6, None, [svl.id])],
            'date': self.date or fields.Date.today(),
            'move_type': 'entry',
            'line_ids': [(0, 0, {
                'name': move_description,
                'account_id': debit_account_id,
                'debit': abs(svl.value),
                'credit': 0,
                'product_id': svl.product_id.id,
            }), (0, 0, {
                'name': move_description,
                'account_id': credit_account_id,
                'debit': 0,
                'credit': abs(svl.value),
                'product_id': svl.product_id.id,
            })],
        } for svl in revaluation_svl]
        account_move = self.env['account.move'].create(move_vals)
        account_move._post()

        return True

