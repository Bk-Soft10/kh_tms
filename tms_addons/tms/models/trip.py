
from werkzeug.urls import url_encode

from odoo import api, exceptions, fields, models, _

import datetime

from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError

from odoo.addons import decimal_precision as dp
import logging

from . import common

_logger = logging.getLogger(__name__)


BLOCKED_FIELDS = ['driver_expense', 'rent_expense', 'other_expense']

class Trip(models.Model):

    _name = "tms.trip"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = "id desc"
    
    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id
    
    
    @api.depends('city_id')
    def _get_current_city(self):
        return self.cur_branch_id.city_id if self.cur_branch_id else False
    
    def _get_branch(self):
        return self.cur_branch_id
    
    def _receipt_route_active_domain(self):
        return 
    
    trip_no = fields.Char(string="Trip Number", readonly=True)
    
    branch_id = fields.Many2one('tms.branch', string='From Branch', readonly=True, default= lambda self: self.env.user.branch_id )
    
    city_id = fields.Many2one('tms.city', string='From City', readonly=True, default= lambda self: self.env.user.branch_id.city_id, store=True )
    
    branch_to_id = fields.Many2one('tms.branch', string='To Branch', required=True, )
    
    city_to_id = fields.Many2one('tms.city', string='To City', required=True, domain=[('trip_disabled', '=', False)])
    
    next_branch_id = fields.Integer(string='Nex Branch', readonly=True, default=0)
    
    note = fields.Text(string='Note')
    
    truck_id = fields.Many2one('tms.truck', string='Truck', required=False, )
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', required=False, )
    driver = fields.Many2one(related='truck_id.driver_id')
    plate_no = fields.Char(related='truck_id.plate_number')
    driver_id = fields.Many2one('res.partner', string='Driver')
    
    driver_mobile = fields.Char(string='Driver Mobile', compute='_get_driver_mobile', store=True, readonly=True, states={'b': [('readonly', False)], 'r': [('readonly', False)], 't': [('readonly', False)]})
    
    distance = fields.Float(string='Distance', )
    
    duration = fields.Float(string='Duration', )
    
    departure_date = fields.Datetime(string='Departure Date', readonly=True)
    
    last_departure_date = fields.Datetime(string='Last Departure Date', readonly=True)
    
    date = fields.Date(compute='_compute_date', store=True)
    
    expected_arrival = fields.Datetime(string='Expected ِ arrival')
    
    arrival_date = fields.Datetime(string='Arrival Date', readonly=True)
    
    driver_expense = fields.Monetary(string="Driver Expense", currency_field='currency_id', required=True, )
    
    rent_expense = fields.Monetary(string="Rent Expense", currency_field='currency_id', )
    
    other_expense = fields.Monetary(string="Other Expense", currency_field='currency_id', tracking=True, )
    
    total_expense = fields.Monetary(string="Total Expense", compute='_compute_expense', currency_field='currency_id')
    
    trip_revenue = fields.Monetary(string="Trip Revenue", compute='_compute_balance', currency_field='currency_id')
    
    trip_balance = fields.Monetary(string="Trip Balance", compute='_compute_balance', currency_field='currency_id')  
    
    trip_route_ids = fields.One2many('tms.trip.route', 'trip_id', string='Trip Routes')
    
    all_receipt_route_ids = fields.One2many('tms.receipt.route', 'trip_id', string='Trip Routes', readonly=True, ondelete="cascade")
    
    receipt_route_ids = fields.One2many('tms.receipt.route', 'trip_id', string='Trip Routes', readonly=True, domain=[('trip_route_id', '=', False)])
            
    receipt_route_active_ids = fields.One2many('tms.receipt.route', 'trip_id', string='Active Receipts', domain=[('down_date', '=', False)], readonly=True)
    
    active_route_id = fields.Many2one('tms.trip.route', readonly=True, compute='_get_active_route')
    
    trip_route_count = fields.Integer(readonly=True,compute='_get_route_count')
    
    cur_branch_id = fields.Many2one('tms.branch', string='Current Branch', help='Current branch trip stay in', default=_get_branch)
    cur_city_id = fields.Many2one('tms.city', string='Current City', default=_get_current_city, store=True, help='City of current branch trip stay in')
    
    receipt_mapping_ids = fields.One2many('tms.trip.receipt.mapping', 'trip_id' , readonly=True, domain=[('trip_route_id', '=', False)])
    
    receipt_ids = fields.One2many('tms.receipt', 'trip_id', string='Reciepts', readonly=False)

    next_state = fields.Char(compute='_get_next_state')
    
    state = fields.Selection([
        ('b','Branch'),
        ('r', 'In Road'),
        ('t', 'Transient'),
        ('a', 'Arrival'),
        ('e', 'Ended'),
        ('c', 'Cancelled'),
    ], string='Status', index=True, readonly=True, default='b',
        tracking=True, copcancely=False, copy=False)
    
    currency_id = fields.Many2one('res.currency', default=_default_currency, string="Company Currency", readonly=True)
    
    can_arrive = fields.Boolean(compute='_can_arrive')
    can_takeoff = fields.Boolean(compute='_can_takeoff')
    can_stop_trip = fields.Boolean(compute='_can_stop_trip')
    can_cancel_trip = fields.Boolean(compute='_can_cancel_trip')
    can_upload = fields.Boolean(compute='_can_upload')
    can_print  = fields.Boolean(compute='_can_print')
    can_untakeoff  = fields.Boolean(compute='_can_untakeoff')
    
    trip_id = fields.Many2one('tms.trip', default='_get_self', store=False) 
    
    routes_html = fields.Text(compute='_compute_breadcrumb')
    
    routes_text = fields.Text(compute='_compute_route_text', store=True)
    
    branch_name = fields.Char(related='branch_id.name', readonly=True)
    
    car_count = fields.Integer(compute='_get_car_count', string="Car Count", store=True)
    
    is_internal = fields.Boolean(string='Internal Trip', )
    
    internal_type = fields.Selection([
        ("1",'Upload Cars'),
        ("2", 'Download Cars'),
    ], string='Internal Type',  default="1", )
    
    partner_id = fields.Many2one('res.partner', string='Client')
    resv2_name = fields.Char(string="Actual Recipient")
    resv2_id = fields.Char(string="ID")
    resv2_mobile = fields.Char(string="Mobile")
    
    takeoff_by = fields.Many2one('res.users', "Takeoff By")
    arrived_by = fields.Many2one('res.users', "Arrived By")
    
    calculated = fields.Boolean()
    posted = fields.Boolean()
    ignore = fields.Boolean()
    amove_id = fields.Many2one('account.move', string='Income Entry', readonly=True, ondelete='set null')
    emove_id = fields.Many2one('account.move', string='Journal Entry', readonly=True, ondelete='set null')
    expense_posted = fields.Boolean()
    calc_date = fields.Date("Calculated Date")
    
    can_change_expense = fields.Boolean(compute='_can_change_expense')
    auto_expensed =  fields.Integer(help="""Determine if current trip expense calculated automatically according to the expense table
                                            0: is not set
                                            1: is set to true
                                            2: is set to false""", default=0)
    
    total_income = fields.Float('Actual Income')
    virtual_income = fields.Float('Virtual Income')
    
    
    def _can_change_expense(self):
        self.can_change_expense = self.check_can_change_expense()
        
    
    def check_can_change_expense(self):
        t = self
        if t.expense_posted or t.state == 'c':
            return False
        if t.env.user.has_group('tms.group_tms_admin'):
            return True
        return t.auto_expensed == 2 and t.state == 'b'
                
    
    
    def _get_last_departure_date(self):
        for r in self:
            r.last_departure_date = r.departure_date 
        
    def _get_self(self):
        return self
    
    @api.onchange('city_id')
    def _city_changed(self):
        return {'domain': {}}

    def _compute_breadcrumb(self):
        for r in self:
            r.routes_html = r._trip_route_ids_changed()['value']['routes_html']
    
    
    def _get_car_count(self):
        for r in self:
            r.car_count = len(r.all_receipt_route_ids) if r.all_receipt_route_ids else 0
            
    @api.onchange('trip_route_ids')
    def _trip_route_ids_changed(self):
        style = """
        <link rel="stylesheet" href="tms/static/src/css/style.css">
"""
        
        active = self._get_active_route()
        
        current = self._get_current_route()
                
        first_sapn = '<span class="active">' if self.state == 'b' else '<span>'
        end_span = '</span>'
        if self.state != 'b' :
            end_span = '</span>'
        
        name = self.branch_id.name.replace("فرع ", "")
        
        routes_html = style + '<div class="head-routes"><div class="rbreadcrumb">'+first_sapn + name + end_span
        last_route = None
        for r in self.trip_route_ids:
            claz = 'active road' if self.state == 'r' else 'active'
            route = active or current
            span = ('<span class="%s">'%(claz,) if route and route.id == r.id else '<span>')
            end_span = '</span>'
            if r.arrival_date:
                end_span = '</span>'
            
            name = r.branch_to_id.name.replace("فرع ", "")
            
            routes_html += span + name + end_span
            last_route = r
        
        claz = 'active road' if self.state == 'r' else 'active'
        
        last_sapn = '<span class="%s">'%(claz,) if not active and self.state in ['r', 'a'] else '<span>'
        
        name = (self.branch_to_id.name or '').replace("فرع ", "")
        
        routes_html += last_sapn + name +'</span></div></div>'
                
        return {'value': {'routes_html': routes_html}}
    
    
    def _compute_route_text(self, ret=False):
        name = self.branch_id.name.replace("فرع ", "")
        for r in self.trip_route_ids:
            name = '%s-%s' % (name, r.branch_to_id.name.replace("فرع ", ""))
        name = '%s-%s' % (name, (self.branch_to_id.name or '').replace("فرع ", ""))
        
        if ret:
            return name
        self.routes_text = name
    
    
    def _get_route_text(self):
        routes = self.branch_id.name.replace("فرع ", "")
        for r in self.trip_route_ids:
            routes = '%s-%s' % (routes, r.branch_to_id.name.replace("فرع ", ""))
        routes = '%s-%s' % (routes, (self.branch_to_id.name or '').replace("فرع ", ""))
        
        return routes
    
    @api.depends('branch_to_id', 'city_to_id.branch_ids', 'city_id')
    @api.onchange('city_to_id')
    def _city_to_changed(self):
        domain = {'branch_to_id': [('id', '=', 0)]}
        value = {}
        has_city = False
        first_branch_id = False
        if self.city_to_id:
            ids = self.city_to_id.branch_ids.mapped('id')
            domain['branch_to_id'] = [('id', 'in', ids)]
            has_city = True if len(ids) > 0 else False
            first_branch_id = ids[0] if len(ids) == 1 else False
                
        if not has_city or not self.city_id:
            value = {'branch_to_id' : False, 'cur_city_id' : False, 'distance': False, 'duration': False, 'receipt_route_ids': []}
        else :
            distance , duration, expected_arrival = self._compute_arrival()
            value = {
                'distance': distance, 
                'duration': duration, 
                'expected_arrival': expected_arrival, 
                'branch_to_id': False,'receipt_route_ids': [] ,
                'driver_expense': distance * 0.65 
                }
            if first_branch_id:
                branch_id = self.env['tms.branch'].browse(first_branch_id)[0]
                value['branch_to_id'] = branch_id
                self.branch_to_id = first_branch_id
                
        
        routes = self._trip_route_ids_changed()['value'] 
        value.update(routes) 
        if self.is_internal:
            value.update({'branch_to_id': self.branch_id}) 
        
        return {'domain': domain, 'value': value}
    
    @api.depends('city_id', 'branch_id', 'city_to_id')
    @api.onchange('branch_to_id')
    def _branch_to_changed(self):
        value = {'receipt_route_ids': [(6, 0, [])]}
        routes = self._trip_route_ids_changed()['value']  
        value.update(routes) 
        return {'value': value}
    
    @api.onchange('driver_id')
    def _driver_changed(self):
        value = {'driver_mobile': self.driver_id.mobile}
        return {'value': value}
    
    @api.onchange('vehicle_id')
    def _vehicle_changed(self):
        driver_id = self.vehicle_id.sudo().driver_id
        value = {
            'driver_id': driver_id, 
            'driver_mobile': driver_id.mobile or '966'
        }
        
        return {'value': value}
    
    @api.depends('driver_id')
    
    def _get_driver_mobile(self):
        self.driver_mobile = self.driver_id.mobile if self.driver_id else self.driver_mobile
        
    @api.onchange('is_internal')
    @api.depends('trip_route_ids')
    def _is_internal_changed(self):
        if self.departure_date:
            if self.branch_id != self.branch_to_id or self.trip_route_ids:
                return {'value': {'is_internal': False, 'internal_type': "1"}}
            return {}
        if not self.is_internal:
            return {'value': {'internal_type': "1"}}
        return {'value': {'city_to_id': self.branch_id.city_id, 'branch_to_id': self.branch_id, 'trip_route_ids': [(6, 0, [])]}}
    
    
        
    def _compute_distance(self):
        pass
        
    def _compute_expense(self):
        for rec in self:
            rec.total_expense = 0
        
        pass
    
    def _compute_balance(self):
        pass
    
    @api.onchange('driver_expense', 'rent_expense', 'other_expense')
    def _expense_changed(self):
        
        total_expens = 0;
        if self.driver_expense:
            total_expens += self.driver_expense
        if self.rent_expense:
            total_expens += self.rent_expense
        if self.other_expense:
            total_expens += self.other_expense 
        self.total_expense = total_expens
        
        return {'value': {'total_expense': total_expens}}
    
    def _get_active_route(self):
        active_rout  = None
        if self.state == 'r' and self.trip_route_ids:
            for trip_route in self.trip_route_ids:
                if not trip_route.arrival_date:
                    if not active_rout:
                        active_rout = trip_route
                    elif trip_route.sequence < active_rout.sequence:
                        active_rout = trip_route
                    
        self.active_route_id = active_rout               
        return active_rout
    
    def _get_current_route(self):
        current_rout  = None
        if self.state == 't' and self.trip_route_ids:
            for trip_route in self.trip_route_ids:
                if trip_route.arrival_date:
                    current_rout = trip_route
                        
        return current_rout
    
    def _get_next_route(self):
        for trip_route in self.trip_route_ids:
            if not trip_route.arrival_date:
                return trip_route
        return None
        
    def _get_last_route(self):
        lat_route = None
        if self.trip_route_ids:
            lat_route = self.trip_route_ids[len(self.trip_route_ids) -1] 
        return lat_route    
    
    def _get_prev_route(self):
        prev_rout  = None
        if self.trip_route_ids:
            for trip_route in self.trip_route_ids:
                if trip_route.arrival_date:
                    prev_rout = trip_route
                        
        return prev_rout
    
    @api.depends('trip_route_ids')
    def _get_prev_route_of(self, seq):
        prev_rout  = None
        if self.trip_route_ids:
            for trip_route in self.trip_route_ids:
                if trip_route.sequence == seq -1:
                    prev_rout = trip_route
                    break
                        
        return prev_rout
        
    def _get_route_count(self):
        self.trip_route_count = len(self.trip_route_ids) if self.trip_route_ids else 0 
        return self.trip_route_count   
        
    def _get_next_state(self):
        if self.state == 'b':
            return 'r'
        
        if self.state == 'r':
            return 't' if self._get_next_route() != None else 'b'
        #mark it to branch
        return 'b'
    
    def next_trip_no(self, branch_sequence):
        trip_no = branch_sequence._next()
        if self.search([('trip_no', '=', trip_no)], limit=1, count=True):
            return self.next_trip_no(branch_sequence)
        return trip_no
    
    
    @api.depends('departure_date')
    def _compute_date(self):
        for r in self:
            r.date = common.timestamp_company_date_st(self, r.departure_date or fields.Datetime.now())
    
    @api.model
    def create(self, vals):
        _logger.info(vals)
        branch_id = self.env.user.branch_id
        trip_seq_id = branch_id.get_sequence('trip_seq_id')
        if not trip_seq_id:
            raise ValidationError(_('This branch has invalid sequence'))
        
        trip_no = trip_seq_id.sudo()._next()
        
        vals.update({'branch_id': branch_id.id, 'city_id': branch_id.city_id.id,
                 'cur_branch_id': branch_id.id, 'cur_city_id': branch_id.city_id.id,
                 'trip_no': trip_no})
        
        vehicle_id = self.env['tms.truck'].browse(vals['truck_id'])[0]
        # vals['driver_id'] = vehicle_id.sudo().driver_id.id
        _logger.info(vals)
        
        trip = super(Trip, self).create(vals)
        super(Trip, trip).write({'routes_text': trip._get_route_text()})
        
        """
        if  ('driver_expense' not in vals) or vals['driver_expense'] <= 0.0:
                raise ValidationError(_('Please enter the driver expense right'))
        """
        
        if vehicle_id.active_trip_id:
            raise ValidationError(_('The truck %s already used in another trip')% (vehicle_id.name))
        
        
        
        vehicle_id = vehicle_id.sudo()
        driver_id = vehicle_id.driver_id.sudo()
        
        if 'driver_mobile' in vals:
            if vals['driver_mobile'] and vals['driver_mobile'] != driver_id.mobile:
                driver_id.write({'mobile_phone': vals['driver_mobile']})
        # else:
        #     super(Trip, trip).write({'driver_mobile': driver_id.mobile})
        
        if not trip.is_internal and not trip.trip_route_ids and trip.branch_id == trip.branch_to_id :
            super(Trip, trip).write({'is_internal': True, 'internal_type': "1", 'distance': 0, 'duration': 0, 'expected_arrival': False})
        
        if not trip.is_internal:
            distance, duration, expected_arrival = trip._compute_arrival()
            if distance <= 0 and (trip.trip_route_ids or trip.city_id != trip.city_to_id):
                raise ValidationError(_('No distance between city: %s and city: %s') % (trip.city_id.name, trip.city_to_id.name))
            if trip.distance != distance:
                super(Trip, trip).write({'distance': distance, 'duration': duration, 'expected_arrival': expected_arrival}) 
        
        vehicle_id.write({'active_trip_id': trip.id})
                  
        return trip
    
    
    def write(self, vals):
        if 'branch_id' in vals and vals['branch_id']:
            branch_id = self.env['tms.branch'].browse(vals['branch_id'])
            vals.update({'cur_branch_id': branch_id.id, 'cur_city_id': branch_id.city_id.id})
        
        """
        if 'driver_expense' in vals and vals['driver_expense'] <= 0.0:
            raise ValidationError(_('Please enter the driver expense right'))
        """
        
        for r in self:
            if r.expense_posted or r.emove_id:
                for f in BLOCKED_FIELDS:
                    if f in vals:
                        del vals[f]
    
        if 'vehicle_id' in vals and vals['vehicle_id']:
            vehicle_id = self[0].vehicle_id
            vehicle_id.sudo().write({'active_trip_id': False})
            vehicle_id = self.env['tms.truck'].browse(vals['truck_id'])[0]
            vals['driver_id'] = vehicle_id.sudo().driver_id.id
        
        if 'driver_id' in vals and not vals['driver_id']:
            del vals['driver_id']    
        
        ret = super(Trip, self).write(vals)
        
        if 'branch_to_id' in vals or 'trip_route_ids' in vals:
            t = self[0]
            ret = super(Trip, self).write({'routes_text': t._get_route_text()})
            if not t.is_internal and not t.trip_route_ids and t.city_id == t.city_to_id :
                super(Trip, t).write({'is_internal': True, 'internal_type': "1"})
            
        if 'vehicle_id' in vals and vals['vehicle_id']:
            vehicle_id = self[0].vehicle_id.sudo()
            vehicle_id.write({'active_trip_id': self[0].id})
        
        if 'driver_mobile' in vals:
            vehicle_id = self[0].vehicle_id.sudo()
            driver_id = vehicle_id.driver_id.sudo()
            if vals['driver_mobile'] and vals['driver_mobile'] != driver_id.mobile:
                driver_id.write({'mobile': vals['driver_mobile']})
        
        if 'city_id' in vals or 'city_to_id' in vals or 'trip_route_ids' in vals:
            for t in self:
                if not t.is_internal and not t.trip_route_ids and t.city_id == t.city_to_id :
                    super(Trip, t).write({'is_internal': True, 'internal_type': "1", 'distance': 0, 'duration': 0, 'expected_arrival': False})
                if not t.is_internal:
                    distance, duration, expected_arrival = t._compute_arrival()
                    if distance <= 0 and (t.trip_route_ids or t.city_id != t.city_to_id):
                        raise ValidationError(_('No distance between city: %s and city: %s') % (t.city_id.name, t.city_to_id.name))
                    if t.distance != distance:
                        super(Trip, t).write({'distance': distance, 'duration': duration, 'expected_arrival': expected_arrival})  
                
        return ret
    
    
    def unlink(self):
        for r in self:
            if r.state != 'b' :
                raise ValidationError(_('You can only remove trip if it in branch state'))
            if r.expense_posted or r.emove_id or r.amove_id:
                raise UserError(_('This trip was posted'))
        self.mapped('vehicle_id').sudo().write({'active_trip_id': False})
        return super(Trip, self).unlink()
                 
    @api.depends('can_stop_trip')
    
    def action_stop_trip(self):
        self.ensure_one()
        context =  dict(self._context)
        return {
            'name': _('Stop Trip'),
            'type': 'ir.actions.act_window',
            'res_model': 'tms.trip.stop.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'context': context,
            'target': 'new',
        }
        
    
    @api.depends('can_stop_trip','receipt_route_active_ids')
    
    def action_do_stop_trip(self, branch_id):
        now = fields.Datetime.now()
        if not self.can_stop_trip:
            raise UserError(_('Can not stop the trip where it at current states'))
        active_route = self._get_active_route()
        
        if self.receipt_route_active_ids:
            receipt_ids = self.mapped('receipt_route_active_ids.receipt_id') 
            
            for r in receipt_ids:
                
                state = 'a' if r.branch_to_id.id == branch_id.id else 't'
                r.super_write({'trip_id': False, 
                        'cur_branch_id': branch_id.id, 'cur_city_id': branch_id.city_id.id,'state':  state})
            self.receipt_route_active_ids.write({'down_date': now, 'state': 'd'})
        
        if active_route:
            active_route.write({'arrival_date': now, 'arrived_by': self.env.user.id})
        
        self.write({'state': 'e', 'arrival_date': now, 'arrived_by': self.env.user.id})
        self.vehicle_id.sudo().write({'city_id': branch_id.city_id.id, 'branch_id': branch_id.id,
                                     'active_trip_id': False})
           
        
        if not self.is_internal and self.receipt_route_ids:
            mapping = self.env['tms.trip.receipt.mapping'].search([('trip_id', '=', self.id)])
            self.receipt_route_ids._sum_distance(mapping)
            
        return True
    
    
    @api.depends('can_arrive', 'receipt_route_active_ids')
    
    def action_arrival(self):
        cur_branch_id = self.env.user.branch_id
        cur_city_id = cur_branch_id.city_id
        now = fields.Datetime.now()
        
        if not self.can_arrive:
            raise UserError(_('Can not change state of trip to arrival where it not in road '))
        active_route = self._get_active_route()
        last_route = self._get_last_route()
        
        
        #if active_route:
        #    raise UserError(_('Active route: %s') % active_route.branch_to_id.name)
        arrivals_receipts = list()
        
        if self.is_internal and self.branch_id == self.branch_to_id:
            if self.internal_type == "1":
                for receipt_route in self.receipt_route_active_ids:
                    receipt_id = receipt_route.receipt_id
                    receipt_id.no_validate(self._context).super_write({'trip_id': False})
                    receipt_route.write({'down_date': now})
            elif self.internal_type == "2": 
                posted_data = {
                    'posted_date': now,
                    'posted_by': self.env.uid,
                    'resv2_name': self.resv2_name,
                    'resv2_mobile': self.resv2_mobile,
                    'resv2_id': self.resv2_id,
                    'trip_id': False
                    }
                
                for receipt_route in self.receipt_route_active_ids:
                    receipt_id = receipt_route.receipt_id
                    receipt_id.no_validate(self._context).action_post(posted_data)
                    receipt_route.write({'down_date': now, 'state': 'd'})
        
        else:
            for receipt_route in self.receipt_route_active_ids:
                receipt_id = receipt_route.receipt_id
                if receipt_id.branch_to_id.id == cur_branch_id.id:
                    receipt_id.no_validate(self._context).super_write({'trip_id': False, 
                        'cur_branch_id': cur_branch_id.id, 'cur_city_id': cur_branch_id.city_id.id, 'arrival_date': now, 'state': 'a'})
                    receipt_route.write({'down_date': now, 'state': 'd'})
                    arrivals_receipts.append(receipt_id)
                else:
                    rdata = {'cur_branch_id': cur_branch_id.id, 'cur_city_id': cur_branch_id.city_id.id, 'state': 't'}
                    #check the trip is last route
                    if not active_route:
                        rdata['trip_id'] = False
                    receipt_id.no_validate(self._context).super_write(rdata)
                    if not active_route:
                        receipt_route.write({'down_date': now, 'state': 'd'})
                 
        
        truck_data = {'city_id': cur_city_id.id, 'branch_id': cur_branch_id.id,'active_trip_id': False}
        
        trip_data = { 'cur_branch_id': cur_branch_id.id, 
                      'cur_city_id': cur_city_id.id,
                      'next_branch_id': 0, 
                      'state': 't', 
                      'virtual_income': self.calc_virtual_income()
                }
        
        #if this.branch_to_id.id == cur_branch_id.id:
        if not active_route:
            trip_data.update({'arrival_date': now, 'state': 'a', 'arrived_by': self.env.user.id})
            truck_data['active_trip_id'] = False
            if not self.is_internal and self.receipt_route_ids:
                mapping = self.env['tms.trip.receipt.mapping'].search([('trip_id', '=', self.id)])
                self.receipt_route_ids._sum_distance(mapping)
                
        else:
            active_route.write({'arrival_date': now, 'arrived_by': self.env.user.id})
            #truck_data['trip_id'] = False
        #else:
        #    next_route = self._get_next_route()
        #    if next_route:
        #        trip_data['next_branch_id'] = next_route.branch_id.id 
        #    
        
        super(Trip, self).write(trip_data)
        self.vehicle_id.sudo().write(truck_data)   
        self.truck_id.sudo().write(truck_data)   
        
        if not self.is_internal or self.branch_id != self.branch_to_id:
            for r in arrivals_receipts:
                r.action_arrival()
          
        return True
    
    @api.depends('can_takeoff', 'receipt_route_active_ids', 'is_internal', 'internal_type')
     
    def action_takeoff(self):
        cur_branch_id = self.env.user.branch_id
        now = fields.Datetime.now()
        if not self.can_takeoff:
                raise UserError(_('Can not takeoff the trip where not in [In Branch, Transient] states'))
            
        mapping = self.env['tms.trip.receipt.mapping']
        
        route = self._get_current_route()
        receipt_ids = self.mapped('receipt_route_active_ids.receipt_id')
        
        if not self.is_internal and self.receipt_ids:
            for receipt in self.receipt_ids:
                receipt.no_validate(self._context).super_write({'state': 'r'})
            # self.receipt_ids.no_validate(self._context).super_write({'state': 'r'})
        
        is_internal = self.is_internal or (not self.trip_route_ids and self.city_id == self.city_to_id)
        if self.vehicle_id.seats and len(self.receipt_route_active_ids) > self.vehicle_id.seats:
            raise ValidationError(_("The maximum car loaded should be less or equals (%s)" % (self.vehicle_id.seats, )))
        
        city_id = route.city_to_id if route else self.city_id
        
        ttri = self
        if route:
            #ttri = route
            for tri in self.trip_route_ids:
                if tri.sequence > route.sequence:
                    ttri = tri
                    city_id = ttri.city_id
                    break
        
        elif len(self.trip_route_ids) > 0:
            ttri = self.trip_route_ids[0]
        
        city_to_id = ttri.city_to_id
        
        distance = common.tms_get_distance_no_cache(city_id, city_to_id);
        if not is_internal and distance > 0:
            for receipt_route in self.receipt_route_active_ids:
                data = {'receipt_route_id': receipt_route.id, 'trip_id': self.id, 
                        'trip_route_id': route.id if route else False,
                        'distance': distance, 'city_id': city_id.id, 'city_to_id': city_to_id.id,
                        'receipt_id': receipt_route.receipt_id.id}
                mapping.create(data)
        
        #if route:
        #~    route.receipt_mapping_ids.refresh()
        #    raise UserError(("Receipt count: %s") % len(route.receipt_mapping_ids))
        
        if route:
            if not route.departure_date:
                route.write({'departure_date': now, 'last_departure_date': now, 'takeoff_by': self.env.user.id})
            else:
                route.write({'last_departure_date': now, 'takeoff_by': self.env.user.id})
        
 #       if self.trip_route_ids:
#            self.trip_route_ids.refresh()
        
        next_route = self._get_next_route()
        if next_route:
            next_branch_id = next_route.branch_to_id
        else:
            next_branch_id = self.branch_to_id
        
        data = {'state': 'r', 'next_branch_id': next_branch_id.id, 'car_count': len(self.all_receipt_route_ids),
                'virtual_income': self.calc_virtual_income()}
        if not self.last_departure_date:
            data['last_departure_date'] = now
            if not self.departure_date:
                data['departure_date'] = now
        
        if not route:
            data['takeoff_by'] = self.env.user.id
        
        self.write(data)
        
        if not is_internal:
            if route: 
                distance, duration, expected_arrival = route._compute_arrival()
                if expected_arrival:
                    route.write({'distance': distance, 'duration': duration, 'expected_arrival': expected_arrival})
            else:
                distance, duration, expected_arrival = self._compute_arrival()
                if expected_arrival:
                    super(Trip, self).write({'distance': distance, 'duration': duration, 'expected_arrival': expected_arrival})
            
            
            
            
        return True
    
    @api.depends('can_untakeoff', 'receipt_route_active_ids')
     
    def action_untakeoff(self):
        
        if not self.can_untakeoff:
            raise UserError(_('You can not cancel takeoff of this trip'))
        
        prev = self._get_prev_route()
        
        active = self._get_active_route()
        route = self._get_next_route()
        branch_id = route.branch_id if route else self.branch_id
        
        receipt_ids = self.mapped('receipt_route_active_ids.receipt_id')
        if receipt_ids:
            for r in receipt_ids:
                r.no_validate(self._context).super_write({'state': 'b' if r.branch_id == branch_id and r.branch_id == r.cur_branch_id else 't'})
            
        receipt_mapping_ids = prev.receipt_mapping_ids if prev else self.receipt_mapping_ids
        if receipt_mapping_ids:
            receipt_mapping_ids.unlink()
        
        data = {'state': 't' if prev else 'b', 'next_branch_id': 0}
        
        if prev:
            prev.write({'last_departure_date': False})
        else:
            data['last_departure_date'] = False
            
        self.write(data)
        
    
    @api.depends('can_cancel_trip')
    
    def action_cancel_trip(self): 
        cur_branch_id = self.env.user.branch_id
        now = fields.Datetime.now()
        for this in self:
            # if not this.can_cancel_trip:
            #     raise UserError(_('Can not cancel trip where it in branch state'))
            
            if self.receipt_mapping_ids:
                self.receipt_mapping_ids.unlink()  
                
            for receipt_route in this.receipt_ids:
                receipt_id = receipt_route.receipt_id
                if receipt_id.trip_id == this:
                    receipt_id.no_validate(self._context).super_write({'trip_id': False})
                if not receipt_route.down_date:
                    receipt_route.write({'down_date': now})
                    
            this.write({'state': 'c', 'cur_branch_id': cur_branch_id.id, 'cur_city_id': cur_branch_id.city_id.id, 'next_branch_id': 0})
            this.vehicle_id.sudo().write({'city_id': cur_branch_id.city_id.id, 'branch_id': cur_branch_id.id, 'active_trip_id': False})
            this.truck_id.sudo().write({'city_id': cur_branch_id.city_id.id, 'branch_id': cur_branch_id.id, 'active_trip_id': False})
            
        return True
    
    def calc_virtual_income(self):
        amount = sum([x.amount_untaxed for x in self.mapped('all_receipt_route_ids.receipt_id')])
        #raise ValidationError("Virtual Income: %s" % (amount))
        return amount

    
    def action_select_receipts(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id('tms.action_tms_receipt_by_branch')
        action['context'] = self._context
        return action
    
    
    
    def name_get(self):
        result = []
        for trip in self:
            result.append((trip.id,  str(trip.trip_no)))
        return result

    
    @api.depends('city_id', 'city_to_id')
    def _compute_arrival(self):
        expected_arrival = False
        if self.trip_route_ids:
            distance = duration = 0 
            last = False
            for r in self.trip_route_ids:
                distance += r.distance
                duration += r.duration
                if r.city_to_id.id != self.city_to_id.id:
                    last = r
            if last:
                #distance -= last.distance
                #duration -= last.duration
                freight_price_obj = self.env['tms.freight.price']    
                city_dist = freight_price_obj.search(['|', '&', ('city_id', '=', last.city_to_id.id), ('city_to_id', '=', self.city_to_id.id),
                                              '&', ('city_id', '=', self.city_to_id.id), ('city_to_id', '=', last.city_to_id.id)], limit=1)
                
                if city_dist:
                    if last.last_departure_date:
                        hours = int(city_dist.duration) or 1
                        
                        minutes = int((city_dist.duration % hours) *  60)
                        expected_arrival =  fields.Datetime.to_string( fields.Datetime.from_string(last.last_departure_date) + 
                                                                            datetime.timedelta(hours=hours, minutes=minutes) )
                    
                    return city_dist.distance + distance, city_dist.duration + duration, expected_arrival
            
                raise ValidationError(_('No distance between city: %s and city: %s') % (last.city_to_id.name, self.city_to_id.name))     
            
            
        if self.city_id ==  self.city_to_id or not self.city_id or not self.city_to_id:
            return False, False, False
        
        if self.city_to_id:
            freight_price_obj = self.env['tms.freight.price']    
            city_dist = freight_price_obj.search(['|', '&', ('city_id', '=', self.city_id.id), ('city_to_id', '=', self.city_to_id.id),
                                          '&', ('city_id', '=', self.city_to_id.id), ('city_to_id', '=', self.city_id.id)], limit=1)
            if city_dist:
                if self.last_departure_date:
                    hours = int(city_dist.duration) or 1
                    
                    minutes = int((city_dist.duration % hours) *  60)
                    expected_arrival =  fields.Datetime.to_string( fields.Datetime.from_string(self.departure_date) + 
                                                                        datetime.timedelta(hours=hours, minutes=minutes) )
                
                return city_dist.distance, city_dist.duration, expected_arrival
            
            raise ValidationError(_('No distance between city: %s and city: %s') % (self.city_id.name, self.city_to_id.name))
        
        return False, False, self.expected_arrival    
    
    def resave_arrival(self):
        distance, duration, expected_arrival = self._compute_arrival()
        super(Trip, self).write({'distance': distance, 'duration': duration, 'expected_arrival': expected_arrival})
    
    
    
    def _can_arrive(self):
        current_branch = self.env.user.branch_id
        r = self
        r.can_arrive = False
        if r.state == 'r':
            route = r._get_active_route()
            if route:
                r.can_arrive = (route.branch_to_id.id == current_branch.id)
            else:
                r.can_arrive = (r.branch_to_id.id == current_branch.id)
            
                 
    
    def _can_takeoff(self):
        current_branch_id = self.env.user.branch_id
        r = self
        r.can_takeoff = False
        
        if r.state in ['b', 't']:
            if self.env.user.has_group("tms.group_tms_trip_takeoff"):
                route = r._get_current_route()
                if route:
                    r.can_takeoff = (route.branch_to_id.id == current_branch_id.id)
                else:
                    r.can_takeoff = (r.branch_id.id == current_branch_id.id)
        
        if r.can_takeoff and r.is_internal:
            r.can_takeoff = len(self.env['tms.receipt.route'].search([('trip_id', '=', r.id)])) > 0
        
        
    
    def _can_untakeoff(self):
        self.can_untakeoff = (self.env.user.has_group('tms.group_tms_cancel_trip_takeoff') and self.state == 'r')
                    
    
    def _can_stop_trip(self):
        self.can_stop_trip = not self.is_internal and (self.env.user.has_group('tms.group_tms_stop_trip') and self.state == 'r')
    
    
    def _can_cancel_trip(self):
        current_branch_id = self.env.user.branch_id
        
        self.can_cancel_trip = self.state == 'b' and (self.branch_id.id == current_branch_id.id) \
                and self.env.user.has_group('tms.group_tms_cancel_trip_takeoff')
                  
    
    def _can_upload(self):
        current_branch_id = self.env.user.branch_id
        self.can_upload = self.state in ['b', 't'] and (self.cur_branch_id.id == current_branch_id.id)
    
    show_activity = fields.Boolean(compute='_show_activity')
    
    def _show_activity(self):
        self.show_activity = self.env.user.has_group('tms.group_tms_show_activity')

    
    def action_print_route(self): 
        """
        template = self.env.ref('base.view_company_report_form_with_print')
        return {
            'name': _('Choose Your Document Layout'),
            'type': 'ir.actions.act_window',
            'context': {'discard_logo_check': True},
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.env.user.company_id.id,
            'res_model': 'res.company',
            'views': [(template.id, 'form')],
            'view_id': template.id,
            'target': 'new',
        }"""
        
        return self.env.ref('tms.action_print_trip').report_action(self) 
    
    
    
    def action_print_jr_report(self): 
        report = self.env['ir.actions.report'].search([('report_name', '=', 'tms.jr_tms_rtrip')], limit=1)
        return report.report_action(self)
    
    def _get_trip(self):
        return self
    
    def _get_receipts(self):
        return self.receipt_route_ids
    
    # @api.model
    # def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
    #     if self._context.get('current', None):
    #         branch_id = self.env.user.branch_id
    #         if args:
    #             from odoo.osv import expression
    #             args = expression.AND([['|', ('branch_id', '=', branch_id.id), ('branch_to_id', '=', branch_id.id)], args])
    #         else:
    #             args = ['|', ('branch_id', '=', branch_id.id), ('branch_to_id', '=', branch_id.id)]
        
        
    #     return super(Trip, self)._search(args, offset=offset, limit=limit, order=order, count=count, access_rights_uid=access_rights_uid)
    
    
    
    
    
    def action_calculate_truck_income(self, validate=False):
        
        import time
        cr = self._cr
        cr.execute("""UPDATE tms_trip SET ignore=%s WHERE ignore=%s""", (False, True))
        cr.commit()
        domain = [('calculated', '=', False), ('is_internal', '=', False), ('ignore', '=', False), ('state', 'in', ('a', 'e')), ('date', '>', '2019-01-01')]
        offset = 0
        trips = self.search(domain, limit=100, order="id asc")
        while trips:
            super(Trip, trips).write({'ignore': True})
            offset += len(trips)
            #_logger.info("Processing %s trips", len(trips))
            try:
                common.tms_process_trip_distance(trips, validate)
            except Exception as e:
                if validate:
                    raise e
                _logger.exception(e)
                break
            
            cr.commit()
            #break
            
            time.sleep(2)
            trips = self.search(domain, limit=100, order="id asc")
        
        cr.execute("""UPDATE tms_trip SET ignore=%s WHERE ignore=%s""", (False, True))
        
   
    def _cron_calculate_truck_income(self):
        self.action_calculate_truck_income() 
                    
    
    def action_post_truck_income(self, validate=False):
        pass 
    
    def compute_receipt_distance(self, domain=None):
        mapping_obj = self.env['tms.trip.receipt.mapping']
        domain = domain or [('posted', '=', False), ('calculated', '=', False), ('state', 'in', ('a', 'e'))]
        domain.append(('distance', '>', 0))
        trips = self.search(domain, limit=500)
        offset = 0
        counter = 0;
        while trips:
            for t in trips:
                if t.distance > 0:
                    t.receipt_route_ids._recalc_distance_and_amount(mapping_obj)
            offset += len(trips)
            self._cr.commit()
            counter += len(trips)
            if len(trips) == 500:
                trips = self.search(domain, offset=offset, limit=500)
            else:
                trips = False
            if counter > 1000:
                break
        raise ValidationError("Updating %s trips" % counter)
    
    def recompute_receipt_distance_for(self, trip_ids):
        freight_price_obj = self.env['tms.freight.price'] 
        city_map = {}
        
        mapping_obj = self.env['tms.trip.receipt.mapping']
        
        domain = [('posted', '=', False), ('calculated', '=', False), ('distance', '>', 0), ('is_internal', '=', False), ('state', 'in', ('a', 'e')), ('arrival_date', '>', '2019-01-01')]
        trips = self.search(domain, limit=100)
        offset = 0
        while trips:
            for t in trips:
                mapping = mapping_obj.search([('trip_id', '=', t.id)])
                mapping._recompute_distance(city_map,freight_price_obj )
                mps = []
                torem = []
                for m in mapping:
                    if m.distance > 0:
                        mps.append(m)
                    elif m.city_id == m.city_to_id:
                        torem.append(m) 
                
                t.receipt_route_ids._sum_distance(mps)
                for m in torem:
                    m.unlink()
                    
            
            offset += len(trips)
            self._cr.commit()
            if len(trips) == 100:
                trips = self.search(domain, offset=offset, limit=100)
            else:
                trips = False
            import time    
            time.sleep(1)
    
    
    
    def compute_receipt_mapping(self):
        max_trip_count = 0
        mapping_obj = self.env['tms.trip.receipt.mapping']
        domain = [('car_count', '>', 0), ('calculated', '=', False), ('distance', '>', 0), ('is_internal', '=', False), ('state', 'in', ('a', 'e')), ('arrival_date', '>', '2018-03-31 21:00:00')]
        trips = self.search(domain, order='date', limit=100)
        offset = 0
        
        while trips:
            mtrips = self.browse()
            for t in trips:
                mapping = mapping_obj.search([('trip_id', '=', t.id), ('distance' , '>', 0)])
                t.receipt_route_ids._sum_distance(mapping)
            
            offset += len(trips)          
            receipts = trips.env['tms.receipt'] 
            
            for t in trips:
                receipt_rrs = t.all_receipt_route_ids
                can_calc = True
                counter = 0;
                for receipt_rr in receipt_rrs:
                    if receipt_rr.receipt_id.state == 'c':
                        continue
                    
                    if receipt_rr.receipt_id.state not in ('a', 'e'):
                        can_calc = False
                        break
                    counter +=1
                
                if can_calc:
                    if counter > 0:
                        for rr in receipt_rrs:
                            receipts |= rr.receipt_id
            
            
            
            
            for r in receipts:
                amount = r.amount_untaxed
                if r.shipping_type == 2:
                    amount = r.go_price
                    if r.amount_tax > 0:
                        amount -= amount * 5/105      
                
                mtrips |= r.trip_id
                
                distance = 0
                for rr in r.receipt_trip_ids:
                    distance += rr.distance
                if distance > 0:
                    for rr in r.receipt_trip_ids:
                        if rr.trip_id.distance > 0:
                            div = amount/distance * min(rr.distance, distance)
                            rr.write({'amount': round(div, 3)})
            
            
            
            self._cr.commit()
            import time    
            time.sleep(2)
            
            #raise UserError("trips: %s" % (trips.ids,))
            
            if max_trip_count > 0 and offset >= max_trip_count:
                break
            
            if len(trips) == 100:
                trips = self.search(domain, order='date', offset=offset, limit=100)
            else:
                trips = False
            
            mtrips.write({'calculated': True})
    
    
    def print_last_departure_date(self):
        return fields.Datetime.to_string(fields.Datetime.context_timestamp(self, fields.Datetime.from_string(self.last_departure_date)) )
    
                
class TripRoute(models.Model):

    _name = "tms.trip.route"
    _order = "sequence"
    
    sequence = fields.Integer(string='Sequence')
        
    trip_id = fields.Many2one('tms.trip')
    
    city_id = fields.Many2one('tms.city', required=True)
    
    branch_id = fields.Many2one('tms.branch', required=True)
    
    city_to_id = fields.Many2one('tms.city', required=True)
    
    branch_to_id = fields.Many2one('tms.branch', required=True)
    
    departure_date = fields.Datetime(string='Departure Date', readonly=True)
    
    last_departure_date = fields.Datetime(string='Last Departure Date', readonly=True)
    
    arrival_date = fields.Datetime(string='Arrival Date', readonly=True)
    
    expected_arrival = fields.Datetime(string='Expected ِ arrival')
    
    distance = fields.Float(string='Distance')
    
    duration = fields.Float(string='Duration')
    
    receipt_route_ids = fields.One2many('tms.receipt.route', 'trip_route_id', string='Receipts Route')
        
    branch_name = fields.Char(related='branch_to_id.name', readonly=True) 
    
    receipt_mapping_ids = fields.One2many('tms.trip.receipt.mapping', 'trip_route_id' , readonly=True)
    
    takeoff_by = fields.Many2one('res.users', "Takeoff By")
    arrived_by = fields.Many2one('res.users', "Arrived By")     
      
    
    def onchange(self, values, field_name, field_onchange):
        result = super(TripRoute, self).onchange(values, field_name, field_onchange)
        return result

    @api.onchange('city_to_id')
    def _city_to_changed(self):
        domain = {'branch_to_id': [('id', '=', 0)]}
        value = {}
        
        if not self.sequence :
            self.sequence = len(self.trip_id.trip_route_ids) if  self.trip_id.trip_route_ids else 2
            value['sequence'] = self.sequence
            
        last_route = None   
        if not self.city_id:
            for route in self.trip_id.trip_route_ids:
                if route.sequence < self.sequence:
                    last_route = route
            
            if last_route:
                self.city_id = last_route.city_to_id
                self.branch_id = last_route.branch_to_id
                value['city_id'] = last_route.city_to_id
                value['branch_id'] = last_route.branch_to_id
                value['departure_date'] = self.departure_date
                value['last_departure_date'] = False
                
            else:
                self.city_id = self.trip_id.city_id
                self.branch_id = self.trip_id.branch_id
                self.city_to_id = False #self.trip_id.city_to_id
                self.branch_to_id = False #self.trip_id.branch_to_id
                value['city_id'] = self.city_id
                value['branch_id'] = self.branch_id
                value['city_to_id'] = self.city_to_id
                value['branch_to_id'] = self.branch_to_id
                value['departure_date'] = self.departure_date
                value['last_departure_date'] = False
        
        
        
        if not self.city_to_id:
            value['branch_to_id'] = False
            value['distance'] = False
            value['duration'] = False
            value['expected_arrival'] = False
            value['last_departure_date'] = False
        else:
            _logger.info("-----_city_to_changed (%s)", len(self))
            ids = self.city_to_id.branch_ids.mapped('id')
            domain['branch_to_id'] = [('id', 'in', ids)]
            if self.branch_to_id and self.branch_to_id.city_id != self.city_to_id:
                value['branch_to_id']= False
            
            first_branch_id = ids[0] if len(ids) == 1 else False
            
            if first_branch_id:
                value['branch_to_id']= self.env['tms.branch'].browse(first_branch_id)[0]
            
            distance, duration, expected_arrival = self._compute_arrival()
            value.update({'distance': distance, 'duration': duration, 'expected_arrival': expected_arrival, 'last_departure_date': False})
        
        res = {'domain': domain, 'value': value}
        
        return res
    
    @api.model
    def _compute_arrival(self):
        expected_arrival = False 
        if self.city_id ==  self.city_to_id or not self.city_id or not self.city_to_id:
            return False, False, False
        
        if self.city_to_id:
            freight_price_obj = self.env['tms.freight.price']    
            city_dist = freight_price_obj.search(['|', '&', ('city_id', '=', self.city_id.id), ('city_to_id', '=', self.city_to_id.id),
                                          '&', ('city_id', '=', self.city_to_id.id), ('city_to_id', '=', self.city_id.id)], limit=1)
            if city_dist:
                if self.last_departure_date:
                    hours = int(city_dist.duration)
                    hours = hours or 1
                    minutes = int((city_dist.duration % hours) *  60)
                    expected_arrival =  fields.Datetime.to_string( fields.Datetime.from_string(self.last_departure_date) + 
                                                                        datetime.timedelta(hours=hours, minutes=minutes) )
                
                return city_dist.distance, city_dist.duration, expected_arrival
            
            raise ValidationError(_('No distance between city: %s and city: %s') % (self.city_id.name, self.city_to_id.name))
        
        return False, False, False
    
    def _get_active_route(self):
        active_rout  = None
        if self.trip_id.trip_route_ids:
            for trip_route in self.trip_id.trip_route_ids:
                if not trip_route.arrival_date:
                    if not active_rout or active_rout.sequence < trip_route.sequence:
                        active_rout = trip_route
                        
        return active_rout.id if active_rout != None else 0
    
    
    def name_get(self):
        result = []
        for route in self:
            result.append((route.id,  str(route.sequence)))
        return result
    

    
    
    def action_print_receipt_route(self): 
        return self.env.ref('tms.action_print_trip_route').report_action(self) 
    
    trip_no = fields.Char(related='trip_id.trip_no')
    
    def _get_trip(self):
        return self.trip_id
    
    def _get_receipts(self):
        return self.receipt_route_ids
    
    
    @api.model
    def create(self, vals):
        route = super(TripRoute, self).create(vals)
        if route.distance <= 0 and route.city_id != route.city_to_id:
            raise ValidationError(_('No distance between city: %s and city: %s') % (route.city_id.name, route.city_to_id.name))
        
        return route
    
    
    def write(self, vals):
        if 'branch_id' in vals or 'branch_to_id' in vals:
            for r in self:
                if r.departure_date:
                    raise ValidationError(_('You can not modify the route if the flight takes off'))        
        result = super(TripRoute, self).write(vals)
        if 'city_id' in vals or 'city_to_id' in vals:
            trips = set()
            for r in self:
                if r.city_id != r.city_to_id:
                    distance, duration, expected_arrival = r._compute_arrival()
                    if r.distance != distance:
                        if not distance:
                            raise ValidationError(_('No distance between city: %s and city: %s') % (r.city_id.name, r.city_to_id.name))
                        super(TripRoute, r).write({'distance': distance, 'duration': duration, 'expected_arrival': expected_arrival})
                        trips.add(r.trip_id) 
            
            for trip in trips:    
                trip.resave_arrival()        
                    
        return result
    
    
    def unlink(self):
        hasGroup = self.env.user.has_group("tms.group_tms_remove_route")
        trips = set()
        for r in self:
            
            trips.add(r.trip_id)
            
            if r.trip_id.state not in ['b', 't']:
                raise ValidationError('You can only remove route if it the in states in branch or transient')
            
            if r.trip_id.state == 't' and not hasGroup:
                raise AccessError(_('Access denied'))
            
            if r.last_departure_date:
                raise UserError(_('You are trying to remove processed trip route'))
            
            
            if r.trip_id and r.trip_id.trip_route_ids:
                sequence = 1
                for route in r.trip_id.trip_route_ids:
                    if route.id != r.id:
                        super(TripRoute, route).write({'sequence': sequence})
                        sequence += 1
            if r.receipt_mapping_ids:
                r.receipt_mapping_ids.unlink()
                        
        ret = super(TripRoute, self).unlink()
        
        for trip in trips:
            trip.resave_arrival()  
        
        return ret
        
    def print_last_departure_date(self):
        return fields.Datetime.to_string(fields.Datetime.context_timestamp(self, fields.Datetime.from_string(self.last_departure_date)) )    
    
class ReceiptRoute(models.Model):

    _name = "tms.receipt.route"
    
    receipt_id = fields.Many2one('tms.receipt', required=False)
    name = fields.Char(string='Receipt', related='receipt_id.receipt_no')
    trip_id = fields.Many2one('tms.trip', required=True) 
    trip_route_id = fields.Many2one('tms.trip.route')
    
    branch_id = fields.Many2one('tms.branch', related='receipt_id.branch_id', string='From', readonly=True)
    branch_to_id = fields.Many2one('tms.branch', related='receipt_id.branch_to_id', string='To', readonly=True)
    route_branch_id = fields.Many2one('tms.branch', compute='_compute_route', string='Route From', readonly=True)
    route_branch_to_id = fields.Many2one('tms.branch', compute='_compute_route', string='Route To', readonly=True)
    departure_date = fields.Datetime(compute='_compute_route', readonly=True)
    arrival_date = fields.Datetime(compute='_compute_route', readonly=True)
    
    cur_branch_id = fields.Many2one('tms.branch', related='receipt_id.cur_branch_id', readonly=True, string="Current Branch")
    
    up_date = fields.Datetime(readonly=True)
    down_date = fields.Datetime(readonly=True)
        
    can_downoad = fields.Boolean(compute='_can_downoad')
    
    state_date = fields.Datetime(compute='_compute_state_date', readonly=True)
    
    receipt_state = fields.Selection(related='receipt_id.state', string='State', readonly=True)
    
    #truck_id = fields.Many2one('tms.truck', related='trip_id.truck_id', string='Truck', readonly=True)
    vehicle_id = fields.Many2one('fleet.vehicle', related='trip_id.vehicle_id', string='Vehicle', readonly=True)
    
    driver_id = fields.Many2one('res.partner', related='trip_id.driver_id', string='Driver', readonly=True)
    
    state = fields.Selection([
        ('u','Up'),
        ('d', 'Down'),
    ], string='State', index=True, readonly=True, default='u', copy=False)
    
    distance = fields.Float(default=0.0)
    amount = fields.Float(default=0.0)
    
    
    
    @api.depends('trip_route_id')    
    def _compute_route(self):
        for r in self:
            r.route_branch_id = r.trip_route_id.branch_id if r.trip_route_id else r.trip_id.branch_id
            r.route_branch_to_id = r.trip_route_id.branch_to_id if r.trip_route_id else r.trip_id.branch_to_id
            r.departure_date = r.trip_route_id.last_departure_date if r.trip_route_id else r.trip_id.last_departure_date
            r.arrival_date = r.trip_route_id.arrival_date if r.trip_route_id else r.trip_id.arrival_date
    
    
    def _compute_state_date(self):
        for r in self:
            r.state_date = r.up_date if r.state == 'u' else r.down_date 
    
    
    def _can_downoad(self):
        branch_id = self.env.user.branch_id
        for r in self:
            r.can_downoad = r.trip_id.state != 'r' and r.receipt_id.cur_branch_id == branch_id
    
    
    @api.depends('receipt_id', 'state', 'can_downoad')
    def action_downoad(self):
        now = fields.Datetime.now()
        for r in self:
            if not r.can_downoad:
                raise UserError(_('Can download this receipt'))
            mappings = self.env['tms.trip.receipt.mapping'].search([('receipt_route_id', 'in', r.ids)])
            if not mappings:
                r.unlink()
                #raise ValidationError('AAAAA')
            elif (r.receipt_id.state == 'b' or (r.receipt_id.state == 'a' and r.trip_id.state == 'b')) and r.receipt_id.cur_branch_id == r.receipt_id.branch_id:
                r.unlink()
                #raise ValidationError('BBBBBB')
            elif  r.receipt_id.state == 'a':
                pass
            else:
                r.write({'state': 'd', 'down_date': now})
                rdata = {'trip_id': False, 'cur_branch_id': self.env.user.branch_id.id,
                         'cur_city_id': self.env.user.branch_id.city_id.id,
                         'state': 't' if not r.trip_id.is_internal else r.receipt_id.state}
                r.receipt_id.no_validate(self._context).super_write(rdata)
    
    
    def unlink(self):
        mappings = self.env['tms.trip.receipt.mapping'].search([('receipt_route_id', 'in', self.ids)])
        if mappings:
            mappings.unlink()
        for r in self:
            r.receipt_id.no_validate(self._context).super_write({'trip_id': False})
        
        super(ReceiptRoute, self).unlink()
            
    
    def open_receipt_form(self):
        context = self._context.copy()
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'tms.receipt',
                'view_id': False,
                'type': 'ir.actions.act_window',
                'res_id':self.receipt_id.id,
                'context': context,
                'target': 'current',
            }

    
    def open_trip_form(self):
        context = self._context.copy()
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'tms.trip',
                'view_id': False,
                'type': 'ir.actions.act_window',
                'res_id':self.trip_id.id,
                'context': context,
                'target': 'current',
            }
        
    
    def _sum_distance(self, mapping):
        for r in self:
            distance = 0;
            for m in mapping:
                if m.receipt_route_id.id == r.id:
                    distance += m.distance
            r.write({'distance': distance})    
    
    def _recalc_distance_and_amount(self, mapping_obj=None):
        mapping_obj = mapping_obj or self.env['tms.trip.receipt.mapping']
        for r in self:
            if r.trip_id.distance <= 0:
                continue
            distance = 0;
            mapping = mapping_obj.search([('receipt_route_id', '=', r.id)])
            for m in mapping:
                distance += m.distance
            
            amount = r.receipt_id.amount_untaxed
            if r.receipt_id.shipping_type == 2:
                amount = .6 * (r.receipt_id.amount_total - r.receipt_id.amount_tax)
            div = amount/r.trip_id.distance * distance
            olddist = r.distance
            r.write({'distance': distance, 'amount': div})
            if olddist != distance:
                raise ValidationError("Update old distance: %s, new distance: %s " % olddist, distance)
            
            
                
    
    def _recompute_distance(self, mapping):
        for r in self:
            if r.trip_id.distance <= 0:
                continue
            
            distance = amount = 0
            for m in mapping:
                if m.receipt_route_id.id == r.id:
                    distance += m.distance
            
            amount = r.receipt_id.amount_untaxed
            if r.receipt_id.shipping_type == 2:
                amount = .6 * (r.receipt_id.amount_total - r.receipt_id.amount_tax)
            div = amount/r.trip_id.distance * distance
            
            r.write({'distance': distance, 'amount': div})

class TripReceiptMapping(models.Model):
    _name = 'tms.trip.receipt.mapping'
    
    receipt_route_id = fields.Many2one('tms.receipt.route', required=True)
    trip_id =  fields.Many2one('tms.trip')
    trip_route_id =  fields.Many2one('tms.trip.route')
    receipt_id = fields.Many2one('tms.receipt', store=True)
    distance = fields.Float(store=True)
    city_id = fields.Many2one("tms.city", store=True)
    city_to_id = fields.Many2one("tms.city", store=True)
    
    
    @api.depends('trip_route_id', 'trip_id.active_route_id')    
    def _get_receipt(self):
        freight_price_obj = self.env['tms.freight.price'] 
        city_map = {}
        for r in self:
            r.receipt_id = r.receipt_route_id.receipt_id
            city_id = city_to_id = None
            compute_dist = False
            if r.trip_route_id:
                city_id = r.trip_route_id.city_to_id
                ttri = r.trip_id
                compute_dist = True
                for tri in r.trip_id.trip_route_ids:
                    if tri.sequence > r.trip_route_id.sequence:
                        ttri = tri
                        compute_dist = False
                        break
                city_to_id = ttri.city_to_id
                
            else:
                city_id = r.trip_id.city_id
                ttri = r.trip_id
                if len(r.trip_id.trip_route_ids) > 0:
                    ttri = r.trip_id.trip_route_ids[0]
                city_to_id = ttri.city_to_id 
            #distance = common.tms_get_distance(city_map, city_id, city_to_id, freight_price_obj)
            r.distance = ttri.distance if not compute_dist else common.tms_get_distance(city_map, city_id, city_to_id, freight_price_obj)
            r.city_id = city_id
            r.city_to_id = city_to_id
    
            
    def _recompute_distance(self, city_map, freight_price_obj):
        for r in self:
            city_id = city_to_id = None
            compute_dist = False
            if r.trip_route_id:
                city_id = r.trip_route_id.city_to_id
                ttri = r.trip_id
                compute_dist = True
                for tri in r.trip_id.trip_route_ids:
                    if tri.sequence > r.trip_route_id.sequence:
                        ttri = tri
                        compute_dist = False
                        break
                city_to_id = ttri.city_to_id
                
            else:
                city_id = r.trip_id.city_id
                ttri = r.trip_id
                if len(r.trip_id.trip_route_ids) > 0:
                    ttri = r.trip_id.trip_route_ids[0]
                city_to_id = ttri.city_to_id 
            distance = ttri.distance if not compute_dist else common.tms_get_distance(city_map, city_id, city_to_id, freight_price_obj)
            #distance = ttri.distance
            r.write({'distance': distance, 'city_id': city_id.id, 'city_to_id': city_to_id.id})
        self.refresh()
        
        
    
class TripPost(models.Model): 
    _name = 'tms.trip.post'
    _log_access = False
    trip_id = fields.Many2one('tms.trip', required=True) 
    date =  fields.Date()
    postall = fields.Boolean()

class StopTripWizard(models.TransientModel): 
    _name = 'tms.trip.stop.wizard'
    
    branch_id = fields.Many2one('tms.branch', string='Branch', required=True)  
    
    
    def action_stop_trip(self):
        
        trip_id_int = self._context.get('active_id')
        
        self.env['tms.trip'].browse(trip_id_int).action_do_stop_trip(self.branch_id)
        return {'type': 'ir.actions.act_window_close'} 
