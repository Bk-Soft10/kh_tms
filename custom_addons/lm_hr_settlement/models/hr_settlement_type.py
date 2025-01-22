# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HrSettlement(models.Model):
    _name = 'hr.settlement.type'
    _description = 'HR Payroll Settlement'

    name = fields.Char('Name')
    salary_rule_id = fields.Many2one('hr.salary.rule')
    type = fields.Selection([('alw', 'Allowance'), ('ded', 'Deduction')], string='Type')
    code = fields.Char(related='salary_rule_id.code', string='Type')



