# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime , date
import logging
_logger = logging.getLogger(__name__)

class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip'  # change from hr.payslip.run
    
    
    @api.onchange('date_start')
    def onchange_datestart(self):
        if self.date_start:
            self.name =  'Monthly payroll of '+(self.date_start).strftime('%B %Y')




    name = fields.Char(default=lambda self: 'Monthly payroll of '+(date.today()).strftime('%B %Y'))

    

