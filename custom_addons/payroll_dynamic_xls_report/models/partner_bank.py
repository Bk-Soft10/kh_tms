from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class PartnerBank(models.Model):
    _inherit = 'res.partner.bank'
    

    iban = fields.Char("IBAN")


'''
class EmployeePublic(models.Model):
    _inherit = 'res.partner.bank'
    

    iban = fields.Char("IBAN")

'''