# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class van_mession(models.Model):
    _name = 'van.mession'
    _description = 'van_mession.van_mession'

    name = fields.Char()
    date = fields.Date(default=fields.date.today())
    user_id = fields.Many2one('res.users')
    state = fields.Selection([
        ('new','New'),
        ('in_progress', 'In Progress'),
        ('finish', 'Finish'),
        ('done','Done')
    ],default='new')

    lines = fields.One2many('van.mession.line','mession_id')

    order_ids = fields.One2many('sale.order','mession_id')
    can_create = fields.Boolean(compute='compute_can_create',store=True)

    def compute_can_create(self):
        for rec in self:
            rec.can_create = False
            for line in rec.lines:
                if line.check_anailable_qty() > 0 and rec.state == 'in_progress':
                    rec.can_create = True
    def confirm(self):
        if self.state == 'new':
            self.state = 'in_progress'
    def finish(self):
        if self.state == 'in_progress':
            self.state = 'finish'
    def close_mission(self):
        remain = []
        for rec in self.lines:
            if rec.qty - rec.sold_qty - rec.return_qty > 0:
                remain.append((0,0,{'product_id': rec.product_id.id , 'product_uom_qty': rec.qty - rec.sold_qty - rec.return_qty}))


        order = self.env['sale.order'].create({
            'partner_id': self.user_id.partner_id.id,'order_line' : remain
        })
        print(remain)
        # self.state = 'done'




        pass
    

    def create_sale_order(self):
        order_line = []
        for line in self.lines:
            if line.check_anailable_qty() > 0:
                order_line.append((0,0,{
                    'product_id' : line.product_id.id,
                    # 'customer_lead' : 0,
                    'qty' : line.qty - line.sold_qty or 1 ,
                    # 'product_uom_qty' : line.qty,
                    # 'company_id' : self.env.company.id,
                    # 'price_unit' : line.product_id.list_price or 0
                }))
        if order_line:
            return {
                'name': ('Create Order'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'van.mession.order',
                'target' : 'new',
                'context' : {'default_lines' : order_line },
                'view_id': False,
                'type': 'ir.actions.act_window',
            }
        else :
            raise UserError("you dont have stock")
        pass

class SaleOrderInh(models.Model):
    _inherit = 'sale.order'
    mession_id = fields.Many2one('van.mession')

class van_mession(models.Model):
    _name = 'van.mession.line'
    _description = 'van_mession.van_mession'
    _rec_name = 'product_id'
    product_id = fields.Many2one('product.product')
    qty = fields.Float()
    sold_qty = fields.Float(compute='compute_sold_qty')
    return_qty = fields.Float()
    mession_id = fields.Many2one('van.mession')
    def check_anailable_qty(self):
        return self.qty - self.sold_qty
    @api.onchange('qty')
    def onchange_qty(self):
        if self.mession_id.state != 'new':
            raise UserError("connot Change qty")
    def compute_sold_qty(self):
        for rec in self:
            sold_qty = 0
            for order in rec.mession_id.order_ids:
                if order.state == 'sale':
                    for line in order.order_line:
                        if line.product_id.id == rec.product_id.id:
                            sold_qty+=line.qty_delivered
            rec.sold_qty = sold_qty

#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100
