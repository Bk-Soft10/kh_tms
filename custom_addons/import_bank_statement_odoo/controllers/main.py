from odoo import http
from odoo.http import request, content_disposition
import base64

class ExcelDownloadController(http.Controller):
    @http.route('/web/binary/download_excel_template', type='http', auth="user")
    def download_excel_template(self, **kw):
        IrConfigParameter = request.env['ir.config_parameter'].sudo()
        excel_sheet = IrConfigParameter.get_param('custom_excel_config.excel_sheet')
        excel_filename = IrConfigParameter.get_param('custom_excel_config.excel_filename')

        if not excel_sheet or not excel_filename:
            return request.not_found()

        excel_data = base64.b64decode(excel_sheet)
        headers = [
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition(excel_filename))
        ]
        return request.make_response(excel_data, headers=headers)
