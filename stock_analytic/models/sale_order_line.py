from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _prepare_procurement_values(self, group_id=False):
        vals = super()._prepare_procurement_values(group_id=group_id)
        vals["analytic_distribution"] = self.analytic_distribution
        return vals


class StockRule(models.Model):
    _inherit = "stock.rule"

    def _get_custom_move_fields(self):
        fields = super()._get_custom_move_fields()
        fields += ["analytic_distribution"]
        return fields