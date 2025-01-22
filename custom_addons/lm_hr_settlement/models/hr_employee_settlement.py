# -*- coding: utf-8 -*-

from odoo import models, fields, api,_
from odoo.exceptions import ValidationError, UserError


class HrEmployeeSettlement(models.Model):
    _name = 'hr.employee.settlement'
    _description = 'HR Payroll Settlement Request'

    number = fields.Char('Name')
    employee_id = fields.Many2one('hr.employee')
    department_id = fields.Many2one('hr.department', related='employee_id.department_id')
    type = fields.Selection([('alw', 'Allowance'), ('ded', 'Deduction')], string='Type')
    settlement_id = fields.Many2one('hr.settlement.type', ondelete='restrict')
    calculation_method = fields.Selection([('fixed', 'Fixed'), ('percentage_basic', 'Percentage of Basic')],
                                          string='Calculation Method')
    percentage = fields.Float(string='Percentage')
    amount = fields.Float(string='Amount')
    duration = fields.Integer(string='Duration')
    total_amount = fields.Float(string='Total Amount')
    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done'),('cancel', 'Cancelled')],default='draft',string='State')
    notes = fields.Text()

    _rec_name = 'number'


    def unlink(self):
        if any(self.filtered(lambda settlement: settlement.state not in ('draft', 'cancel'))):
            raise UserError(_('You cannot delete a request which is not draft or cancelled!'))
        return super(HrEmployeeSettlement, self).unlink()

    @api.model_create_multi
    @api.returns('self', lambda value:value.id)
    def create(self, vals_list):
        for vals in vals_list:
            vals['number'] = self.env['ir.sequence'].next_by_code(self._name)
        return super(HrEmployeeSettlement, self).create(vals_list)

    def action_confirm(self):
        for record in self:
            record.state = 'done'

    def action_cancel(self):
        for record in self:
            record.state = 'cancel'

    @api.onchange('percentage', 'calculation_method', 'employee_id')
    def compute_amount(self):
        amount=0.0
        for rec in self:
            contract = rec.employee_id.contract_id
            if rec.calculation_method == 'percentage_basic':
                amount = (contract.wage * rec.percentage)/100
        self.amount = amount
        self.total_amount = amount * rec.duration


class Contract(models.Model):
    _inherit = 'hr.contract'
    _description = 'Contract Extension'

    def compute_settlement(self, payslip, code=None):
        result = 0.0
        settlement = self.env['hr.employee.settlement'].search(
            [('employee_id', '=', self.employee_id.id), ('start_date', '>=', payslip.date_from),('state', '=', 'done')])
        for rec in settlement:
            if rec.settlement_id.code == code:
                result = rec.amount
                if rec.sudo().settlement_id.type == "ded":
                    result *= -1
        return float(result)
