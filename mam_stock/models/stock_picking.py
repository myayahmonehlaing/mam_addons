# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import SUPERUSER_ID, Command,_, api, fields, models



class Picking(models.Model):
    _inherit = "stock.picking"


    date_done = fields.Datetime('Date of Transfer', copy=False, readonly=False, help="Date at which the transfer has been processed or cancelled.")

    def _action_done(self):
        """Call `_action_done` on the `stock.move` of the `stock.picking` in `self`.
        This method makes sure every `stock.move.line` is linked to a `stock.move` by either
        linking them to an existing one or a newly created one.

        If the context key `cancel_backorder` is present, backorders won't be created.

        :return: True
        :rtype: bool
        """
        self._check_company()
        date = fields.Datetime.now()
        todo_moves = self.move_ids.filtered(lambda self: self.state in ['draft', 'waiting', 'partially_available', 'assigned', 'confirmed'])
        for picking in self:
            date = picking.date_done if picking.date_done else date
            if picking.owner_id:
                picking.move_ids.write({'restrict_partner_id': picking.owner_id.id})
                picking.move_line_ids.write({'owner_id': picking.owner_id.id})
            todo_moves = picking.move_ids.filtered(lambda self: self.state in ['draft', 'waiting', 'partially_available', 'assigned', 'confirmed'])
            todo_moves.with_context(force_period_date=date)._action_done(cancel_backorder=self.env.context.get('cancel_backorder'))
            picking.write({'date_done': date, 'priority': '0'})

        # if incoming/internal moves make other confirmed/partially_available moves available, assign them
        done_incoming_moves = self.filtered(lambda p: p.picking_type_id.code in ('incoming', 'internal')).move_ids.filtered(lambda m: m.state == 'done')
        done_incoming_moves._trigger_assign()
        self._send_confirmation_email()
        return True




