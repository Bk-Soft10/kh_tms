# -*- coding: utf-8 -*-
# from odoo import http


# class ReportsTemplateCustom(http.Controller):
#     @http.route('/reports_template_custom/reports_template_custom', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/reports_template_custom/reports_template_custom/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('reports_template_custom.listing', {
#             'root': '/reports_template_custom/reports_template_custom',
#             'objects': http.request.env['reports_template_custom.reports_template_custom'].search([]),
#         })

#     @http.route('/reports_template_custom/reports_template_custom/objects/<model("reports_template_custom.reports_template_custom"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('reports_template_custom.object', {
#             'object': obj
#         })
