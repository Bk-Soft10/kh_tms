import base64
from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    excel_sheet = fields.Binary(string="Excel Sheet")
    excel_filename = fields.Char(string="Excel Filename")

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        param = self.env['ir.config_parameter'].sudo()
        param.set_param('custom_excel_config.excel_sheet', self.excel_sheet)
        param.set_param('custom_excel_config.excel_filename', self.excel_filename)

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        param = self.env['ir.config_parameter'].sudo()
        res.update(
            excel_sheet=param.get_param('custom_excel_config.excel_sheet'),
            excel_filename=param.get_param('custom_excel_config.excel_filename'),
        )
        return res
