
import time
from datetime import datetime
from datetime import time as datetime_time
from dateutil import relativedelta

import babel

from odoo import api, fields, models, tools, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError

class Employee(models.Model):

    _inherit = "hr.employee"
    
    state = fields.Selection([("1", 'Not specified'),
                              ("2", 'Active'),
                              ("3", 'Leave'),
                              ("4", 'Exit')], type='integer', string='State', default="1")
    
    
    id_issue_place = fields.Char(string='Id Issue Place')
    id_expiry_date = fields.Date(string='Id Expiry Date')
    id_expiry_hijry = fields.Char(string='Id Expiry Date')
    passport_issue_date = fields.Date(string='Passport Issue Date')
    passport_expiry_date = fields.Date(string='Passport Expiry Date')
    passport_source = fields.Char(string='Passport Source') 
    profession = fields.Char(string='Profession') 
    social_no = fields.Char(string='Social No') 
    guarantor  = fields.Char(string='Guarantor')
    medical_insurance_no = fields.Char(string='Medical insurance') 
    medical_insurance_count = fields.Integer(string='Medical insurance Count')
    insurance_class  = fields.Char(string='Insurance Class')
    
    # @api.multi 
    @api.constrains('emp_code')
    def _check_ssn(self):
        for emp in self:
            if emp.emp_code:
                count = self.search([('id', '!=', emp.id if emp.id else 0), ('emp_code', '=', emp.emp_code)], limit=1, count=True)
                if count > 0:
                    raise ValidationError(_('Employee Code already exist'))
    
    
    # @api.multi
    @api.constrains('identification_id')
    def _check_identification_id(self):
        for emp in self:
            if emp.identification_id:
                count = self.search([('id', '!=', emp.id if emp.id else 0), ('identification_id', '=', emp.identification_id)], limit=1, count=True)
                if count > 0:
                    raise ValidationError(_('Employee id already exist'))
    
    def _get_is_driver(self):
        return self._context.get('driver', False)
    
    emp_code = fields.Char(string="Employee Code", copy=False)
    
    is_driver = fields.Boolean(string="Is Driver", default=_get_is_driver)
    
    truck_id = fields.Many2one('tms.truck')
      
    @api.onchange('user_id')
    def user_changed(self):
        if self.user_id:
            self.user_partner_id = self.user_id.partner_id
            self.work_email = self.user_id.email
            self.user_id.partner_id.employee=True
            
    
    @api.onchange('address_id')
    def onchange_address_id(self):
        if self.address_id:
            self.address_id.employee = True
            
    
    @api.model
    def create(self, vals):
        employee = super(Employee, self).create(vals)
        if employee.user_partner_id:
            employee.user_partner_id.write({'employee': True, 'customer': True})
        return employee
    
    
    # @api.multi
    def write(self, vals):
        ret = super(Employee, self).write(vals)
        if 'user_partner_id' in vals and vals['user_partner_id']:
            user_partner_id = self.env['res.partner'].browse(vals['user_partner_id'])
            user_partner_id.write({'employee': True, 'customer': False})
        return ret

