from odoo import api, fields, models, tools, _

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def action_print_salary_computation(self):
        return self.env.ref('om_hr_payroll.action_report_salary_computation').report_action(self)