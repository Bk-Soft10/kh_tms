# -*- coding: utf-8 -*-
# from odoo import http


# class LmHrSettlement(http.Controller):
#     @http.route('/lm_hr_settlement/lm_hr_settlement/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/lm_hr_settlement/lm_hr_settlement/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('lm_hr_settlement.listing', {
#             'root': '/lm_hr_settlement/lm_hr_settlement',
#             'objects': http.request.env['lm_hr_settlement.lm_hr_settlement'].search([]),
#         })

#     @http.route('/lm_hr_settlement/lm_hr_settlement/objects/<model("lm_hr_settlement.lm_hr_settlement"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('lm_hr_settlement.object', {
#             'object': obj
#         })
