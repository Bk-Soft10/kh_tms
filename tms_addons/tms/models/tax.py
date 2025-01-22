from odoo import models, fields, api, _

class AccountTax(models.Model):
    _inherit = 'account.tax'
    
    license_id = fields.Char(string='License ID')
    #advanced_booleans
    