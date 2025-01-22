# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import  UserError, ValidationError
import datetime
import time


class tms_full_load(models.Model):
    _name = 'tms.full.load'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Full load Car Receipt"

    def action_print(self):
        return self.env.ref('tms_full_load.account_invoice_report_total').report_action(self)
    def action_post(self):
        for rec in self:
            rec.compute_line_price()
            rec.state="process"

    def action_confirm(self):
        for rec in self:
            object = self.env['tms.receipt']
            rec.name = self.env['ir.sequence'].next_by_code("full.load")
            rec.compute_line_price
            rec.state = "done"
            for line in rec.line_ids:
                if line.price:
                    receipt_id = object.sudo().create({
                        'receipt_date': rec.order_date,
                        'is_comp': True,
                        'move_id': rec.move_id.id,
                        'branch_id': rec.branch_id.id,
                        'city_id': rec.city_id.id,
                        'city_to_id': rec.city_to_id.id,
                        'branch_to_id': rec.branch_to_id.id,
                        'pay_branch_id': rec.pay_branch_id.id,
                        'pay_city_id': rec.pay_city_id.id,
                        'shipping_type': rec.shipping_type,
                        'days_to_arrival': rec.days_to_arrival,
                        'shipper_id': rec.partner_id.id,
                        'c_partner_id': rec.partner_id.id,
                        'partner_id': rec.partner_id.id,
                        'car_id': line.car_id,
                        'base_price': line.price,
                        'color': line.color,
                        'body_no': line.body_no,
                        'brand_id': line.brand_id.id,
                        'model_id': line.model_id.id,
                        'resv1_name': line.resv1_name,
                        'resv1_mobile': line.resv1_mobile,
                        'freight_state': line.freight_state.id,
                        'manual_price': True,




                    })
                    receipt_id.action_confirm_receipt()
                    tax_amount = receipt_id.tax_id._compute_amount(line.price, line.price, partner=rec.partner_id)
                    amount_total = 00
                    amount_total = line.price + tax_amount


                    query = 'UPDATE tms_receipt SET base_price=%s ,receipt_price=%s ,amount_untaxed=%s ,amount_tax=%s,amount_total=%s ,residual=%s WHERE id=%s' % (line.price,line.price,line.price,tax_amount,amount_total,amount_total, receipt_id.id)
                    self._cr.execute(query)
                    line.receipt_id = receipt_id

                else:
                    raise ValidationError('there is line without price')

    name = fields.Char()
    days_to_arrival = fields.Integer(string="After Days", readonly=False, required=True)
    is_comp = fields.Boolean(readonly=True, default=True)
    order_date = fields.Datetime(string="Order Date", default=lambda self: fields.Datetime.now())

    @api.depends('is_comp', 'branch_id')
    def _get_move_domain(self):
        domain = [('branch_id', '=', self.env.user.branch_id.id),
                  ('is_comp', '=', self.is_comp)]
        return domain
    move_id = fields.Many2one('tms.move',domain="[('is_comp','=','True')]", string='Move Id', required=True)

    @api.model
    def _get_branch(self):
        return self.env.user.branch_id

    @api.depends('branch_id')
    @api.model
    def _get_city(self):
        return self.env.user.branch_id.city_id if self.env.user.branch_id else False
    branch_id = fields.Many2one('tms.branch', string='Branch', required=True, readonly=True, index=True,
                                default=_get_branch)
    city_id = fields.Many2one('tms.city', string='City', related='branch_id.city_id', required=True, index=True,
                              readonly=True, store=True, default=_get_city)
    def _get_branch_to_id_domain(self):
        return  [('city_id', '=', self.city_to_id.id)]

    city_to_id = fields.Many2one('tms.city', string='To City', required=True, index=True, change_default=False)
    branch_to_id = fields.Many2one('tms.branch', domain="[('city_id','=',city_to_id)]", index=True, string='To Branch',
                                   required=True, change_default=False)
    total_price = fields.Float(string="Total Price",compute="_get_total",default=0.0)
    def _get_total(self):
        for rec in self:
            freight_state_id = self.env['tms.freight.state'].search([('name','=','حمولة تريلا')]).id
            partner_state_obj = self.env['tms.partner.price.list']
            state_price_record = partner_state_obj.search([('partner_id', '=', rec.partner_id.id),
                                                           ('city_from_id', '=', rec.city_id.id),
                                                           ('city_to_id', '=', rec.city_to_id.id),
                                                           ('freight_state_id', '=', freight_state_id)], limit=1)
            if state_price_record:
                rec.total_price=state_price_record.price
            else:
                rec.total_price =0.0


    @api.depends("city_to_id","branch_to_id")
    def _set_pay_branch_city_id(self):
        for rec in self:
           rec.pay_city_id = rec.city_to_id
           rec.pay_branch_id = rec.branch_to_id


    pay_branch_id = fields.Many2one('tms.branch', string='Payment: Branch', required=True,
                                    compute="_set_pay_branch_city_id")

    pay_city_id = fields.Many2one('tms.city', string='Payment: City', required=True, change_default=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('process', 'Process'),
        ('done', 'Done'),
    ], string='Status', index=True, readonly=True, default='draft',
        track_visibility='onchange', copy=False)
    partner_id = fields.Many2one('res.partner', string='Client',domain="[('is_full_load','=','True')]" ,help="The customer how will charge the car", index=True, required=True, change_default=False)

    shipping_type = fields.Selection([('1', 'Go'), ('2', 'Go And Return'), ('3', 'Return')],
                                      string="Receipt Type", default=1, required=True,
                                     readonly=True, states={'draft': [('readonly', False)]})
    line_ids = fields.One2many("tms.full.load.line", "order_id", string="order id", required=False, )

    @api.constrains('line_ids')
    def _check_sale_lines(self):
        for record in self:
            if len(record.line_ids) > 8:
                raise ValidationError('Not more than 8 lines')
    def compute_line_price(self):
        for rec in self:
            if rec.total_price and rec.line_ids:
                line_price = rec.total_price / len(rec.line_ids)
                if line_price :
                    for line in rec.line_ids:
                        line.price = line_price

class FullLoadLine(models.Model):
    _name = 'tms.full.load.line'
    order_id = fields.Many2one("tms.full.load", string="Order ID")
    receipt_id = fields.Many2one("tms.receipt", string="receipt ID")
    car_id = fields.Char(string="Plate Number", index=True, required=False)
    price = fields.Float(string="Price",default=0.0)
    issue_year = fields.Char(string='Issue Year', help="Car manufacturing year")
    color = fields.Char(string='Color', help='Car color')
    body_no = fields.Char(string='Body Number', help='Car body Number')
    brand_id = fields.Many2one('tms.cbrand', string='Car Brand', required=True)
    model_id = fields.Many2one('tms.cmodel', string='Car Model', required=True)
    resv1_name = fields.Char(string="Recipient", required=True, default='')
    resv1_mobile = fields.Char(string="Recipient Mobile")
    freight_state = fields.Many2one('tms.freight.state', string='Freight State')

class ResPartnerExtended(models.Model):
    _inherit = 'res.partner'

    is_full_load = fields.Boolean(string='Is Full Load',default=False)