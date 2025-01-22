from werkzeug.urls import url_encode

from odoo import api, exceptions, fields, models, _
from odoo.osv import expression
import datetime
import json
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError
from odoo.tools import float_is_zero, float_compare, pycompat
from odoo.addons import decimal_precision as dp
import logging

from . import common
from asyncore import write
from ..sms import sender,account,sms,utilities
from odoo.http import request

_logger = logging.getLogger(__name__)

BLOCKED_FIELDS = ['discount', 'discount_amount', 'car_type_price', 'add_price', 'car_type', 'receipt_price', 'base_price',
                   'manual_price', 'amount_untaxed', 'amount_tax', 'amount_total', 'return_price', 'go_price']

class Receipt(models.Model):
    _name = 'tms.receipt'

    _inherit = ['portal.mixin', 'mail.thread.main.attachment', 'mail.activity.mixin', 'sequence.mixin']

    # _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Car Receipt"
    _order = "receipt_date desc, receipt_no desc, id desc"
    
    @api.model
    def _get_branch(self):
        return self.env.user.branch_id 
    
    @api.depends('branch_id')
    @api.model
    def _get_city(self):
        return self.env.user.branch_id.city_id if  self.env.user.branch_id else False
    
    @api.depends('is_comp', 'branch_id')
    def _get_move_domain(self):
        domain = [('branch_id', '=', self.env.user.branch_id.id), 
                  ('is_comp', '=', self.is_comp or self._context.get('is_comp', True))]
        
        if not self.env.user.has_group('tms.group_tms_admin') :
            domain.append(('is_manual', '=', False))
        
        return domain
    
    @api.depends('city_to_id')
    def _get_current_city(self):
        return self.cur_branch_id.city_id if self.cur_branch_id else False
    
    def _comput_arrival(self):
        for rec in self:
            return rec.receipt_date + datetime.timedelta(days=rec.days_to_arrival) if rec.days_to_arrival and rec.receipt_date else False
    
    def _get_pay_branch_domain(self):
        #return   [('city_id', '=', self.pay_city_id.id if self.pay_city_id else 0)]
        return   []
    @api.model
    def _default_currency(self):
        return  self.env.user.company_id.currency_id
    
    def _default_currency_used(self):
        return self.currency_id if self.currency_id else self._default_currency()
    
    def _is_comp(self):
        if 'is_comp' not in self._context and self.id:
            query = "SELECT is_comp FROM 'tms_receipt' WHERE id=%s"
            self._cr.execute(query, self.id)
            is_comp_r = self._cr.fetchone()
            if is_comp_r:
                self._context.update({'is_comp':  is_comp_r[0]})
        
        return self._context.get('is_comp', True)
    
    @api.depends('is_comp')
    def _get_itrans_context(self):
        is_comp = self.is_comp or self._is_comp()
        return {'is_comp': is_comp}
    
    def get_car_model_domain(self):
        if self.brand_id:
            model_ids =  self.brand_id.mapped('model_ids.id')
            return [('id', 'in', model_ids)]
    
    receipt_no = fields.Char(string="Receipt No", readonly=True, copy=False, index=True)
    
    name = fields.Char(string="Display Name", copy=False, index=True)
    
    is_comp = fields.Boolean(readonly=True, default=_is_comp, tracking=True, help="This field set the receipt type is for customers of type company")
    
    branch_id = fields.Many2one('tms.branch', string='Branch', required=True, readonly=True, index=True, default=_get_branch)
    city_id = fields.Many2one('tms.city', string='City', related='branch_id.city_id', required=True, index=True, readonly=True, store=True, default=_get_city)
    move_id = fields.Many2one('tms.move', string='Move Id', required=True, domain=_get_move_domain, ondelete='restrict')
    
    city_to_id = fields.Many2one('tms.city', string='To City', required=True, index=True, change_default=False)
    branch_to_id = fields.Many2one('tms.branch', index=True, string='To Branch',
                                    required=True, change_default=False)

    # branch_to_id = fields.Many2one('tms.branch', releated="city_to_id.branch_ids", index=True, string='To Branch',
    #                                 required=True, change_default=False)
    
    pay_branch_id = fields.Many2one('tms.branch', string='Payment: Branch', required=True, domain=_get_pay_branch_domain)
    
    pay_city_id = fields.Many2one('tms.city', string='Payment: City', required=True, change_default=False)
    

    state = fields.Selection([
            ('d','Draft'),
            ('b', 'In Branch'),
            ('r', 'In Road'),
            ('t', 'Transient'),
            ('a', 'Arrival'),
            ('e', 'Closed'),
            ('c', 'Cancelled'),
        ], string='Status', index=True, readonly=True, default='d',
        tracking=True, copy=False)
    
    
    shipping_type = fields.Selection([('1', 'Go'),('2', 'Go And Return'), ('3', 'Return')],
                                       string="Receipt Type", default="1", required=True,)
                                      
    
    sent = fields.Boolean(default=False, copy=False)
        
    receipt_date = fields.Datetime(string='Receipt Date', index=True, default=lambda self: fields.Datetime.now())
    date = fields.Date(compute='_compute_date', index=True, store=True)
    due_date = fields.Date("Due Date", compute='_compute_due_date', store=True, readonly=True)
    days_to_arrival = fields.Integer(string = "After Days", required=True)
    
    expected_arrival = fields.Date(string='Expected ِ arrival', store=True, compute=_comput_arrival)
    
    arrival_date = fields.Datetime(string='Arrival Date', readonly=True)
    
    car_id = fields.Char(help='Car plate number or customs card number', index=True, required=True, tracking=True)
    is_card = fields.Boolean("Customs Card", help='Select if the car have customs card number', default=False)
    issue_year = fields.Char(string='Issue Year', help="Car manufacturing year")
    color = fields.Char(string='Color', help='Car color')
    body_no = fields.Char(string='Body Number', help='Car body Number')
    
    
    brand_id = fields.Many2one('tms.cbrand', string='Car Brand', required=True, change_default=False)
    model_id = fields.Many2one('tms.cmodel', string='Car Model', required=True,  change_default=False, domain="[('brand_id','=',brand_id)]")
    
    cur_branch_id = fields.Many2one('tms.branch', string='Current Branch', index=True, help='Current branch car stay in', required=True, readonly=True, default=_get_branch)
    cur_city_id = fields.Many2one('tms.city', string='Current City', related='cur_branch_id.city_id', help='City of current branch car stay in',  readonly=True)
    
    posted_date = fields.Datetime(string='Posted Date', readonly=True)
    exit_date = fields.Datetime(string='Exit Date', readonly=True)
    
    exit_no = fields.Char(string='Exit Number', help="The exit receipt number", readonly=True)
    
    partner_id = fields.Many2one('res.partner', string='Client', help="The customer how will charge the car", index=True, required=True, change_default=False)
    partner__id = fields.Many2one('res.partner', string='Client', help="The customer how will charge the car")
    c_partner_id = fields.Many2one('res.partner', string='Client', help="The customer how will charge the car", required=True, change_default=False)
    responsible_id = fields.Many2one('res.partner', string='Responsible', help="The person under the company how will charge the car")
    
    shipper_id = fields.Many2one('res.partner', string='Shipping company', help="The customer how will charge the car", domain=[('is_company', '=', True)])
    
    shipper_mobile = fields.Char(related='shipper_id.mobile', store=False)
        
    cancel_no = fields.Char(string="Cancel No", readonly=True)
    cancel_date = fields.Datetime(string="Cancel Date")
    cancel_by = fields.Many2one('res.users', string='Cancelled By')
    
    
    comment = fields.Text('Additional Information', tracking=True)
        
    receipt_trip_ids =  fields.One2many('tms.receipt.route', 'receipt_id', readonly=True)
    
    itrans_ids = fields.One2many('tms.itrans', 'receipt_id', copy=False)
    
    go_receipt_id = fields.Many2one('tms.receipt', string="Target Receipt", help="Number of Receipt when the current shape type is return", copy=False,)
    
    used_in_id = fields.Many2one('tms.receipt', string="Return Receipt", help="Number of Receipt when current shape type is return", copy=False, readonly=1)
    
    
    same_sender = fields.Boolean(string="Same Sender", default=False)
    
    resv1_name = fields.Char(string="Recipient", required=True, default='')
    resv1_id = fields.Char(string="Recipient ID", index=True)
    resv1_mobile = fields.Char(string="Recipient Mobile", tracking=True)
    resv1_country = fields.Char(string="Recipient Country")
    
    resv2_name = fields.Char(string="Actual Recipient", readonly=True)
    resv2_id = fields.Char(string="Actual Recipient ID", index=True, readonly=True)
    resv2_mobile = fields.Char(string="Actual Recipient Mobile", readonly=True)
    resv2_country = fields.Char(string="Actual Recipient Country", readonly=True)
    
    sender_ssn = fields.Char(related='partner_id.ssn', store=False, readonly=True)
    sender_mobile = fields.Char(related='partner_id.mobile', store=False, readonly=True)
    sender_country = fields.Many2one('res.country', related='partner_id.country_id', store=False, readonly=True)    
    
    trip_id = fields.Many2one('tms.trip', readonly=True, tracking=True) 
    
    company_id = fields.Many2one('res.company', string='Company', change_default=True,
        required=True,
        default=lambda self: self.env['res.company']._company_default_get('account.invoice'))
    
    currency_id = fields.Many2one('res.currency', default=_default_currency, string="Company Currency", readonly=True)
    
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Company Currency", readonly=True)
    
    branch_name = fields.Char(related='branch_id.name', readonly=True)
    
    contract_no = fields.Char(string="Contract No")
    
    can_edit = fields.Boolean(compute='_can_edit')
    
    use_contract = fields.Boolean(compute='_need_contract')
    
    old_receipt_no = fields.Char(string='Old Receipt No')
    
    city_to_manual = fields.Boolean(compute='_is_city_to_manual')
    
    partner_deal = fields.Many2one('tms.partner.price.list', readonly=True)
    
    amove_id = fields.Many2one("account.move", "Journal Entry", readonly=True, copy=False, ondelete='set null')
    invoice_id = fields.Many2one('account.move', readonly=True, copy=False, ondelete='set null')
    can_downoad = fields.Boolean(compute='_can_downoad')
    down_date = fields.Datetime(readonly=True)


    _sql_constraints = [('receipt_used_in_id_unique', 'unique(used_in_id)', 'The receipt has already been used')]
    
    
    
    def _can_edit(self):
        pass
    
    @api.depends('c_partner_id')
    
    def _need_contract(self):
        self.use_contract = self.c_partner_id and self.c_partner_id.is_company and self.c_partner_id.use_contract
    
    
    @api.depends('city_to_id')
    def _is_city_to_manual(self):
        self.city_to_manual = self.city_to_id.manual_price if self.city_to_id else False
        pass
    
    def get_receipt_data(self, r):
        return {'city_to_id': r.city_id, 'branch_to_id': r.branch_id,
                'pay_city_id': r.pay_city_id, 'pay_branch_id': r.pay_branch_id,
                'car_id': r.car_id, 'brand_id': r.brand_id, 'model_id': r.model_id,
                'partner_id': r.partner_id,'c_partner_id': r.c_partner_id,
                'is_card': r.is_card,'issue_year':r.issue_year, 'color': r.color,
                'body_no':r.body_no, 'resv1_name': r.resv1_name, 'resv1_mobile': r.resv1_mobile}
    
    @api.onchange('go_receipt_id')
    def _go_receipt_changed(self):
        vals = self.get_receipt_data(self.go_receipt_id) if self.go_receipt_id else {}
        vals.update({'city_id': self.cur_branch_id.city_id, 'branch_id': self.cur_branch_id})
        return {'value': vals}
    
    @api.onchange('branch_id')
    def _branch_changed(self):
        ret = {}
        mdomain = []
        self.branch_id = self.cur_branch_id
        if self.branch_id:
            mdomain = [('branch_id', '=', self.branch_id.id), ('is_comp', '=', self.is_comp)]
            if not self.env.user.has_group('tms.group_tms_admin') :
                mdomain.append(('is_manual', '=', False))
            
            move_id = self.env['tms.move'].search(mdomain, limit=1)
            if move_id:
                ret = {'value': {'move_id': move_id}}
            
        domain = {'move_id': mdomain}        
        if not self.is_comp:
            domain.update({'go_receipt_id': [('shipping_type', '=', '2'),
                                         ('city_to_id', '=', self.branch_id.city_id.id),
                                          ('used_in_id', '=', False), ('return_cancelled', '=', False)]})
            
        
            
        ret['domain'] = domain
        
        return ret
    
    @api.depends('branch_to_id', 'city_to_id.branch_ids')
    @api.onchange('city_to_id')
    def _city_to_changed(self):
        
        domain = {'branch_to_id': [('id', '=', -1)], 'pay_branch_id': [('id', '=', -1)]}
        has_city = False
        first_branch_id = False
        
        branch_to =  self.branch_to_id if self._context.get('copy') else False
        
        if self.city_to_id:
            ids = self.city_to_id.branch_ids.mapped('id')
            domain['branch_to_id'] = [('id', 'in', ids)]
            has_city = True if len(ids) > 0 else False
            first_branch_id = ids[0] if len(ids) == 1 else False
        
        if self.pay_city_id:
            domain['pay_branch_id'] = [('city_id', '=', self.pay_city_id.id)]
        
        
        res = {'domain': domain}
        
        if not has_city :
            res['value'] = {'branch_to_id' : False, 'cur_city_id' : False}
        else:
            res['value'] = {'cur_city_id' : self.city_to_id, 'branch_to_id': False}
            if first_branch_id:
                branch_id = self.env['tms.branch'].browse(first_branch_id)[0]
                res['value']['branch_to_id'] = branch_id
        
        if self.city_to_id:
            res['value']['city_to_manual'] = self.city_to_id.manual_price if self.city_to_id else False
          
        if self.c_partner_id and self.is_comp:
            ret = self._c_partner_changed()
            res['value'].update(ret['value'])
            _logger.info("------------"+str(ret))
            res['domain'].update(ret.get('domain',''))
        if branch_to and  branch_to.city_id == self.city_id:
                res['value'].update({'branch_to_id':branch_to, 
                    'pay_branch_id' : branch_to, 'pay_city_id' : self.city_id,
                    'cur_city_id' : self.city_to_id, 'branch_to_id': branch_to})
        
        return res
    
    @api.onchange('branch_to_id')
    def _branch_to_changed(self):
        self.pay_branch_id = self.branch_to_id
        return {'value': {'pay_branch_id' : self.branch_to_id, 'pay_city_id' : self.branch_to_id.city_id}}
    
    @api.onchange('pay_city_id')
    def _pay_city_changed(self):
        if self.pay_city_id:
            pay_branch_id = self.pay_branch_id if self._context.get('copy') else False
            if self.city_to_id.id == self.pay_city_id.id:
                pay_branch_id = self.branch_to_id
            elif len(self.pay_city_id.branch_ids) == 1:
                pay_branch_id = self.pay_city_id.branch_ids[0]
            return {'value': {'pay_branch_id': pay_branch_id}}
        return {'value': {'pay_branch_id': False}}
    
           # return {'domain' : {'pay_branch_id': [('city_id', '=', self.pay_city_id.id)]}, 'value': {'pay_branch_id': pay_branch_id}}
        #return {'domain' : {'pay_branch_id': [('id', '=', 0)]}, 'value': {'pay_branch_id': False}}
    
    
    @api.onchange('partner_id')
    def _partner_changed(self):
        try:
            self.check_partner(self.partner_id)
        except (ValidationError) as e:
            self.partner_id = self._origin.partner_id
            raise e
        
        value = {'c_partner_id': self.partner_id, 'recipient_id': self.partner_id}
        return {'value': value}
    
    @api.onchange('c_partner_id')
    def _c_partner_changed(self):
        
        try:
            self.check_partner(self.c_partner_id)
        except (ValidationError) as e:
            self.c_partner_id = self._origin.c_partner_id
            raise e
        
        domain = {'freight_state': []}
        value = {'partner_id': self.c_partner_id, 'recipient_id': self.c_partner_id, 'shipper_id': self.c_partner_id,
                  'use_contract':  self.c_partner_id.use_contract if self.is_comp and self.c_partner_id else False,
                  'freight_state': False  }
        if self.c_partner_id:
            p = self.env['res.partner'].search([('parent_id', '=', self.c_partner_id.id)], limit=1)
            if p:
                value['responsible_id'] = p
            
            city_id = self.city_id.id if self.city_id else 0
            city_to_id = self.city_to_id.id if self.city_to_id else 0
                        
            if self.is_comp:
                state_ids = set()
                self._cr.execute("""SELECT DISTINCT freight_state_id as id, price from tms_partner_price_list
                                     WHERE ((city_from_id=%s AND city_to_id=%s)
                                           OR (city_to_id=%s AND city_from_id=%s))
                                       AND partner_id=%s AND (deal=-1 OR deal_used>0)""",
                      (city_id, city_to_id, city_id, city_to_id,self.c_partner_id.id))
                sqlresult = self._cr.fetchall()
                for (id,price) in sqlresult:
                    state_ids.add(id)
                    p = price
                    _logger.info("---------------"+str(domain))
                
                if len(state_ids):
                    state_ids = list(state_ids)
                    domain['freight_state'] = [('id', 'in', state_ids)]
                    value['freight_state'] = state_ids[0]
                    value['base_price'] = p
                    # value['freight_state'] = self.env['tms.freight.state'].browse(state_ids[0])[0].name_get() if len(state_ids) == 1 else False
                else:
                    # domain['freight_state'] = [('id', '=', 0)]
                    value['freight_state'] = False
                if self._context.get('copy') and self.freight_state and self.freight_state.id in state_ids:
                    del value['freight_state']
            
        # domain['freight_state'] = []
        _logger.info("---------------"+str(domain))
        # return {'value': value, 'domain': domain}
        return {'value': value }


    @api.onchange('is_card')
    def _is_card_changed(self):
        return {'value': {'car_id': False}}

        
    @api.onchange('car_id')
    def _car_changed(self):
        value = {}
        if self.car_id and not self.go_receipt_id:
            receipt = self.search([('car_id', '=', self.car_id)], limit=1)
            if receipt:
                if receipt.id != self.id and  receipt.state not in ['c', 'e']: #state closed
                    return { 'warning' : {
                        'title': _("Warning for car %s") % self.car_id,
                        'message': _("This car already exists in the system")
                        }, 'value': {'car_id': False}}
                else:
                    value['issue_year'] = receipt.issue_year
                    value['color'] = receipt.color
                    value['body_no'] = receipt.body_no
                    value['brand_id'] = receipt.brand_id
                    value['model_id'] = receipt.model_id
            
        
        return {'value': value}
    
    
            #  [('brand_id', '=', self.brand_id.id)]
    @api.onchange('brand_id')
    def _cbrand_changed(self):
        res = {'value' : {'model_id' : False}, 'domain': {'model_id' : [('brand_id', '=', -1)]}}
        if self.model_id and self.model_id.id in self.brand_id.mapped('model_ids.id'):
                del res['value']['model_id']
        res['domain']['model_id'] = self.get_car_model_domain()
        print("res")
        print(res)
        print(res)
        # res.pop('domain')
        print(res)
        print(res)
        print(res)
        print(res)
        print(res)
        print(res)
        return res
    
    
    @api.depends('partner_id')
    @api.onchange('same_sender')
    def _same_sender_changed(self):
         
        res = {'value' : {'model_id' : False}, 'domain': {'model_id' : [('brand_id', '=', -1)]}}
        if self.same_sender:
            partner = self.partner_id or self.c_partner_id
            if not partner:
                return {'warning' : {'message':  _("Please select the client/sender first")}}
            
            return {'value': {'resv1_name': partner.name, 'resv1_id': partner.ssn, 'resv1_mobile': partner.mobile , 'resv1_country': partner.country_id.name if partner.country_id else False}}

        return {'value': {'resv1_name': False, 'resv1_id': False, 'resv1_mobile': False, 'resv1_country': False}}
    
    @api.onchange('days_to_arrival', 'receipt_date')
    def _days_to_arrival_changed(self):
        res = {'value' : {'expected_arrival' : False}, 'domain':{}}
        
        
        
        if self.days_to_arrival and self.receipt_date:
            res['value']['expected_arrival'] = fields.Date.to_string( fields.Date.from_string(self.receipt_date) + 
            datetime.timedelta(days=self.days_to_arrival) )
       
        return res
 
    @api.depends('receipt_date')
    def _compute_date(self):
        for r in self:
            r.date = common.timestamp_company_date_st(self, r.receipt_date or fields.Datetime.now())
 
    @api.depends('partner_id', 'date')
    def _compute_due_date(self):
        
        for r in self:
            pterm = r.partner_id.property_payment_term_id
            if pterm:
                pterm_list = pterm.with_context(currency_id=r.currency_id.id).compute(value=1, date_ref=r.date)[0]
                r.due_date = max(line[0] for line in pterm_list)
            elif r.due_date and (r.date > r.due_date):
                r.due_date = r.date
                
 
    def check_partner(self, partner):
        
        if not partner:
            return
        
        if isinstance(partner, int) :
            partner = self.env['res.partner'].browse(partner)
        
        if partner.is_blocked and self.state == 'd':
            raise ValidationError(_('This customer is blocked!'))
        
    @api.model
    def create(self, vals):
        
        #if True:
        #    raise ValidationError(_('receipt_date: (%s)') % vals.get('receipt_date'))
        
        if not self.env.user.has_group('tms.group_tms_receipt_date') or not vals.get('receipt_date', False) :
            vals.update({'receipt_date': fields.Datetime.now()})
        
        #move_id = self.env['tms.move'].browse(vals.get('move_id'))
        if not vals.get('is_comp'):
            if self._context.get('is_comp'):
                vals['is_comp'] = True
            else:
                vals['is_comp'] = False
        
        move_id = self.env['tms.move'].browse(vals['move_id'])
        
        branch_id = move_id.branch_id
        city_id = branch_id.city_id
        
        
        vals['is_comp'] = move_id.is_comp
        
        vals['tax_id'] = branch_id.tax_id.id
            
        if not vals.get('is_card'):
            common.tms_check_plate_number(vals['car_id'])
        
        new_vals = self._price_state_type_change(validate=True, vals=vals)
        
        if 'warning' in new_vals:
            raise UserError(new_vals['warning']['message'])
        
        if new_vals and new_vals.get('value'):
            vals.update(new_vals.get('value'))
        
        if 'valid_price' in vals and not vals['valid_price']:
            raise ValidationError(_('Please configure the city price list!'))
        
        
        if vals['days_to_arrival'] <= 0:
            raise ValidationError(_('Enter valid days to arrive'))
        
        receipt_no = self.env.user.company_id.sec_id.sudo()._next()
        code = receipt_no[:4]
        prefix = str(int(receipt_no[4:]))
        name = code + '-' + prefix
        
        vals.update({'receipt_no':receipt_no, 'name': name, 'branch_id': branch_id.id,
                      'city_id': city_id.id, 'cur_branch_id': branch_id.id,
                      'cur_city_id': city_id.id})
        
        if not vals.get('pay_branch_id'):
            vals.update({'pay_branch_id':vals.get('branch_id'), 'pay_city_id':vals.get('city_id')})
        
        
        receipt_id = None
        # _logger./info()
        if 'shipping_type' in vals:

            if not vals['is_comp'] and vals['shipping_type'] == '3' :
                if not ('go_receipt_id' in vals) or not vals['go_receipt_id']:
                    raise ValidationError(_('Please insert valid original receipt!'))
                receipt_id = self.browse(vals['go_receipt_id'])[0]
                if not receipt_id:
                    raise ValidationError(_('The return receipt has already been used '))
                receipt_date = fields.Datetime.from_string(receipt_id.receipt_date) + datetime.timedelta(days=365)    
                    
                if receipt_date <  datetime.datetime.now():
                    raise ValidationError(_('It has been more than a year since you entered the receipt '))
                
                if receipt_id.used_in_id:
                    raise ValidationError(_('The receipt has already been used'))
            
            #get_receipt_data
        if 'car_id' in vals and not vals['car_id']:    
            receipt = self.search([('car_id', '=', vals['car_id']), ('state', 'not in', ['e', 'c'])], limit=1)
            if receipt:
                raise ValidationError(_("This car (%s) already exists in the system") % (vals['car_id'],))
        
        
        if self._context.get("edit") and 'manual_price' in vals and vals['manual_price'] > 3000 and not self.env.user.has_group("tms.group_tms_change_receipt_price"):
            raise UserError(_("You need extra permission for the price more than 3,000 \nPlease contact the system support!"))    
        
        #if 'car_id' in vals:
        #self._validate_vals(vals)  
        
        if receipt_id:
            vals['amount_untaxed'] = self._get_return_price(receipt_id)
        
        #_logger.info("------check vals: %s", vals)       
        result = super(Receipt, self).create(vals)
        
        result.check_partner(result.partner_id)
        
        if result.move_id.is_comp !=  result.is_comp:
            super(Receipt, self).write({'is_comp': result.move_id.is_comp})
        
        if  result.receipt_price == 0.0 :
            super(Receipt, self).write({'receipt_price': result.amount_untaxed - result.add_price})
        
        if result.partner_deal and result.partner_deal.deal > -1 :
            if result.partner_deal.deal_used - result.partner_deal.deal > 0:
                pass
        
        if receipt_id:
            receipt_id.sudo().write({'used_in_id': result.id})
        """
        if result.is_comp and result.partner_deal.deal != -1:
            partner_deal = result.partner_deal
            if partner_deal.deal_used - 1 <= 0:
                raise ValidationError(_("The deal for this client is not available or finished"))
            partner_deal.sudo().write({'deal_used': partner_deal.deal_used - 1})
        """
        return result
    
    @api.model
    def super_create(self, vals):
        return super(Receipt, self).create(vals)
    
    
    
    def write(self, vals):
        receipt_id = None
        used_receipt_id = None
        cur_branch_id = None
               
        if 'amove_id' in vals:
            return super(Receipt, self).write(vals)
        
        if 'is_comp' in vals:
            del vals['is_comp']
        
        
        if 'partner_id' in vals:
            if not vals['partner_id']:
                raise ValidationError(_('Please set partner id correctly'))
            
        self[0].check_partner(vals['partner_id'] if 'partner_id' in vals else self[0].partner_id)
        
        if 'cur_branch_id' in vals and 'cur_city_id' not in vals:
            if vals.get('cur_branch_id'):
                cur_branch_id = self.env['tms.branch'].browse(vals['cur_branch_id'])[0]
                vals['cur_city_id'] = cur_branch_id.city_id.id
        
        car_id = vals['car_id'] if 'car_id' in vals else None
        is_card = False
        if car_id:
            is_card = vals['is_card'] if 'is_card' in vals else self[0].is_card 
            
        if car_id and not is_card :
            common.tms_check_plate_number(vals['car_id'])    
        
        if 'valid_price' in vals and not vals['valid_price']:
            raise ValidationError(_('Please configure the city price list!'))
        
        partner_deal = False
        for receipt in self:
            partner_deal = receipt.partner_deal            
            if 'pay_branch_id' in vals and not vals['pay_branch_id']:
                vals['pay_branch_id'] = receipt.branch_to_id
                vals['pay_city_id'] = receipt.city_to_id
            
            if not receipt.is_comp and 'shipping_type' in vals and vals['shipping_type'] == '3' and not receipt_id:
                go_receipt_id_id = ('go_receipt_id' in vals and vals['go_receipt_id'])
                if not go_receipt_id_id:
                    raise ValidationError(_('The enter the go and return receipt'))
                receipt_id = self.browse(go_receipt_id_id)[0]
                
                if not receipt_id: 
                    raise ValidationError(_('No receipt selected for go and return'))
                receipt_date = fields.Datetime.from_string(receipt_id.receipt_date) + datetime.timedelta(years=1)    
                
                if receipt_date >  fields.Datetime.now():
                    raise ValidationError(_('It has been more than a year since you entered the receipt ')) 
                
                if receipt_id.used_in_id and receipt_id.used_in_id != receipt.id:
                    raise ValidationError(_('The return receipt has already been used ')) 
                used_receipt_id = receipt
                
        if 'partner_deal'in vals and partner_deal:
            partner_deal.sudo().write({'deal_used': partner_deal.deal_used + 1})
                    
        if 'receipt_date' in vals and not vals['receipt_date']:
            del vals['receipt_date']
            
        if 'car_id' in vals and not vals['car_id']:
            r = self.search([('car_id', '=', vals['car_id']), ('state', 'not in', ['e', 'c'])], limit=1)
            if r and r.id != receipt.id :
                raise ValidationError(_("This car (%s) already exists in the system")%(vals['car_id'],))
        
        if 'is_comp' in vals:
            del vals['is_comp']
            
        if self._context.get("edit") and 'manual_price' in vals and vals['manual_price'] > 3000 and not self.env.user.has_group("tms.group_tms_change_receipt_price"):
            raise UserError(_("You need extra permission for the price more than 3,000 \nPlease contact the system support!"))    
                            
        result = super(Receipt, self).write(vals)
        
        resave = False
        
        for receipt in self:
            resave = receipt._validate_vals(vals)
            if not resave:
                break
            
        if resave:
            for name in vals.copy():
                if name in self._fields:
                    field = self._fields[name]
                    if field.type in ('one2many', 'many2many') :
                        vals.pop(name)
            
            if 'is_comp' in vals:
                del vals['is_comp']  
            result = super(Receipt, self).write(vals)
        
        #if 'discount' in vals and vals['discount'] > self.env.user.max_discount:
        #    raise ValidationError( _('You can only set max discount to (%s) %s' % (str(self.env.user.max_discount), '%')))
        
        
        if receipt_id:
            receipt_id.sudo().write({'used_in_id': used_receipt_id.id})
            
        if 'state' in vals and (vals['state'] == 'b' or self.state=='d'):
            if 'receipt_no' not in vals:
                self.recreate_receipt_no()
                
             
        
        """
        if 'partner_deal'in vals:
            partner_deal = self[0].partner_deal
            if partner_deal.deal_used - 1 <= 0:
                raise ValidationError(_("The deal for this client is not available or finished"))
            partner_deal.sudo().write({'deal_used': partner_deal.deal_used - 1})
        """    
        return result   

    

    
    def unlink(self):
        for receipt in self:
            if receipt.state != 'd':
                raise UserError(_('You can only delete receipt if its in draft state.'))
            if receipt.go_receipt_id:
                receipt_id = self.env['tms.receipt'].search([('id', '=', receipt.go_receipt_id)], limit=1)
                if receipt_id:
                    receipt_id.write({'used_in_id': False})
        return super(Receipt, self).unlink()            
     
    
    def super_write(self,vals):
        if 'is_comp' in vals:
            del vals['is_comp']
        super(Receipt, self).write(vals)
    
    
    
    # def _write(self, vals):
    #     clear_cash = False
    #     for r in self:
    #         if r.amove_id or 'amove_id' in vals:
    #             for f in BLOCKED_FIELDS:
    #                 if f in vals:
    #                     vals.pop(f)
    #                     clear_cash = True
    #             break
    #         elif r.state != 'd' and not self.env.user.has_group("tms.group_tms_change_receipt_price") or \
    #              not self._context.get('edit'):
    #             for f in BLOCKED_FIELDS:
    #                 vals = dict(vals)
    #                 if f in vals:
    #                     _logger.info("___________________________"+str(vals))
    #                     _logger.info("___________________________"+str(type(vals)))
    #                     _logger.info("___________________________"+str(f))

    #                     vals.pop(f)
    #                     clear_cash = True
    #             break
    #     ret = True  
    #     if vals:
    #         ret = super(Receipt, self)._write(vals)

    #     return ret
    
    
        
    def _validate_vals(self, vals): 
        
        if 'validate' in self._context and not self._context.get('validate'):
            return False
         
        need_update = False
        if self.is_comp:
            if 'c_partner_id' in vals:
                need_update = True
                vals['partner_id'] = vals['c_partner_id']
        elif 'partner_id' in vals:
            need_update = True
            vals['c_partner_id'] = vals['partner_id']
        
        ignore_fields = ['trip_id']
        for f in ignore_fields:
            if f in vals:
                return need_update
        
        state =  vals['state'] if 'state' in vals else (self[0].state or 'd')
        
        r = self
                    
        if state not in ('d', 'b') or r.payment_total > 0 or r.amove_id or r.is_manual_price:
            return need_update
        
        fields = ['discount', 'discount_amount', 'car_type_price', 'add_price', 'car_type', 'manual_price']
        
        
        if len(self) > 1:
            for f in fields:
                if f in vals:
                    raise ValidationError(_('You can update prices on multi transaction'))
        
       
        have_vals = False
        for f in fields:
            if f in vals:
                have_vals = True
                break
        
        if not have_vals:
            for f in ['add_price_ids', 'partner_id', 'c_partner_id', 'branch_to_id', 'discount_type', 'shipping_type']:
                if f in vals:
                    have_vals = True
                    break 
        
        if not have_vals:
            return need_update
                
        if have_vals:
                            
            result = r._price_state_type_change(validate=True, vals=vals)
            
            if not result:
                return need_update
            
            if 'warning' in result:
                raise ValidationError(result['warning']['message'])
            
            values = result['value']             
            vals.update(values)
            
            valid_price = vals.get('valid_price', r.valid_price)
            
            if not valid_price:
                raise ValidationError(_('Please review the shipping price list for the companies') if self.is_comp \
                               else _('Please review the price list for the cities'))

        return True
    """
    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None): 
        super(Receipt, self)._search(args, offset=offset, limit=limit, order=order, count=count, access_rights_uid=access_rights_uid)
    """
    
    
    @api.depends('state')
    def action_confirm_receipt(self):
        for r in self:
            if r.state != 'd':
                raise ValidationError(_('This receipt is not valid to confirmed'))
            
        if self.shipping_type  == '2':
            self._compute_residual()  
            if not self.reconciled:
                raise ValidationError(_('Please make all payment before validation!'))
        for r in self:
            # move_id = r.move_id
            # receipt_no = False
            # while True:
            #     receipt_no = move_id.receipt_sec_id.sudo()._next()
            #     if self.search([('receipt_no', '=', receipt_no)], limit=1, count=True) == 0:
            #         break 
            # code = move_id.code + receipt_no[4:5]
            # prefix = str(int(receipt_no[len(code)+1:]))
            # name = code + '-' + prefix    
            if  r.is_comp == False:
                r.create_invoice()
            r.no_validate(self._context).super_write({'state': 'b'})    
            
            
            # common.tms_action_send_sms(r)
        
        return True
    
    
    def recreate_receipt_no(self):
        for r in self:
            move_id = r.move_id
            receipt_no = False
            while True:
                receipt_no = move_id.receipt_sec_id.sudo()._next()
                if len(self.search([('receipt_no', '=', receipt_no)], limit=1)) == 0:
                    break 
            code = move_id.code + receipt_no[4:5]
            prefix = str(int(receipt_no[len(code)+1:]))
            name = code + '-' + prefix    
            r.super_write({'receipt_no': receipt_no, 'name': name})  
    
    
    
    @api.depends('state', 'payment_total', 'can_cancel')
    def action_cancel_receipt(self):
        self.ensure_one()
        
        if not self.can_cancel:
            raise UserError(_('Access Error!Check your receipt state, current branch, receipt payments or contact the administrator!'))
        
        if self.payment_total > 0 and not self.invoice_id:
            context =  dict(self._context)
            context.update({'default_receipt_id': self.id, 'receipt_id': self.id, 'default_source': 1, 'source': 1, 'type': 'outbound'})  
            return {
                'name': ('Refund Payments'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'tms.register.payments',
                'view_id': False,
                'type': 'ir.actions.act_window',
                'context': context,
                'target': 'new'
            }
        
        self._make_cancel()
    
    def _can_downoad(self):
        branch_id = self.env.user.branch_id
        for r in self:
            r.can_downoad = r.trip_id.state != 'r' and r.cur_branch_id == branch_id

    def action_downoad(self):
        now = fields.Datetime.now()
        for r in self:
            if not r.can_downoad:
                raise UserError(_('Can download this receipt'))            
            if  r.state == 'a':
                pass
            else:
                r.write({'state': 'd', 'down_date': now})
                rdata = {'trip_id': False, 'cur_branch_id': self.env.user.branch_id.id,
                         'cur_city_id': self.env.user.branch_id.city_id.id,
                         'state': 't' if not r.trip_id.is_internal else r.state}
                r.no_validate(self._context).super_write(rdata)

#                r.receipt_id.no_validate(self._context).super_write(rdata)

    
    @api.depends('can_return')
    def action_cancel_return(self):
        self.ensure_one()
        if not self.can_return:
            raise ValidationError(_('You can not cancel this receipt cancelled before or used or exceeded date')) 
        
        if self.payment_total == self.go_price:
            self._cancel_return()
        else:
            context =  dict(self._context)
            context.update({'default_receipt_id': self.id, 'receipt_id': self.id, 'default_source': 1, 'source': 1, 'type': 'outbound'})  
            return {
                'name': ('Refound Payments'),
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'tms.register.payments',
                'view_id': False,
                'type': 'ir.actions.act_window',
                'context': context,
                'target': 'new'
            }
    
        

    def action_post(self, vals):
        
        if self.state not in ['a', 't']:
            raise ValidationError(_('This receipt can not posted!'))
        
        
        move_id = self.env['tms.move'].search([('branch_id', '=', self.cur_branch_id.id), ('is_comp', '=', self.is_comp), ('is_manual', '=', False)], limit=1)
        if not move_id:
            if not self.cur_branch_id.costcenter1_id:
                move_id = self.move_id
                #move_id = self.env['tms.move'].search([('branch_id', '=', self.branch_id.id), ('is_comp', '=', self.is_comp), ('is_manual', '=', False)], limit=1)
                if not move_id:
                    raise ValidationError(_('This branch has invalid exit sequence'))
        
        if self.env.user.branch_id != self.cur_branch_id:
            raise UserError("Your branch is not meet the receipt current branch!")
                    
        
        context = dict(self._context)
        receipt = self.with_context(context)

        ground_total = receipt.ground_total
        
        ground_payment = receipt.ground_payment if ground_total > 0 else 0
        
        rem = receipt.currency_id.round(ground_total - ground_payment) if ground_total > 0  else 0
        
        receipt._compute_residual()
        
        if not self.is_comp and not self.partner_id.allow_debit:
            
            if not receipt.reconciled and  not receipt.is_comp:
                raise ValidationError(_('Please register receipt payment before post!'))
                        
            if not float_is_zero(rem, precision_rounding=receipt.currency_id.rounding):
                return self.action_register_ground_payments()
                
                #raise ValidationError(_('Please register ground payment before post!'))
          
            
        vals.update( {
            'posted_date': fields.Datetime.now(),
            'posted_by': self.env.uid,
            'exit_no': move_id.post_sec_id.sudo()._next(),
            'state': 'e'
            })
        
        self.super_write(vals)
        
        
    
    def action_post_wizard(self):
        self.ensure_one()
        #self.compute_grounds_price()
        if not self.is_comp:
            self._compute_residual()
            ground_total = self.ground_total
            ground_payment = self.ground_payment if ground_total > 0 else 0
            if not self.partner_id.allow_debit:
                if ground_total != ground_payment:
                    return self.action_register_ground_payments(recompute=False)
                
                if not self.reconciled:
                    raise ValidationError(_('Please make all payment before posted!')) 
        
        context =  dict(self._context)
        
        return {
            'name': _('Post Receipt'),
            'type': 'ir.actions.act_window',
            'res_model': 'tms.post.receipt',
            'view_type': 'form',
            'view_mode': 'form',
            'context': context,
            'target': 'new',
        }
        
    def dump(self, obj):
        for attr in dir(obj):
            _logger.error("obj.%s = %s" , attr, getattr(obj, attr))


    
    
    def name_get(self):
        result = []
        for receipt in self:
            result.append((receipt.id, receipt.name))
        return result
    

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('receipt_no', '=like', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        obj = self.search(domain + args, limit=limit)
        return obj.name_get()
    
    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        if self._context.get('current', None):
            branch_id = self.env.user.branch_id
            if args:
                args = expression.AND([['|', ('branch_id', '=', branch_id.id), ('branch_to_id', '=', branch_id.id)], args])
            else:
                args = ['|', ('branch_id', '=', branch_id.id), ('branch_to_id', '=', branch_id.id)]
        """
        if self._context.get('selector', None):
            active_id = self._context.get('active_id')
            if active_id:
                states = ('state', 'in', ['b', 't'])
                trip = self.env['tms.trip'].browse(active_id)
                
                #trip_route_count= self.env['tms.receipt.route'].search([('trip_id','=', active_id)], count=True)
                args = [('id', '=', 0)]
                if trip.is_internal:
                    if trip.internal_type ==1:
                        args = [('state', '=', 'b'), ('trip_id', '=', False), ('cur_branch_id', '=', self.env.user.branch_id.id)]
                    elif trip.internal_type ==2:
                        args = [('state', '=', 'a'), ('partner_id', '=', trip.partner_id.id), ('trip_id', '=', False), ('cur_branch_id', '=', self.env.user.branch_id.id)]
                else:
                    args = [states, ('trip_id', '=', False), ('cur_branch_id', '=', self.env.user.branch_id.id)]
        
                _logger.info("_get_receipt_domain is_internal: %s, internal_type: %s", trip.is_internal, trip.internal_type)    
        """
        
        return super(Receipt, self)._search(args, offset=offset, limit=limit, order=order, access_rights_uid=access_rights_uid)

    freight_state = fields.Many2one('tms.freight.state', string='Freight State', domain=[('id', '=', 0)])
    
    car_type = fields.Many2one('tms.car.type', related='model_id.car_type_id', string='Car Type', store=True, readonly=True)    
    
    car_state = fields.Many2one('tms.car.state', string='Car State') 
    
    base_price = fields.Monetary(currency_field='currency_id', readonly=True)
    
    car_type_price = fields.Monetary(currency_field='currency_id', readonly=True)
    
    car_state_price = fields.Monetary(currency_field='currency_id', readonly=True)
        
    receipt_price = fields.Monetary(currency_field='currency_id', readonly=True)
    
    return_price = fields.Monetary(currency_field='currency_id', store=True, readonly=True)
      
    go_price = fields.Monetary(currency_field='currency_id', store=True, readonly=True)  
    
    return_cancelled = fields.Boolean(readonly=True, tracking=True)
                        
    amount_untaxed = fields.Monetary(currency_field='currency_id',store=True, readonly=True)
    
    amount_tax = fields.Monetary(currency_field='currency_id', store=True, readonly=True)    
    
    amount_total = fields.Monetary(currency_field='currency_id', store=True, readonly=True, tracking=True)
    
    pick_cost = fields.Monetary(string='Pickup Cost', readonly=True, default=0.0)
    
    discount = fields.Float(default=0)
        
    discount_amount = fields.Monetary(currency_field='currency_id', readonly=True, tracking=True)
    
    add_price_ids = fields.One2many('tms.receipt.add.price', 'receipt_id' ) 
    
    add_price = fields.Monetary(currency_field='currency_id', readonly=True, tracking=True)
    
    residual = fields.Monetary(currency_field='currency_id', compute='_compute_residual', store=True, readonly=True)
    
    reconciled = fields.Boolean(string='Paid/Reconciled', store=True, readonly=True, compute='_compute_residual',
        help="It indicates that the invoice has been paid and the journal entry of the invoice has been reconciled with one or several journal entries of payment.")
       
    ground_amount = fields.Monetary(string='Ground Amount', currency_field='currency_id', compute='_compute_ground', store=True)
        
    ground_days = fields.Integer(string='Ground Days', compute='_compute_ground', store=True)
    
    ground_discount = fields.Monetary(string='Ground Discount', currency_field='currency_id')
    
    ground_amount_tax = fields.Monetary(string='Ground Tax', currency_field='currency_id', readonly=True)
    
    ground_total = fields.Monetary(string='Ground Total', currency_field='currency_id', readonly=True)
    
    ground_payment = fields.Monetary(string='Ground Payments', compute='_compute_ground_payment', currency_field='currency_id', store=True)
    
    batch_payment_id = fields.Many2one('tms.batch.payment', readonly=True)
            
    payment_total = fields.Monetary(currency_field='currency_id', compute='_compute_residual', store=True)
    
    show_add_price = fields.Boolean(default=False, store=False)
    
    manual_price = fields.Monetary(string='Manual Price', currency_field='currency_id', tracking=True)
    is_manual_price = fields.Boolean(readonly=True)
    price_diff = fields.Float(digits=(2, 2), readonly=True)
    
    posted_by = fields.Many2one('res.users', string='Posted By', readonly=True)
    
    posted = fields.Boolean(default=False, readonly=True)
    
    discount_type = fields.Selection([
            ("0",'No Discount'),
            ("1", 'Percentage Discount'),
            ("2", 'Fixed Discount'),
        ], string='Discount Type', index=True, type='integer', default="0",
        tracking=True)
    
    valid_price = fields.Boolean(default=False, readonly=True)
    
    payment_ids = fields.One2many('tms.payments', 'receipt_id', copy=False, readonly=True)
    
    have_payments = fields.Boolean(compute='_have_payments')
    
    @api.constrains('pick_cost')
    def _check_pick_cost(self):
        for s in self:
            if s.amount_untaxed > 0 and s.pick_cost > s.amount_untaxed:
                raise ValidationError("Pickup cost most be less than amount price.")
    
    
    def _have_payments(self):
        self.have_payments = self.payment_ids and len(self.payment_ids) > 0
    
    def _compute_tax_to(self, amount, branch_id, incl=False, tax_id=False):
        
        #raise ValidationError("%s X %s" % (self, self._origin.tax_id,))
                        
        if not tax_id:
            if '_origin' in self and self._origin and  self._origin.tax_id:
                tax_id = self._origin.tax_id
            elif self.tax_id:
                tax_id = self.tax_id
            else:
                tax_id = branch_id.tax_id
            
        tax_amount = 0.0
        if amount and tax_id:
            tax_id = tax_id.sudo()
            price_include = tax_id.price_include
            tax_id.price_include = incl
            tax_amount = tax_id._compute_amount(amount, amount, partner=self.partner_id or self.c_partner_id)
            tax_id.price_include = price_include
        
        return tax_amount
    
    def _compute_tax_to_inc(self, amount, branch_id):
        return self._compute_tax_to(amount, branch_id, incl=True)
    
    def _compute_tax(self, amount):
        return self._compute_tax_to(amount, self.branch_id)
    
    def _compute_tax_inc(self, amount):
        return self._compute_tax_to(amount, self.branch_id, incl=True)
    

    def _clac_receipt_price(self, vals):
        state_price = 0.0
        res = {'valid_price': False}
        
        freight_state_id = vals.get('freight_state') or self.freight_state.id
        car_type = vals.get('car_type')
        car_state = vals.get('car_state')
        base_price = vals.get('base_price', 0)
        manual_price = vals.get('manual_price',  self.manual_price)
        shipping_type = vals.get('shipping_type') or self.shipping_type
        is_comp = vals['is_comp'] if 'is_comp' in vals  else (self and self.is_comp) or self._context.get('is_comp')
        city_id = (vals.get('city_id') and self.env['tms.city'].browse(vals.get('city_id'))) or (self.city_id or self.env['tms.move'].browse(vals['move_id']).branch_id.city_id)
        city_to_id = (vals.get('city_to_id') and self.env['tms.city'].browse(vals.get('city_to_id'))) or self.city_to_id
        partner_id_id = vals.get('partner_id') or self.partner_id.id
        car_type = self.env['tms.car.type'].browse(car_type) if car_type else (self.car_type or self.env['tms.cmodel'].browse(vals.get('model_id')).car_type_id)
        
        car_state = self.env['tms.car.state'].browse(car_state) if  car_state else self.car_state
        
        if not is_comp and city_to_id and city_to_id.manual_price:
            #if True:
            #raise ValidationError("base_price : %s, manual_price: %s" % (base_price, manual_price))
            #if manual_price > 0:
                #base_price = 0
            res['valid_price'] = manual_price > 0
            state_price = base_price
        elif city_id and city_to_id:
            if freight_state_id:
                if is_comp:
                    partner_state_obj = self.env['tms.partner.price.list']
                    state_price_record = partner_state_obj.search([('partner_id', '=', partner_id_id),
                                               ('city_from_id', '=', city_id.id),
                                               ('city_to_id', '=', city_to_id.id),
                                               ('freight_state_id', '=', freight_state_id)], limit=1)
                    if not state_price_record:
                        state_price_record = partner_state_obj.search([('partner_id', '=', partner_id_id),
                                           ('city_from_id', '=', city_to_id.id),
                                           ('city_to_id', '=', city_id.id),
                                           ('freight_state_id', '=', freight_state_id)], limit=1)
                    
                    if state_price_record:
                        state_price = state_price_record.price
                        res['valid_price'] = True
                        res['partner_deal'] = state_price_record.id
                    #if not self.env.in_onchange:
                    #raise ValidationError("state_price:%s " % state_price)
                    
            elif not is_comp :
                
                if shipping_type == '3':
                    if 'go_receipt_id' in vals:
                        go_receipt_id_id = vals['go_receipt_id'] and self.browse(vals['go_receipt_id'])[0]
                    else:
                        go_receipt_id_id = self.go_receipt_id
                    
                    if go_receipt_id_id:
                        state_price = go_receipt_id_id.return_price
                        res['valid_price'] = True
                        if go_receipt_id_id.branch_id.tax_id and not go_receipt_id_id.branch_to_id.zero_tax_to:
                            res['amount_return'] = state_price - go_receipt_id_id._compute_tax_inc(state_price)
                        else:
                            res['amount_return'] = state_price
                        
                elif not res['valid_price']:
                    freight_price_obj = self.env['tms.freight.price']
                    state_price_record = freight_price_obj.search([('city_id', '=', city_id.id),
                                                                   ('city_to_id', '=', city_to_id.id)], limit=1)
                    
                    d1 = fields.Datetime.from_string('2022-09-21 00:00:00')
                    d2 = fields.Datetime.from_string('2022-09-25 00:00:00')
                    receipt_date = self and self[0].receipt_date or fields.Datetime.now()
                    if self and shipping_type != '2' and city_id.id in (2, 3) and city_to_id.id == 1 and receipt_date >= d1 and receipt_date < d2 :
                        if city_id.id == '2':
                            state_price = 392
                        else:
                            state_price = 592
                        
                        res['discount'] = 0.0
                        res['discount_amount'] = 0.0
                        res['discount_type'] = 0
                        res['valid_price'] = True
                        
                    elif state_price_record:
                        state_price = state_price_record.two_way_price if shipping_type == '2' else  state_price_record.one_way_price 
                        res['valid_price'] = True
                    
        res['base_price'] = state_price
        res['car_type_price'] = 0 if is_comp else car_type.value if car_type else 0.0
        res['car_state_price'] = car_state.value if car_state else 0.0
        res['receipt_price'] =  res['base_price'] + res['car_type_price'] + res['car_state_price']
        #raise UserError("base_price_old: %s, state_price: %s, city_id:%s, city_to_id:%s" % (base_price_old, state_price, city_id, city_to_id))
        vals.update(res)
        return vals
        
    def _compute_amount0(self):
        pass
    
    def _get_val(self, key, vals):
        if key in vals:
            return vals[key]
        return self.__getitem__(key)
    
    def _compute_amount(self, vals):
        #date = fields.Date.from_string(self.receipt_date ) if self.receipt_date else fields.Date.context_today(self)
        
        
        discount_type = self._get_val('discount_type',  vals)
        discount_amount =  self._get_val('discount_amount',  vals)
        discount = self._get_val('discount',  vals)
        receipt_price =  self._get_val('receipt_price',  vals)
        shipping_type = self._get_val('shipping_type',  vals)
        partner_deal = self._get_val('partner_deal',  vals)
        manual_price = self._get_val('manual_price',  vals)
        car_type_price = self._get_val('car_type_price',  vals)
        car_state_price = self._get_val('car_state_price',  vals)
        is_comp = vals['is_comp'] if 'is_comp' in vals  else self and self.is_comp or self._context.get('is_comp')
        currency_id = self._default_currency_used()
        branch_id = (vals.get('branch_id') and self.env['tms.branch'].browse(vals.get('branch_id'))) or (self.branch_id or self.env['tms.move'].browse(vals['move_id']).branch_id)
        branch_to_id = (vals.get('branch_to_id') and self.env['tms.branch'].browse(vals.get('branch_to_id'))) or self.branch_to_id
        city_id = branch_id.city_id
        city_to_id = branch_to_id.city_id
        
        ret = {'return_price': 0, 'go_price': 0, 'amount_untaxed': 0, 'amount_tax': 0, 'amount_total': 0, 'add_price': 0}
        if shipping_type == '3' or (self and manual_price != self.manual_price) or discount_type not in ('1', '2') or receipt_price <= 0:
            ret['discount'] = 0.0
            ret['discount_amount'] = 0.0
            ret['discount_type'] = 0
        elif discount_type == 1:
            discount_amount = currency_id.round(discount/100.0 * receipt_price)
            ret['discount_amount'] = discount_amount
        elif discount_type == '2' :
            discount = currency_id.round(discount_amount/receipt_price * 100.0)
            ret['discount'] = discount
        
        if shipping_type != '3':
            
            t_add_price = 0.0
            for addprice in self.add_price_ids:
                if addprice.amount > 0:
                    t_add_price += abs(addprice.amount)
            
            if t_add_price == 0.0:
                t_add_price = abs(vals.get('add_price',  0.0))
                
            
            ret['add_price'] = t_add_price
            
            if is_comp and partner_deal: 
                if isinstance(partner_deal, int) and partner_deal > 0:
                    partner_deal = self.env['tms.partner.price.list'].browse(partner_deal)
                    
            ret['amount_untaxed'] = t_add_price + receipt_price - discount_amount
            ret['amount_tax'] = self._compute_tax_to(ret['amount_untaxed'], branch_id) if not branch_to_id.zero_tax_to and ret['amount_untaxed'] > 0 else 0.0
            #ret['manual_price'] = 0.0
            
            if is_comp and partner_deal and partner_deal.with_tax and not branch_to_id.zero_tax_to:
                t_add_price_tax = self._compute_tax_to_inc(t_add_price, branch_id) if t_add_price > 0 else 0.0
                price_taxed = self._compute_tax_to_inc(partner_deal.price, branch_id)
                price_untaxed = partner_deal.price - price_taxed
                receipt_price = price_untaxed + car_type_price + car_state_price
                ret['base_price'] =  price_untaxed
                ret['receipt_price'] =  receipt_price
                ret['amount_untaxed'] = t_add_price + receipt_price
                ret['amount_tax'] = t_add_price_tax + price_taxed
                ret['manual_price'] = partner_deal.price
            
            
            if not is_comp and manual_price > 0:
                is_manual = city_to_id.manual_price
                t_add_price_tax = self._compute_tax_to(t_add_price, branch_id) if not branch_to_id.zero_tax_to and t_add_price > 0 else 0.0
                
                manual_price_tax = self._compute_tax_to_inc(manual_price, branch_id) if not branch_to_id.zero_tax_to else 0.0
                tax_id = branch_id.tax_id if not branch_to_id.zero_tax_to else None 
                
                new_receipt_price = abs(manual_price - manual_price_tax)
                
                if receipt_price <= 0 or is_manual:
                    receipt_price = new_receipt_price
                
                old_receipt_price = receipt_price
                 
                discount_amount =  old_receipt_price - new_receipt_price if not is_manual and old_receipt_price >  new_receipt_price else 0
                discount = discount_amount/receipt_price * 100.0 if receipt_price > 0 else 0
                if discount == 0:
                    discount_amount = 0
                
                
                ret['discount'] =  discount
                ret['discount_amount'] =  discount_amount
                ret['discount_type'] =  1 if discount_amount > 0 else 0
                ret['car_type_price'] =  car_type_price
                ret['car_state_price'] =  car_state_price
                ret['receipt_price'] =  receipt_price
                ret['base_price'] = self._get_val('base_price',  vals)
                ret['amount_untaxed'] = t_add_price + new_receipt_price
                ret['amount_tax'] = t_add_price_tax + manual_price_tax
                ret['price_diff'] = new_receipt_price - old_receipt_price
                
                    
            ret['amount_total'] = ret['amount_untaxed'] + ret['amount_tax']
            
            if shipping_type == '2':
                ret['return_price'] = currency_id.round(ret['amount_total'] * 0.45) if currency_id else ret['amount_total'] * 0.45
                ret['go_price'] = currency_id.round(ret['amount_total'] - ret['return_price']) if currency_id else ret['amount_total'] - ret['return_price']
        else: 
            if 'amount_return' in vals:
                ret['amount_untaxed'] = vals['amount_return']
                del vals['amount_return']
            
           
        
        vals.update(ret)

    
    ignore_dicount_error = False
    
    def _prevent_change_price(self,vals={}):
        r = self
        state = vals.get('state',  r.state)
        if not state:
            return False
        is_manual_price = vals.get('is_manual_price',  r.is_manual_price)
        if is_manual_price or r.amove_id or r.payment_total > 0.01 :
            return True
        if state == 'd':
            return not r._context.get('edit') 
        return False if r._context.get('edit') and state not in ('e', 'c') and self.env.user.has_group("tms.group_tms_change_receipt_price")  else True
         
    
    @api.onchange('discount_amount')
    def _discount_amount_changed(self):
        
        if self.discount_type != '2'  or self._prevent_change_price():
            return {}
        
        if self.discount_amount < 0.0:
            self.discount_amount = 0
            return {'value': {'valid_price': False},'warning': {'message': _('The discount should be between 0 and 100')}}
        
        if self.manual_price > 0:
            return self._price_state_type_change()
        
        max_discount = self.env.user.max_discount
        
        newval = {}
        receipt_price = self.receipt_price
        if receipt_price == 0:
            self._clac_receipt_price(newval)
            receipt_price = newval['receipt_price']
        newval['discount_amount'] = self.discount_amount
        
        discount = 0
        if receipt_price > 0:
            discount = self.discount_amount/receipt_price * 100.0
        
        if discount > max_discount:
            self.ignore_dicount_error = True
            self.discount_amount = max_discount/100.0 * receipt_price
            self.discount = max_discount
            
            return {'warning': {'message': _('You can only set max discount to (%s) %s' % (str(max_discount), '%'))}}
                
        return self._price_state_type_change(vals=newval)
    
    @api.onchange('discount')
    def _discount_changed(self):
        if self.discount_type != '1'  or self._prevent_change_price():
            return {}
        if self.manual_price > 0:
            return self._price_state_type_change()
        
        newval = {}
        receipt_price = self.receipt_price
        if receipt_price == 0:
            self._clac_receipt_price(newval)
            receipt_price = newval['receipt_price']
        newval['discount'] = self.discount
        
        max_discount = self.env.user.max_discount
        
        if self.discount > max_discount:
            self.ignore_dicount_error = True
            self.discount_amount = max_discount/100.0 * receipt_price
            self.discount = max_discount
            
            return {'warning': {'message': _('You can only set max discount to (%s) %s' % (str(max_discount), '%'))}}
        
        return self._price_state_type_change(vals=newval)
        
    @api.onchange('discount_type')
    def _discount_type_changed(self):
        if self.discount_type == 0 or self._prevent_change_price():
            self.discount = 0.0
            self.discount_amount = 0.0
        return self._price_state_type_change(vals={'discount_type': self.discount_type,
                                                    'discount':self.discount, 'discount_amount':self.discount_amount})
    
    @api.onchange('model_id', 'freight_state', 'car_state',
                  'partner_id', 'c_partner_id', 'branch_to_id',
                  'add_price_ids', 'shipping_type', 'manual_price')
    def _price_state_type_change(self, validate=False, vals=None):
        
        r = self
        res = {}
        value = {}
        if vals:
            value.update(vals)
        if self._prevent_change_price(value):
            is_manual_price = value.get('is_manual_price',  r.is_manual_price)
            #raise UserError("prevent_change is_manual_price: %s" % is_manual_price)            
            return res

        value['valid_price'] = False                                  
        if (value.get('model_id') or r.model_id) and (value.get('partner_id') or r.partner_id):
            
            r._clac_receipt_price(value)
            r._compute_amount(value)
            r._compute_residual(value)
            discount_type = self._get_val('discount_type', value)
            discount = self._get_val('discount', value)
            if not value['valid_price']:
                if validate:
                    res['warning'] = {'message': _('Please review the shipping price list for the companies') if self.is_comp \
                               else _('Please review the price list for the cities')}
            
            else:
            
                if discount_type > 0:
                    max_discount = self.env.user.max_discount
                    if not self.ignore_dicount_error:
                        if discount > max_discount:
                            res['warning'] = {'message':  _('You can only set max discount to (%s) %s' % (str(max_discount), '%'))}
                        elif discount > 100 or discount < 0:
                            res['warning'] = {'message': _('The discount should be between 0 and 100')}
                        # self.ignore_dicount_error = True
                        
                        
                elif discount > 0:
                    value['discount'] = 0.0
                    value['discount_amount'] = 0.0
        
         
        if not value['valid_price'] and 'warning' not in res and validate :
            res['warning'] = {'message': _('Please review the shipping price list for the companies') if self.is_comp \
                               else _('Please review the price list for the cities')}
        
        
        res['value'] = value
        
        return  res                           
 
    
    def read(self, fields=None, load='_classic_read'):
        result = super(Receipt, self).read(fields=fields, load=load)
        vals = result[0] if len(result) == 1 else False
        if vals and 'receipt_price' in vals and 'amount_untaxed' in vals:
            discount = vals['discount'] if 'discount' in vals else 0
            discount_amount = vals['discount_amount'] if 'discount_amount' in vals else 0
            receipt_price = 0
            if vals['receipt_price'] <= 0:
                add_price = vals['add_price'] if 'add_price' in vals else 0
                vals['receipt_price'] = receipt_price = vals['amount_untaxed'] - add_price
            if discount_amount > 0 and discount <= 0 and receipt_price > 0:
                vals['discount'] = discount_amount/receipt_price * 100
            result[0] = vals 
        return result
    
    
    @api.depends('arrival_date')
    def _compute_ground(self):
        pass
    
    def _get_ground_payment(self):
        pyaments = self.env['tms.payments'].search([('receipt_id', '=', self.id), ('source', '=', 2)])
        ground_payment = pyaments.compute_payments(self.currency_id) if pyaments else 0.0
        return ground_payment

    
    def _compute_ground_payment(self):
        self.ground_payment = self._get_ground_payment()

    
    def _compute_return_price(self):
        currency_id = self._default_currency()
        if currency_id:
            self.return_price = currency_id.round(.4 * self.payment_total)
            self.go_price = currency_id.round(self.payment_total - self.return_price)
 

    
    @api.depends('state', 'currency_id', 'invoice_id.amount_total_signed')
    def _compute_residual(self, vals=None):
        for rec in self:
            rec.reconciled = False
            if rec.state == 'c':
                return
            total_payment = 0
            if (rec.is_comp or rec.invoice_id) and not rec.amove_id:
                
                if rec.invoice_id and rec.invoice_id.state == 'paid':
                    print("invoice_id.state == 'paid':")
                    total_payment = rec.amount_total
                elif rec.invoice_id:
                    total_payment = abs( rec.invoice_id.amount_residual - rec.invoice_id.amount_total )
            else:
                if rec.invoice_id:
                    total_payment = abs( rec.invoice_id.amount_residual - rec.invoice_id.amount_total )
            
            if vals:
                amount_total = vals['amount_total'] if 'amount_total' in vals else rec.amount_total
                residual = amount_total - total_payment
                vals['payment_total'] = total_payment
                vals['residual'] = residual
                return vals
            rec.payment_total = rec.currency_id.round(total_payment)
            rec.residual = rec.amount_total - total_payment
            if rec.residual <= 0:
                rec.reconciled = True
            else:
                rec.reconciled = False
            _logger.info("================= rec.reconciled"+str(rec.reconciled))
    
    @api.depends('state', 'currency_id')
    def _compute_payments(self, vals=None):
        
        if self.invoice_id:
            return self._compute_residual(vals)
        
        pyaments = self.env['tms.payments'].search([('receipt_id', '=', self.id), ('source', '=', 1)])
        total_payment = pyaments.compute_payments(self.currency_id)
        if vals:
            vals['payment_total'] = total_payment
            return vals
        self.payment_total = total_payment
                    
    
    
    @api.depends('can_return')
    def _cancel_return(self):
        if not self.can_return:
            raise ValidationError(_('You can not cancel this receipt cancelled before or used or exceeded date')) 
         
        self._compute_residual()
        precision = self.env['decimal.precision'].sudo().precision_get('Product Price')
        
        
        if float_compare(self.payment_total, self.go_price, precision_digits=precision) != 0:
            raise ValidationError(_('Something wont wrong current payment total != go price (%s, %s)') % (self.payment_total, self.go_price)) 
                
        vals = {'payment_total': self.payment_total, 'residual': 0.0, 'reconciled': True, 'return_cancelled': True}
        
        self.super_write(vals)    
             
        
    
    def _make_cancel(self, cancel_return=False):
        
        
        if self.state not in ('b', 'k'):
            raise ValidationError(_('This receipt is going up of branch'))   
        if  self.invoice_id:
            raise ValidationError(_('This receipt was posted'))  
        cancel_no = self.move_id.cancel_sec_id.sudo()._next()
        cancel_date = fields.Datetime.now()
        self.no_validate(self._context).super_write({'state': 'c', 'cancel_no': cancel_no, 'cancel_date': cancel_date, 'cancel_by': self.env.user.id,
                           'residual': 0, 'reconciled': True})
        if self.go_receipt_id:
            self.go_receipt_id.super_write({'used_in_id': False})
        
        payment_ids = self.env['tms.payments'].search([('receipt_id', '=', self.id), ('amove_id', '=', False)])
        if payment_ids:
            payment_ids.write({'ignore': True})
    
        
    def _update_payments(self):
        self.refresh()
        self._compute_residual()
        vals = {'payment_total': self.payment_total, 'residual': self.residual, 'reconciled': self.reconciled}
        self.super_write(vals)
        if (self.shipping_type != '2' or self.reconciled) and self.state == 'd':
            self.action_confirm_receipt()


    receipt_activity = fields.Many2one('tms.receipt.activity')
    
    def _get_receipt_activity(self):
        if not self.receipt_activity:
            self.receipt_activity = self.env['tms.receipt.activity'].create({'receipt_id': self.id}) 
            self.super_write({'receipt_activity': self.receipt_activity.id})
        return self.receipt_activity
    
    def post_receipt_message(self,msg,commit=True):
        # self._get_receipt_activity().message_post(body=msg, message_type='comment')
        try:
            receipt_activity = self._get_receipt_activity()
            receipt_activity.message_post(body=msg, message_type='comment')
            if commit:
                receipt_activity._cr.commit()
        except Exception:
            pass    
        #self._get_receipt_activity().write({'in_comment': msg})
    
    
     
    def action_receipt_activities(self):
        self.ensure_one()
        context =  dict(self._context)
        context.update({'receipt_id': self.id, 'id': self._get_receipt_activity().id})  
        return {
            'name': ('Receipt Activities'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'tms.receipt.activity',
            'view_id': False,
            'res_id': self.receipt_activity.id,
            'type': 'ir.actions.act_window',
            'context': context,
            'domain': [('id', '=', self.receipt_activity.id)]
        }

    def create_invoice(self):
        if not self.invoice_id :
            inv_obj = self.env['account.move']
            vals = {
                'partner_id': self.partner_id.id or self.c_partner_id.id ,
                'ref' : self.name,
                'date' : self.receipt_date.date(),
                'move_type' : 'out_invoice',
                'invoice_line_ids': [(0,0,{
                    'name':_('transportation service for car %s %s plate No %s ' , self.brand_id.name, self.model_id.name , self.car_id),
                    'account_id': self.branch_id.ac_income_id.id,
                    'quantity' : 1,
                    'price_unit' : self.amount_untaxed,
                    # 'tax_ids': [(0,0,self.branch_id.tax_id.id)]
                })]
            }
            inv = inv_obj.create(vals)
            self.invoice_id = inv
            inv.action_post()
     
    def action_register_payment(self):
        self.ensure_one()
        if self.shipping_type == '2' or self.is_comp:
            self.create_invoice()
        if not self.invoice_id :
            return False
        return self.invoice_id.line_ids.action_register_payment()
        # context =  dict(self._context)
        # context.update({'default_receipt_id': self.id, 'receipt_id': self.id, 'default_source': 1, 'source': 1})
        # return {
        #     'name': ('Register Payment'),
        #     'view_type': 'form',
        #     'view_mode': 'form',
        #     'res_model': 'tms.register.payments',
        #     'view_id': False,
        #     'type': 'ir.actions.act_window',
        #     'context': context,
        #     'target': 'new'
        # }
    
     
    def action_register_ground_payments(self, recompute=True):
        #if recompute:
        #    self.compute_grounds_price()
        context =  dict(self._context)
        context.update({'default_receipt_id': self.id, 'receipt_id': self.id, 'default_source': 2, 'source': 2})  
        return {
            'name': ('Register Ground Payment'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'tms.register.payments',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'context': context,
            'target': 'new'
        }
    
    
    
    def action_print_receipt(self):
        """ Print the invoice and mark it as sent, so that we can see more
            easily the next step of the workflow
        """
        self.ensure_one()
        
        # return common.print_receipt(self)
        return self.env.ref('tms.action_print_receipt_exit').report_action(self)

    
    def action_print_receipt_exit(self):
        self.ensure_one()
        return self.env.ref('tms.action_print_receipt_exit').report_action(self)
    
    
    def action_print_receipt_voucher(self):
        self.ensure_one()
        #payments = self.env['tms.payments'].search([('receipt_id', '=', self.id)])
        
        #_logger.info("payments: %s", payments)
        return self.payment_ids[0].action_print_voucher()
    
    
    show_activity = fields.Boolean(compute='_show_activity')
    
    def _show_activity(self):
        self.show_activity = self.env.user.has_group('tms.group_tms_show_activity')
    
    def action_send_sms(self):
        common.tms_action_send_sms(self)
        
    def action_arrival(self):
        common.tms_action_send_post_sms(self)
        
        
    
    def copy0(self, default=None):
        self.ensure_one()
        vals = self.copy_data(default)[0]
        # To avoid to create a translation in the lang of the user, copy_translation will do it
        new = self.with_context(lang=None).super(Receipt,)(vals)
        self.copy_translations(new)
        return new
    
    
    def copy(self, default=None):
        context =  dict(self._context)
        context.update({'copy':1, 'edit':1})
        return {
            'name': ('Receipt'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'tms.receipt',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'context': context,
            'target': 'current'
        }
        
    @api.model
    def default_get(self, fields):
        ctx = self._context
        rec = super(Receipt, self).default_get(fields)
        if ctx.get('copy') and ctx.get('active_id'):
            r = self.browse(ctx.get('active_id'))
            #self._context.update({'is_comp':r.is_comp})
            rec.update({'move_id': r.move_id.id, 'is_comp': r.is_comp, 'partner_id': r.partner_id.id, 'c_partner_id': r.partner_id.id,
                         'city_id': r.city_id.id, 'branch_id': r.branch_id.id, 'pay_city_id': r.pay_city_id.id,
                         'city_to_id': r.city_to_id.id, 'branch_to_id': r.branch_to_id.id,
                          'pay_branch_id': r.pay_branch_id.id,'days_to_arrival': r.days_to_arrival,
                          'brand_id': r.brand_id.id, 'model_id': r.model_id.id,
                          'same_sender': True, 'resv1_name': r.resv1_name, 'resv1_mobile': r.resv1_mobile,
                          'base_price': r.base_price, 'freight_state': r.freight_state.id if r.freight_state else False,
                          'car_type': r.car_type.id if r.car_type else False, 'discount_type': r.discount_type, 'discount': r.discount, 'discount_amount': r.discount_amount,
                          'shipping_type': r.shipping_type, 'manual_price': r.manual_price if not r.is_comp else 0, 'contract_no': r.contract_no})
            
            
             
        #_logger.info("Receipt default_get context: %s, rec: %s", self._context, rec)
        
        
        return rec
    
    can_change_date = fields.Boolean(compute='_can_change_any')    
    can_cancel = fields.Boolean(compute='_can_change_any')
    can_post = fields.Boolean(compute='_can_change_any')
    hide_extra = fields.Boolean(compute='_can_change_any')
    can_return = fields.Boolean(compute='_can_change_any')
    
    def _can_change_any(self):
        self.can_return = False
        user = self.env.user
        self.can_change_date = self.state == 'd' and user.has_group('tms.group_tms_receipt_date')
        
        self.can_cancel = self.state == 'd' or ( self.state in ('b', 'k') and (user.branch_id == self.branch_id and not self.amove_id and self.payment_total == 0 and user.has_group('tms.group_tms_cancel_receipt')))
        self.can_post = self.state in ['t', 'a'] and (self.cur_branch_id.id == user.branch_id.id or \
                                                       (self.state == 'a' and self.branch_to_id == user.branch_id))
        self.hide_extra =self.is_comp and not user.has_group('tms.group_tms_extra_receipt_price')
        if self.shipping_type == '2' and not self.return_cancelled and self.state == 'e' and not self.used_in_id and user.has_group('tms.group_tms_cancel_receipt'):
            receipt_date = fields.Datetime.from_string(self.receipt_date) + datetime.timedelta(days=365)    
            self.can_return = receipt_date >  datetime.datetime.now()
        

    @api.depends('amount_total','return_price')
    
    def _can_change_return(self):
        self.can_return = False
        if self.shipping_type == '3' and self.state=='a':
            receipt_date = fields.Datetime.from_string(self.receipt_date) + datetime.timedelta(days=365)    
            self.can_return = receipt_date >  datetime.datetime.now() and self.env.user.has_group('tms.group_tms_cancel_receipt')
        
    roo = fields.Integer(compute='can_edit_receipt')
    ro = fields.Integer(compute='can_edit_receipt')
    ro2 = fields.Integer(compute='can_edit_receipt', help="For ground discount")
    ro3 = fields.Integer(compute='can_edit_receipt', help="For Comments")
    ro4 = fields.Boolean(compute='can_edit_receipt', help="For Show Ground Payments")
    ro5 = fields.Boolean(compute='can_edit_receipt', help="For Add Price")
    show_prices = fields.Boolean(store=False, string='Show Price Details')
    ro6 = fields.Integer(compute='can_edit_receipt', help="Change Receipt Price")
    ro7 = fields.Integer(compute='can_edit_receipt', default=1, help="Change Pickup Price")
    edit_mode = fields.Boolean()
    
    @api.depends('payment_total')
    
    def can_edit_receipt(self):
        edit = self.state == 'd'
        self.roo = 0 if edit else 1
        self.ro5 = False
        self.ro7 = 1
        if not self.amove_id and not self.invoice_id:
            if self.state == 'b':
                if self.is_comp:
                    if self.payment_total == 0 and self.env.user.has_group("tms.group_tms_extra_receipt_price"):
                        self.ro5 = True
                elif self.payment_total == 0:
                    self.ro5 = True
            elif self.state == 'd' and self.is_comp and self.env.user.has_group("tms.group_tms_extra_receipt_price"):
                self.ro5 = True
            elif self.state == 'd' and not self.is_comp:
                self.ro5 = True
            
            if not edit and (self.state not in ['c', 'e'] and self.env.user.has_group("tms.group_tms_admin")):
                self.roo = 0
                edit = self.payment_total == 0
                
        #edit = self.env.user.has_group("tms.group_tms_admin")    
        self.ro =  0 if edit else 1
        self.ro2 = 0 if self.state in ['c', 'e', 'a'] and self.ground_amount > 0 and self.ground_payment == 0 else 1
        self.ro3 = 0 if self.edit_mode or self.state not in ['c', 'e']  else 1
        self.ro4 = self.ground_total != self.ground_payment
        self.ro6 = 1
        if not self.amove_id and not self.invoice_id and self.state !='c' and self.env.user.has_group("tms.group_tms_change_receipt_price"):
            self.ro6 = 0
        if not self.amove_id and not self.invoice_id:
            self.ro7 = 0 if self.is_comp and self.env.user.has_group('tms.group_tms_edit_pickup_price') else 1
        
    
    refresh_frights = fields.Boolean(store=False)
    
    @api.depends('city_id', 'city_to_id', 'c_partner_id') 
    @api.onchange('refresh_frights')
    def _onchange_refresh_com_fright(self):
        city_id = self.city_id
        city_to_id = self.city_to_id
        state_ids = set()
        if city_id and city_to_id:
            self._cr.execute("""SELECT DISTINCT freight_state_id as id from tms_partner_price_list
                                 WHERE ((city_from_id=%s AND city_to_id=%s)
                                       OR (city_to_id=%s AND city_from_id=%s))
                                   AND partner_id=%s AND (deal=-1 OR deal_used>0)""",
                  (city_id, city_to_id, city_id, city_to_id,self.c_partner_id.id))
            sqlresult = self._cr.fetchall()
            for (id,) in sqlresult:
                state_ids.add(id)
        
        domain = {}
        if len(state_ids):
            state_ids = list(state_ids)
            domain['freight_state'] = [('id', 'in', state_ids)]
        return domain
    
          
    def no_validate(self, ctx):
        ctx = dict(ctx)
        ctx.update({'validate': False})
        s = self.with_context(ctx)
        return s


    tax_id = fields.Many2one('account.tax', 'Account Tax', store=True)
    tax_g_id = fields.Many2one('account.tax', 'Ground Account Tax', store=True)
    
    def _compute_tax_id(self):
        for r in self:
            r.tax_id = r.branch_id.tax_id
            r.tax_g_id = r.branch_to_id.tax_id
    
    """
    go_ret_fraction = fields.Float(compute='_compute_go_ret_fraction', store=True)
    def _compute_go_ret_fraction(self):
        for r in self:
            r.go_ret_fraction = .6
    """
    #out_price = fields.Float(compute='_compute_out_price', store=True)
    
    def _compute_out_price(self):
        for r in self:
            r.out_price = 0.0
            if r.shipping_type ==3 and r.go_receipt_id:
                out_price = r._get_return_price(r.go_receipt_id)
                r.out_price = out_price
    
    def _get_return_price(self,r):
        out_price = 0.0
        if r.tax_id and r.amount_tax > 0:
            tax_id = r.tax_id
            tax_amount = 0.0
            amount = r.return_price
            tax_id = tax_id.sudo()
            price_include = tax_id.price_include
            tax_id.price_include = True
            tax_amount = tax_id._compute_amount(amount, amount, partner=r.partner_id or r.c_partner_id)
            tax_id.price_include = price_include
            out_price = r.currency_id.round(amount - tax_amount)
        else:
            out_price = r.return_price
        return out_price
    
    detect_report_branch_name = fields.Boolean(compute='_is_get_rep_branch_name', store=False)
    def get_report_branch_name(self, report_name):
        if report_name == 'tms.print_receipt_exit':
            return self.cur_branch_id.name
        return self.branch_id.name
    
    
    def _is_get_rep_branch_name(self):
        self.detect_report_branch_name = True
    
     
    def action_change_receipt_price(self):
        context =  dict(self._context)
        context.update({'default_receipt_id': self.id, 'receipt_id': self.id})  
        return {
            'name': ('Change Receipt Price'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'tms.change.receipt.price',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'context': context,
            'target': 'new'
        }
    
    has_entry = fields.Boolean(compute='_compute_has_entry')
    
    def action_cancel_entry(self):
        
        self.ensure_one()
        
        cr = self.env.cr
        date = self.date
        
        if date and self.amove_id and not self.invoice_id:
            
            #receipt_date = fields.Datetime.from_string(date) - datetime.timedelta(months=2)
            
            lock_date = max(self.env.user.company_id.period_lock_date or '0000-00-00', self.env.user.company_id.fiscalyear_lock_date or '0000-00-00')
            if self.user_has_groups('account.group_account_manager'):
                lock_date = self.env.user.company_id.fiscalyear_lock_date
            if date <= (lock_date or '0000-00-00'):
                if self.user_has_groups('account.group_account_manager'):
                    message = _("You cannot add/modify entries prior to and inclusive of the lock date %s") % (lock_date)
                else:
                    message = _("You cannot add/modify entries prior to and inclusive of the lock date %s. Check the company settings or ask someone with the 'Adviser' role") % (lock_date)
                raise UserError(message)
            
            
            cr.execute("""DELETE FROM account_move WHERE id=%s""", (self.amove_id.id,))
            
            
        return True
    
    
    def _compute_has_entry(self):
        for r in self:
            r.has_entry = bool(r.amove_id)
            
    
    def action_toggle_edit_mode(self):
        for r in self:
            if r.state in ('a', 'e') and not r.amove_id:
                if r.edit_mode:
                    r.state = 'e'
                    r.edit_mode = False
                elif r.state == 'e':
                    r.state = 'a'
                    r.edit_mode = True
                
    
class AddPrice(models.Model):
    _name = 'tms.receipt.add.price'
    receipt_id =  fields.Many2one('tms.receipt') 
    description = fields.Char(string='Description', required=True)
    currency_id = fields.Many2one('res.currency', related='receipt_id.currency_id', string="Company Currency", readonly=True)
    amount = fields.Monetary(string="Amount", currency_field='currency_id', required=True)
              
    
    @api.model
    def create(self, vals):
        if vals['amount'] <= 0:
            raise ValidationError('The of amount add price should be more than zero')
        return super(AddPrice, self).create(vals)
        
    
class PostReceipt(models.TransientModel):
    _name = "tms.post.receipt"
    _description = "Post receipt to client" 
    
    
    resv2_name = fields.Char(string="Actual Recipient", required=True)
    resv2_id = fields.Char(string="ID", required=True)
    resv2_mobile = fields.Char(string="Mobile", required=True)
    resv2_country = fields.Char(string="Country")
    
    @api.model
    def default_get(self, fields):
        rec = super(PostReceipt, self).default_get(fields)
        active_id = self._context.get('active_id')

        # Check for selected invoices ids
        if not active_id:
            raise UserError(_("Programmation error: wizard action executed without active_id in context."))

        receipt = self.env['tms.receipt'].browse(active_id)[0]
        
        rec.update({
            'resv2_name': receipt.resv1_name,
            'resv2_mobile': receipt.resv1_mobile,
            'resv2_country': receipt.resv1_country,
            'resv2_id': False})
        return rec
    

    
    def post_receipt(self):
        
        active_id = self._context.get('active_id')
        
        if not active_id:
            raise UserError(_("Programmation error: wizard action executed without active_id in context."))
        
        receipt = self.env['tms.receipt'].browse(active_id)[0]
         
        res = {
            'posted_date': fields.Datetime.now(),
            'posted_by': self.env.uid,
            'resv2_name': self.resv2_name,
            'resv2_mobile': self.resv2_mobile,
            'resv2_country': self.resv2_country,
            'resv2_id': self.resv2_id,
            }
        
        receipt.action_post(res)
        """
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }"""
        """return { 'type' :  'ir.actions.act_close_wizard_and_refresh_view' }"""
    
    
class ReceiptActivity(models.Model):
        _name = "tms.receipt.activity"
        _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
        
        receipt_id =  fields.Many2one('tms.receipt', tracking=True)
        in_comment = fields.Text(string='System Comment', tracking=True, readonly=True)
        
        def name_get(self):
            result = []
            for a in self:
                result.append((a.id, "%s" % (str(a.id))))
            return result
        
    
class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    
    def send_mail(self, auto_commit=False):
        context = self._context
        if context.get('default_model') == 'tms.receipt' and \
                context.get('default_res_id') and context.get('mark_receipt_as_sent'):
            receipt = self.env['tms.receipt'].browse(context['default_res_id'])
            receipt = receipt.with_context(mail_post_autofollow=True)
            receipt.sent = True
            receipt.message_post(body=_("Invoice sent"))
        return super(MailComposeMessage, self).send_mail(auto_commit=auto_commit)


class ChangeReceiptPrice(models.TransientModel):
    _name = "tms.change.receipt.price"
    _description = "Change receipt receipt" 
    
    
    price = fields.Float(string="New Price", required=True)
    with_tax = fields.Boolean(string="With Tax")
    actual_price = fields.Float(string="Actual Price", readonly=True, store=False)
    receipt_id = fields.Many2one('tms.receipt')
    hide_tax = fields.Boolean(compute='_hide_tax')
    
    @api.onchange('price', 'with_tax')
    def on_price_changed(self):
        tax_id = self.receipt_id.tax_id
        tax_amount = 0.0
        if self.price and tax_id and self.receipt_id.amount_tax > 0 and not self.with_tax:
            tax_amount = tax_id._compute_amount(self.price, self.price, partner=self.receipt_id.partner_id or self.receipt_id.c_partner_id)
        
        self.actual_price = self.with_tax and self.price or (self.price + tax_amount)
    
        
    
    def post_receipt(self):
        receipt_id = self.receipt_id
        
        if not self.env.user.has_group("tms.group_tms_change_receipt_price"):
            raise UserError(_("You have no permission to change the receipt price!"))
        
        if receipt_id.state =='c':
            raise UserError(_("You can not change price of cancelled receipt!"))
        
        # if receipt_id.amove_id:
        #     raise UserError(_("The receipt was posted to accounting!"))
        
        # if receipt_id.invoice_id:
        #     raise UserError(_("The receipt was posted to accounting!"))
        
        if receipt_id.add_price_ids:
            receipt_id.add_price_ids.unlink()
        
        ret = {'manual_price': self.price,'is_manual_price': True,
                'amount_untaxed': self.price, 'amount_total': self.price,
                'amount_tax': 0, 'add_price': 0}   
        
        if receipt_id.amount_tax>0 and self.with_tax:
            price_taxed = receipt_id._compute_tax_inc(self.price)
            price_untaxed = self.price - price_taxed
            ret['amount_untaxed'] = price_untaxed
            ret['amount_tax'] = price_taxed
            
            
        elif receipt_id.amount_tax>0:
            ret['amount_tax'] = receipt_id._compute_tax(ret['amount_untaxed']) if not receipt_id.branch_to_id.zero_tax_to and ret['amount_untaxed'] > 0 else 0.0
            ret['amount_total'] = self.price + ret['amount_tax']
            ret['manual_price'] = ret['amount_total']
        
        receipt_price = receipt_id.receipt_price
        
        discount_amount =  receipt_price - ret['amount_untaxed']  if receipt_price >  ret['amount_untaxed'] else 0
        discount = discount_amount/receipt_price * 100.0 if discount_amount > 0 else 0
        ret['discount'] =  discount
        ret['discount_amount'] =  discount_amount
        ret['discount_type'] =  '2' if discount_amount > 0 else '0'
        ret['residual'] = ret['amount_total']
        
        if receipt_id.shipping_type == '2':
            ret['go_price'] =  ret['amount_total'] * .55
            ret['return_price'] =  ret['amount_total'] - ret['go_price']
            
        
        
        receipt_id._compute_residual(ret)
        
        if ret['residual'] < 0:
            raise ValidationError(_("You should make cancel the receipt payments before change the price!"))
        
        new_receipt_price = ret['amount_untaxed']
        ret['price_diff'] = new_receipt_price - receipt_id.receipt_price
        
        
        
        ctx = dict(self._context)
        ctx.update({'validate': False, 'edit': 1})
        receipt_id.with_context(ctx).super_write(ret)
        if receipt_id.invoice_id:
            receipt_id.invoice_id.button_draft()
            receipt_id.invoice_id.button_cancel()
            receipt_id.invoice_id= False
            receipt_id.create_invoice()
        
    
    
    def _hide_tax(self):
        self.hide_tax = self.receipt_id.amount_tax == 0
