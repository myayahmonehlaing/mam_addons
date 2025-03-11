# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountMoveRefuseWizard(models.TransientModel):
    """This wizard can be launched from an he.expense (an expense line)
    or from an hr.expense.sheet (En expense report)
    'hr_expense_refuse_model' must be passed in the context to differentiate
    the right model to use.
    """

    _name = "account.move.refuse.wizard"
    _description = "Account Move Refuse Reason Wizard"

    reason = fields.Char(string='Reason', required=True)
    move_id = fields.Many2one('account.move')

    @api.model
    def default_get(self, fields):
        res = super(AccountMoveRefuseWizard, self).default_get(fields)
        active_ids = self.env.context.get('active_ids', [])
        res.update({
            'move_id': active_ids[0] if active_ids else False,

        })
        return res

    def account_move_refuse_reason(self):
        self.ensure_one()
        if self.move_id:
            self.move_id.refuse_move(self.reason)
        return {'type': 'ir.actions.act_window_close'}
