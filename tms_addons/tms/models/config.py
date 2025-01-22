# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError
from odoo.osv import expression
import logging

_logger = logging.getLogger(__name__)

def _return_int_if(s):
    
    try:
        return int(s) # for int, long and float
    except ValueError:
        try:
            complex(s) # for complex
        except ValueError:
            pass
    return False


class State(models.Model):
    _name = 'tms.state'
    
    name = fields.Char(string='Name', required=True, translate=True, index=True)
    city_ids = fields.One2many('tms.city', 'state_id', string='Cities', readonly=True)
    
    # 
    def name_get(self):
        result = []
        for state in self:
            result.append((state.id,  state.name))
        return result    

class City(models.Model):
    _name = 'tms.city'

    # 
    def _get_city_ids(self):
        
        pass

    
    code = fields.Char(string='Code', required=True, index=True, copy=False)
    
    name = fields.Char(string='Name', required=True, translate=True, index=True)
    state_id = fields.Many2one('tms.state', string='State', required=True)
    trip_disabled = fields.Boolean(string="Disable on Trips", default=False)
    branch_ids = fields.One2many('tms.branch', 'city_id', string='Branches', readonly=True)
    
    prices_ids = fields.One2many('tms.freight.price', 'city_id', string='Freight Prices')
    
    manual_price = fields.Boolean(string='Is Manual Price')
    
    # 
    @api.constrains('code')
    def _check_ssn(self):
        for c in self:
            if c.code:
                count = self.search([('id', '!=', c.id if c.id else 0), ('code', '=', c.code)], limit=1)
                if len(count) > 0:
                    raise ValidationError(_('City code already exist'))
    
    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=like', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        obj = self.search(domain + args, limit=limit)
        return obj.name_get()
    
    # 
    def action_validate_distance(self):
        distance_map = {}
        distances = self.env['tms.freight.price'].search([]) 
        mising = []
        for d in distances:
            if d.distance > 0:
                key1 = str(d.city_id.id)+"-"+str(d.city_to_id.id)
                key2 = str(d.city_to_id.id)+"-"+str(d.city_id.id)
                distance_map.update({key1: d.distance, key2: d.distance})
        
        for d in distances:
            if d.distance <= 0:
                key1 = str(d.city_id.id)+"-"+str(d.city_to_id.id)
                key2 = str(d.city_to_id.id)+"-"+str(d.city_id.id)
                distance = distance_map.get(key1)
                if distance:
                    d.write({'distance': distance})
                else:
                    mising.append("%s -> %s" % (d.city_id.name, d.city_to_id.name))
                
        try:
            self._cr.commit()
        except:
            pass
        
        if mising:    
            raise ValidationError("Those cities are missing distance: %s" % mising)
                
        
        
    """
    
    def name_get(self):
        result = []
        for city in self:
            result.append((city.id,  city.name))
        return result
    """
    #city_ids = fields.Integer(compute=_get_city_ids, readonly=True, store=False)
    
class FreightPrice(models.Model):
    _name = 'tms.freight.price'
    
    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id
    
    city_id = fields.Many2one('tms.city', string='City', required=True)
    city_to_id = fields.Many2one('tms.city', string='To City', required=True)
    
    one_way_price = fields.Monetary(string="One Way Price", currency_field='currency_id')   
    two_way_price = fields.Monetary(string="Two Way Price", currency_field='currency_id')   
    show_room_price = fields.Monetary(string="Show Room Price", currency_field='currency_id')
    gove_price = fields.Monetary(string="Government Price", currency_field='currency_id')
    
    distance = fields.Float(string="Distance in KM")
    duration = fields.Float(string="Duration")
    currency_id = fields.Many2one('res.currency', default=_default_currency, string="Company Currency", readonly=True)
    
    _sql_constraints = [('freight_city_unique', 'unique(city_id,city_to_id)', 'City duplicated')]
    
#    def comput_distance_price


BRANCH_SQE_INDEX = {'trip_seq_id': 1, 
                 'batch_payment_seq_id': 2,
                'batch_post_seq_id': 3,
                 'batch_print_seq_id': 4}

class Branch(models.Model):
    _name = 'tms.branch'
    
    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id
    
    @api.depends('code')
    def _comput_code_str(self):
        for b in self:
            b.code_str = str(b.code) 
            
    
    code = fields.Char(string='Code', required=True, index=True, copy=False)
        
    name = fields.Char(string='Name', required=True, translate=True, index=True)
    city_id = fields.Many2one('tms.city', string='City',  required=True)
    state_id = fields.Many2one('tms.state', string='State', related="city_id.state_id", store=True,  readonly=True)
    address = fields.Text(string='Address', translate=True)
    
    allow_go_back = fields.Boolean(string="Allow Go And Back", default=True)
    show_in_fright = fields.Boolean(string="Disable in fright", default=False)
    zero_tax_to = fields.Boolean(string='Zero Tax To' )
    
    ac_cash_id = fields.Many2one('account.account', string='Cash Account',  required=False)
    ac_income_id = fields.Many2one('account.account', string='Income Account',  required=False)
    ac_rece_id = fields.Many2one('account.account', string='Branch Receivable Account',  required=False)
    ac_discount_id = fields.Many2one('account.account', string='Discount Account',  required=False)
    ac_expense_id = fields.Many2one('account.account', string='Expense Account',  required=False)
    ac_advance_income_id = fields.Many2one('account.account', string='Advance Income Account',  required=False)
    ac_comp_cash_id = fields.Many2one('account.account', string='Companies Cash Account',  required=False)
    tax_id = fields.Many2one('account.tax', 'Account Tax')
    
    costcenter1_id = fields.Many2one('account.analytic.account', string='Costcenter1',  required=False)
    costcenter2_id = fields.Many2one('account.analytic.account', string='Costcenter2')
    
    bank_journal_id = fields.Many2one('account.journal', string='Bank Journal', domain=[('type', '=', 'bank')])
    
    commission_rate = fields.Float(string="Commission Rate")
    minimum_target = fields.Monetary(string="Minimum target value", currency_field='currency_id')
    
    responsible_id = fields.Many2one('res.users', string='Branch Responsible',  required=False)
    manager_id = fields.Many2one('res.users', string='Branch Manager')
    
    branch_dest_ids = fields.One2many('tms.branch.dest', 'branch_id', string='Branch Route Destination')
    currency_id = fields.Many2one('res.currency', default=_default_currency, string="Company Currency", readonly=True)
        
    trip_seq_id = fields.Many2one('ir.sequence', string='Trip Sequence', copy=False)
    batch_payment_seq_id = fields.Many2one('ir.sequence', help='Batch Payment Sequence', copy=False)
    batch_post_seq_id = fields.Many2one('ir.sequence', help='Batch Post Sequence', copy=False)
    batch_print_seq_id = fields.Many2one('ir.sequence', help='Batch Print Sequence', copy=False)
    invoice_sec_id = fields.Many2one('ir.sequence', string="Invoice Sequence", copy=False)
            
    partner_id = fields.Many2one('res.partner',"Partner", domain=[('is_company', '=', True), ('customer', '=', False)],
                                 context={'is_company': True, 'default_is_company': True,
                                           'customer': False, 'default_customer': False})
    
    active = fields.Boolean(default=True)
    lat = fields.Float("Latitude", digits=(16, 5))
    lng = fields.Float("Longitude", digits=(16, 5))
    map_link = fields.Html('', compute='_map_link');
    @api.depends('city_id')
    @api.constrains('code')
    def _check_ssn(self):
        for c in self:
            if c.code:
                count = self.search([('id', '!=', c.id if c.id else 0), ('code', '=', c.code)], limit=1)
                if len(count) > 0:
                    raise ValidationError(_('Branch code already exist'))
    
    def name_get(self):
        result = []
        for branch in self:
            result.append((branch.id,  branch.name))
        return result

    @api.model
    def create(self, vals):
        
        """
        trip_seq_id = self._create_sequence(vals, 1).id
        batch_payment_seq_id = self._create_sequence(vals, 2).id
        batch_post_seq_id = self._create_sequence(vals, 3).id
        batch_print_seq_id = self._create_sequence(vals, 4).id
        
        vals.update({'trip_seq_id': trip_seq_id,
                     'batch_payment_seq_id': batch_payment_seq_id,
                     'batch_post_seq_id': batch_post_seq_id,
                     'batch_print_seq_id': batch_print_seq_id})
        """
        
        branch = super(Branch, self).create(vals)
        return branch
    
    
    
    def write(self, vals):
        
        if ('city_id' in vals or 'code' in vals) and (not self._context.get('model', False)):
            if 'city_id' in vals:
                del vals['city_id']
            if 'code' in vals:
                del vals['code']
            if not vals:
                return True
        
        for b in self:
            if ('code' in vals and b.code != vals['code']):
                if self.env['tms.trip'].search([('branch_id', 'in', self.ids)], limit=1):
                    raise UserError(_('This branch already contains items, therefore you cannot modify its code.'))
                code = vals['code']
                if b.trip_seq_id:
                    b.trip_seq_id.write({'prefix': "%s1" % code})
                if b.batch_payment_seq_id:
                    b.batch_payment_seq_id.write({'prefix': "%s2" % code})
                if b.batch_post_seq_id:
                    b.batch_post_seq_id.write({'prefix': "%s3" % code})
                if b.batch_print_seq_id:
                    b.batch_print_seq_id.write({'prefix': "%s4" % code})
                
            
        result = super(Branch, self).write(vals)
        return result
    
    def get_sequence(self, name):
        #from operator import gett 
        sequence = getattr(self, name)
        if not sequence:
            sequence =  self.sudo()._create_sequence({'name': self.name, 'code': self.code}, BRANCH_SQE_INDEX[name])
            self.sudo().write({name: sequence.id})
        return sequence.sudo() 
    
    def next_sequence(self, name):  
        return self.get_sequence(name)._next()
            
    
    def _create_sequence(self, vals, index):
        """ Create new no_gap entry sequence for every new Journal"""
        prefix = "%s%s" % (str(vals['code']), str(index))
        name = "%s.%s" % (str(vals['name']), str(index))
        seq = {
            'name': name,
            'implementation': 'no_gap',
            'prefix': prefix,
            'padding': 0,
            'number_increment': 1,
            'use_date_range': False,
        }
        if 'company_id' in vals:
            seq['company_id'] = vals['company_id']
        seq = self.env['ir.sequence'].create(seq)
        return seq
    
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        context = dict(self.env.context)
        newself = self
        domain = []
        if name:
            domain = ['|', ('code', '=like', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:] 
        
        if context.pop('user_preference', None) and not self.env.user.all_branches:
            # We browse as superuser. Otherwise, the user would be able to
            # select only the currently visible branches (according to rules,
            # which are probably to allow to see the child branches) even if
            # she belongs to some other branches.
            branches = self.env.user.branch_id + self.env.user.branch_ids
            args = (args or []) + [('id', 'in', branches.ids)]
            newself = newself.sudo()
        
        obj = newself.with_context(context).search(domain + (args or []), limit=limit)
        return obj.name_get()  
    
    
    def check_count(self):
        qq = 'SELECT id FROM tms_receipt WHERE branch_id IN %s OR branch_to_id IN %s LIMIT 1'
        self.env.cr.execute(qq, (tuple(self.ids), tuple(self.ids)))
        count = 0
        for st in self.env.cr.dictfetchall():
            count = 1
        return count
    
    def get_invoice_sec_id(self):
        if not self.invoice_sec_id:
            vals = {'name': self.name, 'code': self.code}
            self.invoice_sec_id = self._create_sequence(vals, 5).id
            super(Branch, self).write({'invoice_sec_id': self.invoice_sec_id.id})
        
        return self.invoice_sec_id
    
    @api.onchange('lat', 'lon')
    def on_map_link(self):
        self._map_link()
    
    
    def _map_link(self):
        if self.lat and self.lng:
            self.map_link = '<a href="javascript:window.open(\'https://maps.google.com/?q=%s,%s\',\'tms_google_map\',\'resizable,height=260,width=370\'); return false;" > %s </a>' % (self.lat, self.lng, _('Show Map'))
 
class BranchDest(models.Model):
    _name = 'tms.branch.dest'
    
    branch_id = fields.Many2one('tms.branch', string='Branch', required=True)
    branch_to_id = fields.Many2one('tms.branch', string='To Branch', required=True)
    duration = fields.Float(string='Duration in Hours', required=True)

     
class Move(models.Model):
    _name = 'tms.move'
    
    code = fields.Char(string='Code', required=True, index=True, copy=False)
    name = fields.Char(string='Name', required=True, translate=True, index=True, search='_search_all_fields')
    
    branch_id = fields.Many2one('tms.branch', string='Branch', required=True, default=lambda self: self.env.user.branch_id, context={'user_preference': True})
    
    is_manual = fields.Boolean(string='Manual', default=False)
    is_comp = fields.Boolean(string='Company', default=False)
        
    receipt_sec_id = fields.Many2one('ir.sequence', string='Receipt Sequence', copy=False)
    post_sec_id = fields.Many2one('ir.sequence', string="Post Sequence",  copy=False)
    payment_sec_id = fields.Many2one('ir.sequence', string="Payment Sequence", copy=False)
    trans_sec_id = fields.Many2one('ir.sequence', string="Payment Sequence", copy=False)
    cancel_sec_id = fields.Many2one('ir.sequence', string="Payment Sequence", copy=False)
    cancel_payment_sec_id = fields.Many2one('ir.sequence', string="Cancel Payment Sequence", copy=False)
    
    
    
    padding = fields.Integer(default=8, required=True, string="Padding", help='Count of chars on right sequence ')
    
    
    @api.constrains('code')
    def _check_code(self):
        for c in self:
            if c.code:
                count = self.search([('id', '!=', c.id if c.id else 0), ('code', '=', c.code)], limit=1)
                if len(count) > 0:
                    raise ValidationError(_('Move code already exist'))
    
    
    @api.constrains('branch_id')
    def _check_branch(self):
        """
        c = self
        domain = [('id', '!=', c.id if c.id else 0), ('branch_id', '=', c.branch_id), ('type', '=', c.type)] 
        if c.account_id:
            domain.append(('account_id', '!=', False))
        count = self.search(domain, limit=1, count=True)
        if count > 0:
            raise ValidationError(_('Move already exist for the same settings'))
        """
        pass
            
    
    
    def name_get(self):
        result = []
        for move in self:
            result.append((move.id, "%s  %s" % (move.code, move.name)))
        return result
    
    def _search_all_fields(self, operator, value):
        if operator == 'like':
            operator = 'ilike'
        return ['|', ('code', '=', value), ('name', operator, value)]

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=like', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        obj = self.search(domain + args, limit=limit)
        return obj.name_get()
    
    
    def write(self, vals):
        for move in self:
            if ('code' in vals and move.code != vals['code'] or 'padding' in vals):
                """
                if self.env['tms.receipt'].search([('move_id', 'in', self.ids)], limit=1):
                    raise UserError(_('This move already contains items, therefore you cannot modify its code.'))
                """                
                padding = vals['padding'] if 'padding' in vals else move.padding
                code = vals['code'] if 'code' in vals else move.code
                
                move.receipt_sec_id.write({'prefix': "%s1" % code, 'padding':  padding})
                move.post_sec_id.write({'prefix': "%s2" % code, 'padding':  padding})
                move.payment_sec_id.write({'prefix': "%s3" % code, 'padding':  padding})
                move.trans_sec_id.write({'prefix': "%s4" % code, 'padding':  padding})
                move.cancel_sec_id.write({'prefix': "%s5" % code, 'padding':  padding})
                move.cancel_payment_sec_id.write({'prefix': "%s6" % code, 'padding':  padding})
                
        result = super(Move, self).write(vals)
        return result
            
    @api.model
    def create(self, vals):
        
        receipt_sec_id = self._create_sequence(vals, 1).id
        post_sec_id = self._create_sequence(vals, 2).id
        payment_sec_id = self._create_sequence(vals, 3).id
        trans_sec_id = self._create_sequence(vals, 4).id
        cancel_sec_id = self._create_sequence(vals, 5).id
        cancel_payment_sec_id = self._create_sequence(vals, 6).id
        
        
        vals.update({'receipt_sec_id': receipt_sec_id,
                     'post_sec_id': post_sec_id,
                     'payment_sec_id': payment_sec_id,
                     'trans_sec_id': trans_sec_id,
                     'cancel_sec_id': cancel_sec_id,
                     'cancel_payment_sec_id': cancel_payment_sec_id})
        
        move = super(Move, self).create(vals)
        return move
        
    def _create_sequence(self, vals, index):
        """ Create new no_gap entry sequence for every new Journal"""
        prefix = "%s%s" % (str(vals['code']), str(index))
        name = "%s.%s" % (str(vals['name']), str(index))
        seq = {
            'name': name,
            'implementation': 'no_gap',
            'prefix': prefix,
            'padding': vals['padding'],
            'number_increment': 1,
            'use_date_range': False,
        }
        if 'company_id' in vals:
            seq['company_id'] = vals['company_id']
        seq = self.env['ir.sequence'].create(seq)
        return seq

    
class CarType(models.Model):
    _name = 'tms.car.type'
    
    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id
    
    name = fields.Char(string='Name', required=True, translate=True, index=True)
    value = fields.Monetary(string="Value", currency_field='currency_id', required=True, store=True)
    currency_id = fields.Many2one('res.currency', default=_default_currency, string="Company Currency", readonly=True)
    img = fields.Binary()

class CarState(models.Model):
    _name = 'tms.car.state'
    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id
    
    name = fields.Char(string='Name', required=True, translate=True, index=True)
    value = fields.Monetary(string="Value", currency_field='currency_id', required=True, store=True)
    currency_id = fields.Many2one('res.currency', default=_default_currency, string="Company Currency", readonly=True)

class FreightState(models.Model):
    _name = 'tms.freight.state'  
    
    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id
    
    name = fields.Char(string='Name', required=True, translate=True, index=True)
    value = fields.Monetary(string="Value", currency_field='currency_id', required=True, store=True)
    currency_id = fields.Many2one('res.currency', default=_default_currency, string="Company Currency", readonly=True)
    _sql_constraints = [('freight_state_name_unique', 'unique(name)', 'Fright state name duplicated')]
   

class CarBrand(models.Model):
    _name = 'tms.cbrand'
    
    code = fields.Char(string='Code', required=True, index=True, copy=False)
    name = fields.Char(string='Name', required=True, translate=True)
    model_ids = fields.One2many('tms.cmodel', 'brand_id', string='Models')
    
    
    
    @api.constrains('code')
    def _check_ssn(self):
        for c in self:
            if c.code:
                count = self.search([('id', '!=', c.id if c.id else 0), ('code', '=', c.code)], limit=1)
                if len(count) > 0:
                    raise ValidationError(_('Car brand code already exist'))
    
    
    def name_get(self):
        result = []
        for brand in self:
            result.append((brand.id, "%s - %s" % (brand.code, brand.name)))
                          
        return result 
    
    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=like', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        obj = self.search(domain + args, limit=limit)
        return obj.name_get()

class CarModel(models.Model):
    _name = 'tms.cmodel'
    
    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id
    
    
    code = fields.Char(string='Code', required=True, index=True, copy=False)
    name = fields.Char(string='Name', required=True, translate=True)
    brand_id = fields.Many2one('tms.cbrand', required=True)
    car_type_id = fields.Many2one('tms.car.type', required=True)
    
    value = fields.Monetary(string="Value", related='car_type_id.value', currency_field='currency_id', readonly=True)
    
    currency_id = fields.Many2one('res.currency', default=_default_currency, string="Company Currency", readonly=True)
    
    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('code', '=like', name + '%'), ('name', operator, name)]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        obj = self.search(domain + args, limit=limit)
        return obj.name_get()

class Truck(models.Model):
    _name = 'tms.truck'
    
    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id
    
    def _get_branch(self):
        return self.env.user.branch_id
    
    def _truck_domain(self):
        d = [('is_driver', '=', True), ('truck_id', '=', False)]
        
        return d
    
    code = fields.Char(string='Code', required=True, index=True, copy=False)
    name = fields.Char(string='Name', required=True, translate=True, index=True)
    
    plate_number = fields.Char(string='Plate Number', required=True)
    
    asset_id = fields.Many2one('account.asset', string='Asset')
    tender_asset_id = fields.Many2one('account.asset', string='Tender')
    driver_id = fields.Many2one('hr.employee', domain=['&', ('is_driver', '=', True), ('truck_id', '=', False)])
    km_price = fields.Monetary(string="KM Price")
    costcenter_id = fields.Many2one('account.analytic.account', context={'analytic2':1})
    company_owned = fields.Boolean(string='Company Owned')
    minimum_target = fields.Monetary(string="Minimum target value", currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=_default_currency, string="Company Currency", readonly=True)
    
    branch_id = fields.Many2one('tms.branch', string='Current Branch')
    city_id = fields.Many2one('tms.city', string='Current City')
    truck_type_id = fields.Many2one('tms.truck.type', string='Truck Type')
    #trip_ids = fields.One2many('tms.trip', 'truck_id', string='Trips', readonly=True)
    trips_count = fields.Integer(compute='_compute_trip_count', string='Trips')
    active_trip_id = fields.Many2one('tms.trip', string='Current Trip')
    max_cars = fields.Integer(string="Max Cars", default=8)
    
    lat = fields.Float("Latitude", digits=(16, 5))
    lng = fields.Float("Longitude", digits=(16, 5))
    
    map_link = fields.Html('', compute='_map_link');
    
    @api.model
    def create(self, vals):
        truck = super(Truck, self).create(vals)
        truck.driver_id.write({'truck_id': truck.id})
        return truck
    
    
    def write(self, vals):
        if 'driver_id' in vals:
            for t in self:
                t.driver_id.write({'truck_id': False})
                self.env['hr.employee'].browse(vals['driver_id']).write({'truck_id': t.id})
        return super(Truck, self).write(vals)
    
    
    def unlink(self):
        for t in self:
            t.driver_id.write({'truck_id': False})
        return super(Truck, self).unlink()
    
    @api.onchange('code')
    def _code_change(self):
        ddomain =['&', ('is_driver', '=', True), ('truck_id', '=', False)]
        if self.id:
            ddomain =['|', '&', ('is_driver', '=', True), ('truck_id', '=', False), '&', ('is_driver', '=', True), ('truck_id', '=', self.id)]
        
        return  {'domain': {'driver_id': ddomain}}
        
    
    def action_reset_trip(self):
        if self.active_trip_id and self.active_trip_id.state in ['a', 'e', 'c']:
            self.write({'active_trip_id': False})
    
    
    
    
    @api.constrains('code')
    def _check_code(self):
        for c in self:
            if c.code:
                count = self.search([('id', '!=', c.id if c.id else 0), ('code', '=', c.code)], limit=1)
                if len(count) > 0:
                    raise ValidationError(_('Truck code already exist'))
    
    
    def _compute_trip_count(self):
        #for truck in self:
        self.trips_count = 0 #self.env['tms.trip'].search_count([('vehicle_id', '=', self.id)])
    
    
    def name_get(self):
        result = []
        show_driver = self._context.get("show_driver", False)
        for truck in self:
            if show_driver and truck.driver_id:
                result.append((truck.id, '%s - %s' % (truck.name, truck.driver_id.name)))
            else:
                result.append((truck.id, '%s - %s' %(truck.code, truck.name)))
                          
        return result   
     
    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', '|', ('code', '=like', name + '%'), ('name', operator, name), ('driver_id.name', '=like', name + '%')]
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = ['&', '!'] + domain[1:]
        obj = self.sudo().search(domain + args, limit=limit)
        return obj.name_get()
    
    can_reset_trip = fields.Boolean(compute='_can_reset_trip')
    
    
    def _can_reset_trip(self):
        self.can_reset_trip = self.active_trip_id and self.active_trip_id.state in ['a', 'e', 'c']
    
    
    
    @api.onchange('lat', 'lon')
    def _map_link(self):
        if self.lat and self.lng:
            self.map_link = '<a href="#" onClick="window.open(\'https://maps.google.com/?q=%s,%s\',\'tms_google_map\',\'resizable,height=260,width=370\'); return false;" > %s </a>' % (self.lat, self.lng, _('Show Map'))

class TruckType(models.Model):
    _name = 'tms.truck.type'
    
    name = fields.Char("Type", required=True)
    rate = fields.Float(digits=(0,2))
    capacity = fields.Integer()
    
    
    @api.constrains('name')
    def _check_name(self):
        for c in self:
            if c.name:
                count = self.search([('id', '!=', c.id if c.id else 0), ('name', '=', c.name)], limit=1)
                if len(count) > 0:
                    raise ValidationError(_('Truck type already exists!'))
    
    
    @api.model
    def compute_expense(self, branch_id, branch_to_id):
        domain = ['|', '&', '&', ('truck_type', '=', self.id), ('branch_id', '=', branch_id.id), ('branch_to_id', '=', branch_to_id.id),
                      '&', '&', ('truck_type', '=', self.id), ('branch_id', '=', branch_to_id.id), ('branch_to_id', '=', branch_id.id)]
        expense = self.env['tms.driver.expense.calc'].search(domain, limit=1)
        if expense:
            expense._compute_expense()
        return expense
    
class DriverExpenseCalc(models.Model):
    _name = 'tms.driver.expense.calc'
    _order = 'branch_id, truck_type'
    branch_id = fields.Many2one("tms.branch", "From", required=True)
    branch_to_id = fields.Many2one("tms.branch", "To", required=True)
    truck_type = fields.Many2one("tms.truck.type", "Type", required=True)
    distance = fields.Float()
    time = fields.Float()
    rate = fields.Float(related="truck_type.rate", readonly=True, store=True)
    expense = fields.Float(digits=(16,0), compute='_compute_expense', readonly=True)
    
    
    @api.constrains('truck_type')
    def _check_truck_type(self):
        for c in self:
            domain = ['|', '&', '&', ('truck_type', '=', c.truck_type.id), ('branch_id', '=', c.branch_id.id), ('branch_to_id', '=', c.branch_to_id.id),
                      '&', '&', ('truck_type', '=', c.truck_type.id), ('branch_id', '=', c.branch_to_id.id), ('branch_to_id', '=', c.branch_id.id)]
            count = self.search(domain)
            if len(count) > 1:
                raise ValidationError(_('Truck expense (%s -> %s) already exists!') % (c.branch_id.name, c.branch_to_id.name))
            #if len(count2) > 1 or (len(count2) > 0 and  len(count1) > 0):
            #    raise ValidationError(_('Truck expense (%s -> %s) already exists!') % (c.branch_to_id.name, c.branch_id.name))
            
    
    
    def name_get(self):
        result = []
        for c in self:
            result.append((c.id, '%s <-> %s (%s)' % (c.branch_id.name, c.branch_to_id.name, c.truck_type.name)))
        
        return result
    
    def _compute_expense(self):
        for r in self:
            r.expense = round(r.rate * r.distance * 2, 0)/2
    
    @api.onchange('distance', 'rate')
    def distance_rate_changed(self):
        self.expense = round(self.rate * self.distance * 2, 0)/2
    

class Ground(models.Model):
    _name = 'tms.ground'  
    
    name = fields.Char(string='Name', required=True, translate=True, index=True)
    ground_ids = fields.One2many('tms.ground.price', 'ground_id', string='Ground Price')

    
class GroundPrice(models.Model):
    _name = 'tms.ground.price'
    _order = 'days, price'  
    
    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id   
        
    ground_id = fields.Many2one('tms.ground', string='Ground', required=True)
    days = fields.Integer(string='Days', required=True)
    price = fields.Monetary(string="Price", required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=_default_currency, string="Company Currency", readonly=True)

 
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: