from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    hangersation_quantity = fields.Float(
        string='Quantity',
        help="hungerstation Quantity.",
    )
    hangersation_price = fields.Float(
        string='Price',
        help="The payment reference to set on journal items.",
    )
    show_hangersation_fields = fields.Boolean(
        string='Hangersation info',
        help="hungerstation (Quantity + Price)",
        default=False,
    )

    delivery_date_from = fields.Date(
        string='Delivery Date From',
        help="Start date of delivery period",
    )
    delivery_date_to = fields.Date(
        string='Delivery Date To',
        help="End date of delivery period",
    )
