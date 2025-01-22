import logging
from datetime import timedelta
from odoo import fields, models, api , _

_logger = logging.getLogger(__name__)


class Employee(models.Model):
    _inherit = 'hr.employee'

    visa_warning_message = fields.Char(
        string="Visa Expiry Warning",
        compute='_compute_visa_warning',
        store=False
    )

    @api.depends('visa_expire')
    def _compute_visa_warning(self):
        notify_days = int(self.env['ir.config_parameter'].sudo().get_param(
            'hr_employee_visa_notification.notify_days_before_expiry', 7))

        today = fields.Date.today()

        for employee in self:
            if employee.visa_expire:


                warning_date = employee.visa_expire - timedelta(days=notify_days)
                if today >= warning_date:
                    # Set a warning message with the expiration date
                    employee.visa_warning_message = (
                        f"Visa expiring soon on {employee.visa_expire}"
                    )

                    # Post a message to the employee's record in the chatter
                    message = f"Your visa is expiring soon on {employee.visa_expire}. Please renew it."


                else:
                    employee.visa_warning_message = ""
            else:
                employee.visa_warning_message = ""
