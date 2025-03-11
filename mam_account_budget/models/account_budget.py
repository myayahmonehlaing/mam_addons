# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from datetime import timedelta
import itertools

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv.expression import AND
class CrossoveredBudget(models.Model):
    _name = "mam.budget"
    _description = "Budget"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Budget Name', required=True)
    date_from = fields.Date('Start Date', required=True)
    date_to = fields.Date('End Date', required=True)
    work_account_id = fields.Many2one('account.analytic.account', 'Detail Work',required=True)
    project_account_id = fields.Many2one('account.analytic.account', 'Project Code', required=True)
    building_account_id = fields.Many2one('account.analytic.account', 'Building ',required=True)
    general_budget_id = fields.Many2one('account.budget.post', 'Budgetary Position',required=True)
    user_id = fields.Many2one('res.users', 'Responsible', default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('validate', 'Validated'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], 'Status', default='draft', index=True, required=True, readonly=True, copy=False, tracking=True)
    budget_line = fields.One2many('mam.budget.lines', 'budget_id', 'Budget Lines', copy=True)
    company_id = fields.Many2one('res.company', 'Company', required=True,
        default=lambda self: self.env.company)
    type = fields.Selection([
        ('income', 'Revenue'),
        ('expense', 'Expense'),],default='expense')


    def action_budget_confirm(self):
        self.write({'state': 'confirm'})

    def action_budget_draft(self):
        self.write({'state': 'draft'})

    def action_budget_validate(self):
        self.write({'state': 'validate'})

    def action_budget_cancel(self):
        self.write({'state': 'cancel'})

    def action_budget_done(self):
        self.write({'state': 'done'})


class MamBudgetLines(models.Model):
    _name = "mam.budget.lines"
    _description = "Budget Line"

    name = fields.Char(compute='_compute_line_name')
    date_from = fields.Date(related='budget_id.date_from', store=True)
    date_to = fields.Date(related='budget_id.date_to', store=True)
    work_account_id = fields.Many2one('account.analytic.account',related='budget_id.work_account_id',store=True)
    product_id = fields.Many2one('product.product')
    project_account_id = fields.Many2one('account.analytic.account',related='budget_id.project_account_id', store=True)
    building_account_id = fields.Many2one('account.analytic.account', 'Building Account',related='budget_id.building_account_id',store=True)
    general_budget_id = fields.Many2one('account.budget.post', 'Budgetary Position',related='budget_id.general_budget_id', store=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    budget_id = fields.Many2one('mam.budget', 'Budget', ondelete='cascade', index=True,
                                            required=True)
    company_id = fields.Many2one(related='budget_id.company_id', comodel_name='res.company',
        string='Company', store=True, readonly=True)
    is_above_budget = fields.Boolean(compute='_is_above_budget')
    budget_state = fields.Selection(related='budget_id.state', string='Budget State',
                                                store=True, readonly=True)

    budget_qty = fields.Float("Budget Qty")
    budget_unit_price = fields.Float("Budget Price")
    budget_amount = fields.Monetary("Budget Amount",compute='_compute_budget_amount')

    actual_qty = fields.Float("Actual Qty",compute='_compute_actual_qty')
    actual_unit_price = fields.Float("Actual Price",compute='_compute_actual_price')
    actual_amount = fields.Monetary("Actual Amount",compute='_compute_actual_amount')

    difference_qty = fields.Float("Difference Qty",compute='_compute_difference_qty')
    difference_amount = fields.Monetary("Difference Amount",compute='_compute_difference_amount')

    @api.model_create_multi
    def create(self, vals_list):
        result= super().create(vals_list)

        for budget_line in result:
            if budget_line.budget_id.type == 'expense':
                budget_line.budget_qty *= -1
        return result

    def write(self, vals):
        if 'budget_qty' in vals:
            if vals.get('budget_qty') > 0 and self.budget_id.type == 'expense':
                vals['budget_qty'] *=-1
        res = super().write(vals)
        return res

    @api.model
    def _read_group(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None):
        SPECIAL = {'budget_qty:sum', 'budget_amount:sum', 'actual_qty:sum','actual_amount:sum','difference_qty:sum','difference_amount:sum'}
        if SPECIAL.isdisjoint(aggregates):
            return super()._read_group(domain, groupby, aggregates, having, offset, limit, order)

        base_aggregates = [*(agg for agg in aggregates if agg not in SPECIAL), 'id:recordset']
        base_result = super()._read_group(domain, groupby, base_aggregates, having, offset, limit, order)

        # base_result = [(a1, b1, records), (a2, b2, records), ...]
        result = []
        for *other, records in base_result:
            for index, spec in enumerate(itertools.chain(groupby, aggregates)):
                if spec in SPECIAL:
                    field_name = spec.split(':')[0]
                    other.insert(index, sum(records.mapped(field_name)))
            result.append(tuple(other))

        return result


    def _compute_difference_qty(self):
        for line in self:
            line.difference_qty = (line.budget_qty - line.actual_qty) * -1

    def _compute_difference_amount(self):
        for line in self:
            line.difference_amount = (line.budget_amount - line.actual_amount)* -1


    def _is_above_budget(self):
        for line in self:
            if line.budget_amount > line.actual_amount:
                line.is_above_budget = True
            else:
                line.is_above_budget = False

    @api.depends("budget_id","work_account_id")
    def _compute_line_name(self):
        #just in case someone opens the budget line in form view
        for record in self:
            computed_name = record.budget_id.name
            if record.general_budget_id:
                computed_name += ' - ' + record.general_budget_id.name
            if record.work_account_id:
                computed_name += ' - ' + record.work_account_id.name
            record.name = computed_name

    @api.depends('budget_unit_price', 'budget_qty')
    def _compute_budget_amount(self):
        for line in self:
            # multiple = - 1 if line.budget_id.type == 'expense' else 1
            line.budget_amount = line.budget_unit_price * line.budget_qty

    def _compute_actual_price(self):
        for line in self:
            line.actual_unit_price = line.actual_amount / ( line.actual_qty if line.actual_qty else 1 )

    def _compute_actual_qty(self):
        for line in self:
            date_to = line.date_to
            date_from = line.date_from
            acc_ids = line.general_budget_id.account_ids.ids
            if line.work_account_id.id:
                analytic_line_obj = self.env['account.analytic.line']
                domain = [(line.work_account_id.plan_id._column_name(), 'in', line.work_account_id.ids),
                          ('date', '>=', date_from),
                          ('date', '<=', date_to),
                          ('product_id', '=', line.product_id.id),
                          (line.project_account_id.plan_id._column_name(), '=',line.project_account_id.id),
                          (line.building_account_id.plan_id._column_name(), '=', line.building_account_id.id),

                          ]

                if acc_ids:
                    domain += [('general_account_id', 'in', acc_ids)]

                where_query = analytic_line_obj._where_calc(domain)
                analytic_line_obj._apply_ir_rules(where_query, 'read')
                from_clause, where_clause, where_clause_params = where_query.get_sql()
                select = "SELECT SUM((CASE WHEN  amount > 0 THEN 1 ELSE -1 END) * abs(unit_amount)) from " + from_clause + " where " + where_clause
            else:
                aml_obj = self.env['account.move.line']
                domain = [('account_id', 'in',
                           line.general_budget_id.account_ids.ids),
                          ('date', '>=', date_from),
                          ('date', '<=', date_to),
                          ('parent_state', '=', 'posted')
                          ]
                where_query = aml_obj._where_calc(domain)
                aml_obj._apply_ir_rules(where_query, 'read')
                from_clause, where_clause, where_clause_params = where_query.get_sql()
                select = "SELECT sum(quantity) from " + from_clause + " where " + where_clause

            self.env.cr.execute(select, where_clause_params)
            line.actual_qty = self.env.cr.fetchone()[0] or 0.0

    def _compute_actual_amount(self):
        for line in self:
            date_to = line.date_to
            date_from = line.date_from
            acc_ids = line.general_budget_id.account_ids.ids
            if line.work_account_id.id:
                analytic_line_obj = self.env['account.analytic.line']
                domain = [
                           (line.work_account_id.plan_id._column_name(), 'in', line.work_account_id.ids),
                          ('date', '>=', date_from),
                          ('date', '<=', date_to),
                          ('product_id', '=', line.product_id.id),
                          (line.project_account_id.plan_id._column_name(), '=', line.project_account_id.id),
                          (line.building_account_id.plan_id._column_name(), '=', line.building_account_id.id),

                          ]
                if acc_ids:
                    domain += [('general_account_id', 'in', acc_ids)]

                where_query = analytic_line_obj._where_calc(domain)
                analytic_line_obj._apply_ir_rules(where_query, 'read')
                from_clause, where_clause, where_clause_params = where_query.get_sql()
                select = "SELECT SUM(amount) from " + from_clause + " where " + where_clause
            else:
                aml_obj = self.env['account.move.line']
                domain = [('account_id', 'in',
                           line.general_budget_id.account_ids.ids),
                          ('date', '>=', date_from),
                          ('date', '<=', date_to),
                          ('parent_state', '=', 'posted')
                          ]
                where_query = aml_obj._where_calc(domain)
                aml_obj._apply_ir_rules(where_query, 'read')
                from_clause, where_clause, where_clause_params = where_query.get_sql()
                select = "SELECT sum(credit)-sum(debit) from " + from_clause + " where " + where_clause

            self.env.cr.execute(select, where_clause_params)
            line.actual_amount = self.env.cr.fetchone()[0] or 0.0



    def action_open_budget_entries(self):
        if self.work_account_id:
            acc_ids = self.general_budget_id.account_ids.ids
            # if there is an analytic account, then the analytic items are loaded
            action = self.env['ir.actions.act_window']._for_xml_id('analytic.account_analytic_line_action_entries')
            action['domain']  = [
                                (self.work_account_id.plan_id._column_name(), 'in', self.work_account_id.ids),
                                ('date', '>=', self.date_from),
                                ('date', '<=', self.date_to),
                                ('product_id', '=', self.product_id.id),
                                (self.project_account_id.plan_id._column_name(), 'in', self.project_account_id.ids),
                                (self.building_account_id.plan_id._column_name(), '=', self.building_account_id.id),

                                ]
            if acc_ids:
                action['domain'] += [('general_account_id', 'in', acc_ids)]

        return action

class CrossoveredBudget(models.Model):
    _inherit = "crossovered.budget"

    mam_budget = fields.Boolean()


class CrossoveredBudgetLines(models.Model):
    _inherit = "crossovered.budget.lines"

    crossovered_budget_id = fields.Many2one('crossovered.budget', 'Budget', ondelete='cascade', index=True, required=True)
    mam_budget_id = fields.Many2one('mam.budget','Budget Details')
    mam_budget = fields.Boolean('MAM Budget',store=True,related='crossovered_budget_id.mam_budget')
    planned_amount = fields.Monetary(
        'Planned Amount', required=False,compute='_compute_planned_amount',inverse="_inverse_planned_amount",store=True,
        help="Amount you plan to earn/spend. Record a positive amount if it is a revenue and a negative amount if it is a cost.")
    analytic_account_id = fields.Many2one('account.analytic.account', 'Project Code ',)
    work_account_id = fields.Many2one('account.analytic.account', 'Detail Work',)
    building_account_id = fields.Many2one('account.analytic.account', 'Building',)


    @api.onchange('mam_budget_id')
    def _onchange_mam_budget_id(self):
        if self.mam_budget_id :
            self.analytic_account_id = self.mam_budget_id.project_account_id.id
            self.work_account_id = self.mam_budget_id.work_account_id.id
            self.building_account_id = self.mam_budget_id.building_account_id.id
            self.general_budget_id = self.mam_budget_id.general_budget_id.id

    def _inverse_planned_amount(self):
        pass

    @api.depends('mam_budget_id.budget_line')
    def _compute_planned_amount(self):
        for line in self:
            planned_amount =0.0
            if line.mam_budget_id.id:
                planned_amount = sum((budget_line.budget_amount for budget_line in line.mam_budget_id.budget_line ))
            line.planned_amount = planned_amount



    def _compute_practical_amount(self):
        for line in self:
            acc_ids = line.general_budget_id.account_ids.ids
            date_to = line.date_to
            date_from = line.date_from
            if line.analytic_account_id.id:
                analytic_line_obj = self.env['account.analytic.line']
                domain = [(line.analytic_account_id.plan_id._column_name(), '=', line.analytic_account_id.id),
                          ('date', '>=', date_from),
                          ('date', '<=', date_to),
                          ]
                if acc_ids:
                    domain += [('general_account_id', 'in', acc_ids)]

                if line.work_account_id:
                    domain += [(line.work_account_id.plan_id._column_name(), '=', line.work_account_id.id)]

                if line.building_account_id:
                    domain += [(line.building_account_id.plan_id._column_name(), '=', line.building_account_id.id)]
                where_query = analytic_line_obj._where_calc(domain)
                analytic_line_obj._apply_ir_rules(where_query, 'read')
                from_clause, where_clause, where_clause_params = where_query.get_sql()
                select = "SELECT SUM(amount) from " + from_clause + " where " + where_clause

            else:
                aml_obj = self.env['account.move.line']
                domain = [('account_id', 'in',
                           line.general_budget_id.account_ids.ids),
                          ('date', '>=', date_from),
                          ('date', '<=', date_to),
                          ('parent_state', '=', 'posted')
                          ]
                where_query = aml_obj._where_calc(domain)
                aml_obj._apply_ir_rules(where_query, 'read')
                from_clause, where_clause, where_clause_params = where_query.get_sql()
                select = "SELECT sum(credit)-sum(debit) from " + from_clause + " where " + where_clause

            self.env.cr.execute(select, where_clause_params)
            line.practical_amount = self.env.cr.fetchone()[0] or 0.0



    def action_open_budget_entries(self):
        if self.analytic_account_id :
            # if there is an analytic account, then the analytic items are loaded
            action = self.env['ir.actions.act_window']._for_xml_id('analytic.account_analytic_line_action_entries')
            action['domain'] = [('auto_account_id', '=', self.analytic_account_id.id),
                                ('date', '>=', self.date_from),
                                ('date', '<=', self.date_to)
                                ]
            if self.general_budget_id:
                action['domain'] += [('general_account_id', 'in', self.general_budget_id.account_ids.ids)]

            if self.work_account_id:
                action['domain'] += [(self.work_account_id.plan_id._column_name(), '=', self.work_account_id.id)]

            if self.building_account_id:
                action['domain'] += [(self.building_account_id.plan_id._column_name(), '=', self.building_account_id.id)]


        else:
            # otherwise the journal entries booked on the accounts of the budgetary postition are opened
            action = self.env['ir.actions.act_window']._for_xml_id('account.action_account_moves_all_a')
            action['domain'] = [('account_id', 'in',
                                 self.general_budget_id.account_ids.ids),
                                ('date', '>=', self.date_from),
                                ('date', '<=', self.date_to)
                                ]
        return action

