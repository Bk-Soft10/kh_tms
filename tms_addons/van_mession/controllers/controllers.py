# -*- coding: utf-8 -*-
# from odoo import http


# class VanMession(http.Controller):
#     @http.route('/van_mession/van_mession', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/van_mession/van_mession/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('van_mession.listing', {
#             'root': '/van_mession/van_mession',
#             'objects': http.request.env['van_mession.van_mession'].search([]),
#         })

#     @http.route('/van_mession/van_mession/objects/<model("van_mession.van_mession"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('van_mession.object', {
#             'object': obj
#         })
