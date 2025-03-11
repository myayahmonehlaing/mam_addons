# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PurchaseRefuseWizard(models.TransientModel):
    """This wizard can be launched from an he.expense (an expense line)
    or from an hr.expense.sheet (En expense report)
    'hr_expense_refuse_model' must be passed in the context to differentiate
    the right model to use.
    """

    _name = "purchase.refuse.wizard"
    _description = "Purchase Refuse Reason Wizard"

    reason = fields.Char(string='Reason', required=True)
    order_id = fields.Many2one('purchase.order')

    @api.model
    def default_get(self, fields):
        res = super(PurchaseRefuseWizard, self).default_get(fields)
        active_ids = self.env.context.get('active_ids', [])
        res.update({
            'order_id': active_ids[0] if active_ids else False,

        })
        return res

    def purchase_refuse_reason(self):
        self.ensure_one()
        if self.order_id:
            self.order_id.refuse_order(self.reason)
        return {'type': 'ir.actions.act_window_close'}
