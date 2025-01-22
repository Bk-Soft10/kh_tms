# -*- coding: utf-8 -*-
from odoo import http

# class TmsFullLoad(http.Controller):
#     @http.route('/tms_full_load/tms_full_load/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/tms_full_load/tms_full_load/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('tms_full_load.listing', {
#             'root': '/tms_full_load/tms_full_load',
#             'objects': http.request.env['tms_full_load.tms_full_load'].search([]),
#         })

#     @http.route('/tms_full_load/tms_full_load/objects/<model("tms_full_load.tms_full_load"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('tms_full_load.object', {
#             'object': obj
#         })