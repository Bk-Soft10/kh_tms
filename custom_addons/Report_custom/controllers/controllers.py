# -*- coding: utf-8 -*-
# from odoo import http


# class FleetCustom(http.Controller):
#     @http.route('/fleet_custom/fleet_custom', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/fleet_custom/fleet_custom/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('fleet_custom.listing', {
#             'root': '/fleet_custom/fleet_custom',
#             'objects': http.request.env['fleet_custom.fleet_custom'].search([]),
#         })

#     @http.route('/fleet_custom/fleet_custom/objects/<model("fleet_custom.fleet_custom"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('fleet_custom.object', {
#             'object': obj
#         })
