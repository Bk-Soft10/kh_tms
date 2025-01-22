from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    commercial_registration = fields.Char(
        string='Commercial Registration',
        help="Commercial Registration number of the company"
    )
