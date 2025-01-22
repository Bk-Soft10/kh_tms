# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VanMissionOrder(models.TransientModel):
    _name = 'van.mession.order'
    _description = 'Create Order'
    # _check_company_auto = True

    customer_id = fields.Many2one('res.partner')
    partner_id = fields.Many2one('res.partner')

    lines = fields.One2many('van.mession.order.line' ,'order_id')
    def submit(self):
        order_line = []
        for line in self.lines:
            order_line.append((0,0,{
                # 'product_template_id' : line.product_id.product_tmpl_id.id,
                'product_id' : line.product_id.id,
                # 'customer_lead' : 0,
                # 'name' : line.product_id.name,
                'product_uom_qty' : line.qty,
                # 'company_id' : self.env.company.id,
                # 'price_unit' : line.product_id.list_price or 0
            }))
        mession = self.env.context.get('active_id')
    	
        order = self.env['sale.order'].create({'partner_id': self.customer_id.id,'order_line': order_line,'mession_id': mession})
        
        print(order_line)
        return{
             'name': ('Create Order'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sale.order',
            'res_id': order.id,
            # 'context' : {'default_partner_id' : 4,'default_order_line': order_line},
            'view_id': False,
            'type': 'ir.actions.act_window',
        }
class VanMissionOrderLine(models.TransientModel):
    _name = 'van.mession.order.line'
    _description = 'Create Order'

    product_id = fields.Many2one('product.product')
    qty = fields.Float()
    order_id = fields.Many2one('van.mession.order')
