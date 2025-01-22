# models/res_config_settings.py
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    notify_days_before_expiry = fields.Integer(
        string="Notify Days Before Expiry",
        config_parameter='hr_employee_visa_notification.notify_days_before_expiry',
        default=7,
        help="Number of days before visa expiration to start notifying."
    )
