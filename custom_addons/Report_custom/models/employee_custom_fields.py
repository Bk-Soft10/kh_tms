from odoo import models, fields

class Employee(models.Model):
    _inherit = 'hr.employee'

    iban_number = fields.Char(string="Bank account number (IBAN)")
    bank_name = fields.Char(string="Bank name")
    residence_number = fields.Char(string="al-aqama number ")
    residence_expiry_date = fields.Date(string="al-aqama expiry date")
    hs_no = fields.Char(string="HS-NO")
    border_number = fields.Char(string="Border Number")
    hanger_station_mobile = fields.Char(string="Hanger Station Mobile Number")
    fuel_card = fields.Char(string="Fuel Card")
