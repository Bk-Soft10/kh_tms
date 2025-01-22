from odoo import models, fields , api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    commercial_registration = fields.Char(
        string='Commercial Registration',
        help="Commercial Registration number of the company"
    )

    #is_customer = fields.Boolean(string='Is a Customer', default=False)
    #is_vendor = fields.Boolean(string='Is a Vendor', default=False)

    #@api.onchange('is_customer', 'is_vendor')
    #def _onchange_partner_type(self):
    #    if self.is_customer:
    #        self.customer_rank = 1
    #    else:
    #        self.customer_rank = 0

    #    if self.is_vendor:
    #        self.supplier_rank = 1
    #    else:
    #        self.supplier_rank = 0
