from werkzeug.urls import url_encode

from odoo import api, exceptions, fields, models, _

import datetime
import json

from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError
from odoo.tools import float_is_zero, float_compare, pycompat
from odoo.addons import decimal_precision as dp
from . import common
import logging

_logger = logging.getLogger(__name__)

BLOCKED_FIELDS = ['amount', 'amount_total', 'driver_expense', 'other_expense', 'partner_id', 'c_partner_id']


class ITrans(models.Model):
    _name = 'tms.itrans'
    
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _description = "Internal Car Transport"
    _order = "id desc"
    
    @api.model
    def _get_branch(self):
        return self.env.user.branch_id 
    
    @api.depends('branch_id')
    @api.model
    def _get_city(self):
        return self.env.user.branch_id.city_id if  self.env.user.branch_id else False
        
    @api.model
    def _default_currency(self):
        return self.env.user.company_id.currency_id
        
    receipt_no = fields.Char(string="Receipt No", readonly=True, copy=False, index=True)
    
    is_comp = fields.Boolean(required=True, default=False);
    
    name = fields.Char(string="Display Name", copy=False, index=True)
        
    branch_id = fields.Many2one('tms.branch', string='Branch', required=True, readonly=True, index=True, default=_get_branch)
    city_id = fields.Many2one('tms.city', string='City', required=True, readonly=True, store=True, index=True, default=_get_city)
    move_id = fields.Many2one('tms.move', string='Move Id', required=True, ondelete='restrict')
    branch_to_id = fields.Many2one('tms.branch', string='To Branch')

    state = fields.Selection([
            ('d','Draft'),
            ('o', 'Open'),
            ('p', 'Paid'),
            ('e', 'Ended'),
            ('c', 'Cancelled'),
        ], string='Status', index=True, readonly=True, default='d',
        tracking=True, copcancely=False, copy=False)
    
    
    shipping_type = fields.Selection([
            ("1", 'Place to place'),
            ("2", 'Place to branch'),
            ("3", 'Branch to place'),
            ("4", 'Branch to branch')], type='integer', string="Transport Type",
            default=1, required=True, readonly=True, states={'d': [('readonly', False)]})

                
    receipt_date = fields.Datetime(string='Receipt Date', readonly=True, states={'d': [('readonly', False)]}, default=lambda self: fields.Datetime.now())
    date = fields.Date(compute='_compute_date', store=True)     
    due_date = fields.Date("Due Date", compute='_compute_due_date', store=True, readonly=True)    
    arrival_date = fields.Datetime(string='Arrival Date', readonly=True)
    
    car_id = fields.Char(help='Car plate number or customs card number', required=True)
    is_card = fields.Boolean("Customs Card", help='Select if the car have customs card number', default=False)
    issue_year = fields.Char(string='Issue Year', help="Car manufacturing year")
    color = fields.Char(string='Color', help='Car color')
    body_no = fields.Char(string='Body Number', help='Car body Number')
    
    brand_id = fields.Many2one('tms.cbrand', string='Car Brand', required=True)
    model_id = fields.Many2one('tms.cmodel', string='Car Model', required=True, domain=[('id', '=', -1)])
            
    partner_id = fields.Many2one('res.partner', string='Client', help="The customer how will charge the car", required=True)
    c_partner_id = fields.Many2one('res.partner', string='Client', help="The customer how will charge the car", states={'d': [('readonly', False)]})
    responsible_id = fields.Many2one('res.partner', string='Responsible', help="The person under the company how will charge the car")
    
    shipper_id = fields.Many2one('res.partner', string='Shipping company', help="The customer how will charge the car", domain=[('is_company', '=', True)])
    
    ffrom = fields.Char(string="From")
    
    to = fields.Char(string="To")
                
    currency_id = fields.Many2one('res.currency', default=_default_currency, string="Company Currency", readonly=True)
    
    comment = fields.Text('Additional Information', tracking=True, states={'c': [('readonly', True)]})
    
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', required=True, domain="[('state', '=', 'released')]")
    
    driver_id = fields.Many2one('res.partner', string='Driver', store=True, readonly=True)
        
    driver_expense = fields.Monetary(string="Driver Expense", currency_field='currency_id', tracking=True)
    
    other_expense = fields.Monetary(string="Other Expense", currency_field='currency_id',  tracking=True)
    
    total_expense = fields.Monetary(string="Total Expense", compute='_compute_expense', currency_field='currency_id', store=False)
    
    amount_tax = fields.Monetary(string='Tax', store=True, readonly=True, compute='_compute_amount')
    amount = fields.Monetary(string='Amount', tracking=True)
    amount_total = fields.Monetary(string='Total',  store=True, readonly=True, compute='_compute_amount')
    pick_cost = fields.Monetary(string='Pickup Cost',  default=0.0)
    amount_read = fields.Monetary(string='Amount', readonly=True, compute='_compute_amount_read')
         
    residual = fields.Monetary(compute='_compute_residual', store=True, help="Remaining amount due.")
    
    payment_total = fields.Monetary(currency_field='currency_id', compute='_compute_residual', store=True, copy=False)
    
    batch_payment_id = fields.Many2one('tms.batch.payment')
    
    posted = fields.Boolean(default=False, readonly=True, copy=False)
        
    reconciled = fields.Boolean(string='Paid/Reconciled', store=True, readonly=True, compute='_compute_residual',
        help="It indicates that the invoice has been paid and the journal entry of the invoice has been reconciled with one or several journal entries of payment.")
    
    
    receipt_id =  fields.Many2one('tms.receipt', copy=False, readonly=True)
    
    resv_name = fields.Char(string="Recipient", copy=False)
    resv_id = fields.Char(string="ID", copy=False, index=True)
    resv_mobile = fields.Char(string="Mobile", copy=False)
    resv_country = fields.Char(string="Country", copy=False)
    
    sender_ssn = fields.Char(related='partner_id.ssn', store=False, readonly=True)
    sender_mobile = fields.Char(related='partner_id.mobile', store=False, readonly=True)
    
    same_sender = fields.Boolean(string="Same Sender", default=False)
    
    trans_payment_ids = fields.One2many('tms.payments', 'trans_id', copy=False)
    
    branch_name = fields.Char(related='branch_id.name', readonly=True)
    
    contract_no = fields.Char(string="Contract No")
    use_contract = fields.Boolean(compute='_need_contract')
    
    is_receipt = fields.Boolean(compute='_is_receipt')
        
    amove_id = fields.Many2one("account.move", "Journal Entry", readonly=True, copy=False, ondelete='set null')
    invoice_id = fields.Many2one('account.invoice', readonly=True, copy=False, ondelete='set null')
    
    @api.constrains('pick_cost')
    def _check_pick_cost(self):
        for s in self:
            if s.amount > 0 and s.pick_cost > s.amount:
                raise ValidationError("Pickup cost most be less than amount price.")
    
    def print_receipt_date(self):
        return fields.Datetime.to_string(fields.Datetime.context_timestamp(self, fields.Datetime.from_string(self.receipt_date)) )    
    
    
    def _is_receipt(self):
        self.is_receipt = self.receipt_id or self._context.get('receipt', False)

    
    
    def _need_contract(self):
        return self.c_partner_id and self.c_partner_id.is_company and self.c_partner_id.use_contract
    
    @api.onchange('branch_id')
    def _branch_changed(self):
        is_comp = self.receipt_id.is_comp if self.receipt_id else self.move_id and self.move_id.is_comp != False 
        domain = {'move_id': [('branch_id', '=', self.env.user.branch_id.id)]}
        value = {}
        if self.receipt_id:
            domain['move_id'].append(('is_comp', '=', self.receipt_id.is_comp))
            if not self.env.user.has_group('tms.group_tms_admin') :
                domain['move_id'].append(('is_manual', '=', False))
            
            
            if self.receipt_id.state in ['d', 'b']:
                ids = []
                first_branch = None
                for branch_id in self.city_id.branch_ids:
                    if self.branch_id.id != branch_id.id:
                        ids.append(branch_id.id)
                        first_branch = branch_id
                
                if len(ids) == 1:
                    value['branch_to_id'] = first_branch
                
                value['shipping_type'] = 4
                domain['branch_to_id'] = [('id', 'in', ids)]
                
            elif self.receipt_id.state == 'a':
                value['shipping_type'] = 3 #Branch to place
                
            #value['city_id'] = self.receipt_id.city_id
            #value['branch_id'] = self.receipt_id.branch_id
            value['shipper_id'] = self.receipt_id.shipper_id
            value['responsible_id'] = self.receipt_id.responsible_id
            value['c_partner_id'] = self.receipt_id.c_partner_id
            value['partner_id'] = self.receipt_id.partner_id
                  
            value['move_id'] = self.env['tms.move'].search(domain['move_id'], limit=1)
        
        elif self.branch_id:
            
            move_id = self.env['tms.move'].search(domain['move_id'], limit=1)
            if move_id:
                value['move_id'] = move_id
                is_comp = True if move_id and move_id.is_comp else False
            else:
                is_comp = False 
        
        if not is_comp and self.branch_id:    
            d1 = fields.Datetime.from_string('2022-09-21 00:00:00')
            d2 = fields.Datetime.from_string('2022-09-25 00:00:00')    
            receipt_date = self[0].receipt_date  
            
                
        self._is_receipt()
        value['is_comp'] = is_comp
        value['is_receipt'] = self.is_receipt
        domain['vehicle_id'] = [('city_id', '=', self.env.user.branch_id.city_id.id),
                               ('active_trip_id', '=', False), ('driver_id', '!=', False)]
        
        
        
        
        return {'value': value, 'domain': domain}  
    
    @api.onchange('move_id')
    def _move_changed(self):
        self.partner_id=False
        self.c_partner_id=False
        if not self.receipt_id:
            is_comp = True if self.move_id and self.move_id.is_comp else False
            return {'value': {'is_comp': is_comp}}
        
        return {}
        
    @api.onchange('brand_id')
    def _cbrand_changed(self):
        res = {'value' : {'model_id' : False}, 'domain': {'model_id' : [('brand_id', '=', -1)]}}
        if self.brand_id:
            if self.model_id and self.model_id.id in self.brand_id.mapped('model_ids.id'):
                del res['value']['model_id']
            res['domain']['model_id'] = [('brand_id', '=', self.brand_id.id)]
        return res
        
    @api.onchange('partner_id')
    def _partner_changed(self):
        try:
            self.check_partner(self.partner_id)
        except (ValidationError) as e:
            self.partner_id = self._origin.partner_id
            raise e
        value = {'c_partner_id': self.partner_id, 'use_contract': False}
        return {'value': value}
    
    @api.onchange('c_partner_id')
    def _c_partner_changed(self):
        try:
            self.check_partner(self.c_partner_id)
        except (ValidationError) as e:
            self.c_partner_id = self._origin.c_partner_id
            raise e
        
        value = {'partner_id': self.c_partner_id, 'shipper_id': self.c_partner_id}
        if self.c_partner_id:
            self.env['res.partner'].browse()
            p = self.env['res.partner'].search([('parent_id', '=', self.c_partner_id.id)], limit=1)
            if p:
                value['responsible_id'] = p
            
            value['use_contract'] = self.c_partner_id.use_contract
            
        return {'value': value}
    
    @api.onchange('is_card')
    def _is_card_changed(self):
        return {'value': {'car_id': False}}
    
    @api.onchange('car_id')
    def _car_changed(self):
        
        if self._context.get('receipt', False):
            return {}
        
        value = {}
        if self.car_id:
            receipt = self.search([('car_id', '=', self.car_id)], limit=1)
            if receipt:
                value['issue_year'] = receipt.issue_year
                value['color'] = receipt.color
                value['body_no'] = receipt.body_no
                value['brand_id'] = receipt.brand_id
                value['model_id'] = receipt.model_id
            
        
        return {'value': value}
    
    @api.depends('partner_id')
    @api.onchange('same_sender')
    def _same_sender_changed(self):
         
        res = {'value' : {'model_id' : False}, 'domain': {'model_id' : [('brand_id', '=', -1)]}}
        if self.same_sender:
            partner = self.partner_id or self.c_partner_id
            if not partner:
                return {'warning' : {'message':  _("Please select the client/sender first")}, 'value': {'same_sender': False}}
            
            return {'value': {'resv_name': partner.name, 'resv_id': partner.ssn, 'resv_mobile': partner.mobile , 'resv_country': partner.country_id.name if partner.country_id else False}}

        return {'value': {'resv_name': False, 'resv_id': False, 'resv_mobile': False, 'resv_country': False}}
    
    @api.onchange('driver_expense', 'other_expense')
    def _expense_changed(self):
        res = {'value' : {'total_expense' : self.driver_expense + self.other_expense}}
        return res

    @api.onchange('vehicle_id')
    def _truck_changed(self):
        driver_id = self.vehicle_id.sudo().driver_id if self.vehicle_id else False
        value = {'driver_id': driver_id}
        return {'value': value}
    
    @api.depends('receipt_date')
    def _compute_date(self):
        for r in self:
            r.date = common.timestamp_company_date_st(self, r.receipt_date or fields.Datetime.now())
    
    @api.depends('partner_id', 'date')
    def _compute_due_date(self):
        company_id = self.env.user.company_id
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
        
        receipt_no = False
        name = False
        
        receipt = None
        if 'receipt_date' not in vals or not vals.get('receipt_date'):
            vals.update({'receipt_date': fields.Datetime.now()})
        
        
        if  ('driver_expense' not in vals) or vals['driver_expense'] <= 0.0:
                raise ValidationError(_('Please enter the driver expense right'))
        
        
        move_id = self.env['tms.move'].browse(vals['move_id'])
        
        if 'receipt_id' in vals and vals['receipt_id']:
            receipt = self.env['tms.receipt'].browse(vals['receipt_id'])
            
            #if receipt.branch_id != self.env.user.branch_id and receipt.cur_branch_id != self.env.user.branch_id:
            #    raise ValidationError(_('The receipt branch is not valid for your branch'))
            
            
            partner_id = receipt.c_partner_id or receipt.partner_id
            
            
            receipt_no = False
            while True:
                receipt_no = move_id.trans_sec_id.sudo()._next()
                if self.search([('receipt_no', '=', receipt_no)], limit=1) == 0:
                    break 
            code = move_id.code + receipt_no[4:5]
            prefix = str(int(receipt_no[len(code)+1:]))
            name = code + '-' + prefix
            
            vals.update({
                        'move_id': move_id.id,
                        'is_comp':receipt.is_comp,
                        'is_card':receipt.is_card,
                        'car_id':receipt.car_id,
                        'brand_id':receipt.brand_id.id,
                        'model_id':receipt.model_id.id,
                        'issue_year':receipt.issue_year,
                        'color':receipt.color,
                        'partner_id':partner_id.id,
                        'contract_no': receipt.contract_no,
                        'c_partner_id':partner_id.id,
                        'shipper_id':receipt.shipper_id.id,
                        'responsible_id':receipt.responsible_id.id,
                        'same_sender': receipt.same_sender ,
                        'resv_id': receipt.resv1_id,
                        'resv_name': receipt.resv1_name,
                        'resv_mobile': receipt.resv1_mobile,
                        'resv_country': receipt.resv1_country,
                        'state': 'o'})
            
            #if vals['shipping_type'] == 1:
            #    raise ValidationError(_('Transport type is invalid while receipt is active', receipt_no))
            
            if vals['shipping_type'] == 4:
                if receipt.state == 'd' :
                    receipt.action_confirm_receipt()
                receipt.write({'cur_branch_id': vals['branch_to_id'], 'state': 't' if receipt.state!='a' else receipt.state})
        else:
            receipt_no = self.env.user.company_id.sec_id.sudo()._next()
            code = receipt_no[:4]
            prefix = str(int(receipt_no[4:]))
            name = code + '-' + prefix  
        if  not vals.get('receipt_id') and (not vals.get('is_comp') and vals.get('amount') <= 0.0):
            raise ValidationError(_('You should enter the transport price'))
            
        
        expense_fileds = ['driver_expense', 'other_expense']
        total_expense = 0
        for f in expense_fileds:
            if f in vals:
                total_expense += vals[f] 
        vals.update({'total_expense': total_expense})
        
        #receipt_no = self.sequence_number_next
        if not receipt_no:
            raise ValidationError(_('Unable to create number for trans!!'))
                
        if self.search([('receipt_no', '=', receipt_no)], limit=1):
            raise ValidationError(_('Number for trans (%s) duplicated by system ', receipt_no))
        
        is_comp = move_id.is_comp
        vals['is_comp'] = is_comp
        #is_comp = vals.get('is_comp') or True
        
        #if ('receipt_id' not in vals) and not is_comp and ('amount' not in vals or vals['amount'] <= 0.0): 
        #    raise ValidationError(_('Please enter the transport price!'))
        
        
        vals.update({'receipt_no':receipt_no, 'name': name, 'branch_id': move_id.branch_id.id,
                      'city_id': move_id.branch_id.city_id.id})
            
        vals['tax_id'] = self.env.user.branch_id.tax_id and self.env.user.branch_id.tax_id.id
        ret = super(ITrans, self).create(vals)
        ret.check_partner(ret.partner_id)
        ret.write({'driver_id': ret.vehicle_id.driver_id.id})
        return ret   
    
    
    def write(self, vals):
        
        
        for r in self:
            if r.amove_id:
                for f in BLOCKED_FIELDS:
                    if f in vals:
                        del vals[f]
        
        self[0].check_partner(vals['partner_id'] if 'partner_id' in vals else self[0].partner_id)
        
        expense_fileds = ['driver_expense', 'other_expense']
        if len(self) > 1:
            for f in expense_fileds:
                if f in vals:
                    raise ValidationError(_('You can update expense on multi transaction'))
        
        have_expense = False
        for f in expense_fileds:
            if f in vals:
                have_expense = True
                break
        
        r = self[0]
        is_comp = r.is_comp
        if 'move_id' in vals:
            is_comp = self.env['tms.move'].browse(vals['move_id']).is_comp
            vals['is_comp'] = is_comp
        
        if 'receipt_id' not in vals and (not is_comp and not r.receipt_id):
            if 'amount' in vals and vals['amount'] <= 0.0:
                raise ValidationError(_('You should enter the transport price'))
        
        if have_expense:
            
            if 'driver_expense' in vals and vals['driver_expense'] <= 0.0:
                raise ValidationError(_('Please enter the driver expense right'))
            
            total_expense = 0
            for f in expense_fileds:
                if f in vals:
                    total_expense += vals[f] 
                else:
                    total_expense += r.__getitem__(f)
            
            
            
            vals.update({'total_expense': total_expense})
        
        
        if 'receipt_date' in vals and not vals['receipt_date']:
            del vals['receipt_date']
            
        
        if 'vehicle_id' in vals:
            vehicle_id = self.env['fleet.vehicle'].browse(vals['vehicle_id'])
            vals['driver_id'] = vehicle_id.driver_id.id
        
        
        ret = super(ITrans, self).write(vals)
        
        if 'amount' in vals:
            r._update_payments()
        
        return ret
        
    
    
    def super_write(self,vals):
        super(ITrans, self).write(vals)
    
    @api.depends('amount')
    def _compute_amount(self):
        for r in self:
            r.amount_tax = 0
            tax_id = r.branch_id.tax_id if r.branch_id else None
            if tax_id:
                r.amount_tax = tax_id._compute_amount(r.amount, r.amount, partner=r.partner_id)
            r.amount_total = r.amount_tax + r.amount
    
    @api.depends('amount')
    def _compute_amount_read(self):
        for r in self:
            r.amount_read = r.amount
    
    @api.onchange('amount')
    def _amount_changed(self):
        r = self
        amount_tax = 0
        tax_id = r.branch_id.tax_id if r.branch_id else None
        if tax_id:
            amount_tax = tax_id._compute_amount(r.amount, r.amount, partner=r.partner_id)
        amount_total = amount_tax + r.amount
        
        return {'value': {'amount_total': amount_total, 'amount_tax': amount_tax, }}

    @api.depends('driver_expense', 'other_expense')
    def _compute_expense(self):
        for r in self:
            r.total_expense = r.driver_expense +  r.other_expense 
    
    def _get_payment_info_JSON(self):
        payments_widget = json.dumps({})
        
    """
    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None): 
        super(ITrans, self)._search(args, offset=offset, limit=limit, order=order, count=count, access_rights_uid=access_rights_uid)
    """
    
    
    @api.depends('state')
    def action_confirm_itrans(self):
        for r in self:
            if r.state != 'd':
                raise ValidationError(_('This trans is not valid to confirmed'))
        
        for r in self:
            move_id = r.move_id
            receipt_no = False
            while True:
                receipt_no = move_id.trans_sec_id.sudo()._next()
                if self.search([('receipt_no', '=', receipt_no)], limit=1) == 0:
                    break 
            code = move_id.code + receipt_no[4:5]
            prefix = str(int(receipt_no[len(code)+1:]))
            name = code + '-' + prefix    
            r.write({'state': 'o', 'receipt_no': receipt_no, 'name': name})          
            
        
        return True
    
    
    @api.depends('state', 'can_cancel', 'payment_total')
    def action_cancel_itrans(self):
        if not self.can_cancel:
            raise UserError(_('Access Error!Check your receipt state, current branch, receipt payments or contact the administrator!'))
        
        if self.state == 'd':
            self.sudo().unlink()
            return
        
        if self.payment_total > 0:
            context =  dict(self._context)
            context.update({'default_trans_id': self.id, 'trans_id': self.id, 'default_source': 3, 'source': 3, 'type': 'outbound'})  
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
        else:
            self._make_cancel()
             
     
     
    def action_register_payment(self):
        self.ensure_one()
        context =  dict(self._context)
        context.update({'default_trans_id': self.id, 'trans_id': self.id, 'default_source': 3, 'source': 3})  
        return {
            'name': ('Register Payment'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'tms.register.payments',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'context': context,
            'target': 'new'
        }
    
    
    def action_print_voucher(self):
        self.ensure_one()        
        return self.trans_payment_ids[0].action_print_voucher()
    
    
    def action_print_route(self): 
        return self.env.ref('tms.action_print_itrans_route').report_action(self) 
    
    
    def action_print_receipt(self):
        """ Print the invoice and mark it as sent, so that we can see more
            easily the next step of the workflow
        """
        self.ensure_one()
        from . import common
        return common.print_receipt(self)
     
    
    def dump(self, obj):
        for attr in dir(obj):
            _logger.error("obj.%s = %s" , attr, getattr(obj, attr))


    
    
    def name_get(self):
        result = []
        for trans in self:
            result.append((trans.id, trans.name))
        return result

    @api.onchange('amount_total')
    def _onchange_amount_total(self):
        for inv in self:
            if inv.amount_total < 0:
                raise Warning(_('You cannot validate an invoice with a negative total amount. You should create a credit note instead.'))


    
    @api.depends('state', 'currency_id', 'amount_total', 'invoice_id')
    def _compute_residual(self, vals=None):
        
        if (self.is_comp or self.invoice_id) and not self.amove_id:
            total_payment = 0
            if self.invoice_id and self.invoice_id.state == 'paid':
                total_payment = self.amount_total
            else:
                pyaments = self.env['tms.payments'].search([('trans_id', '=', self.id)])
                total_payment = pyaments.compute_payments(self.currency_id) if pyaments else 0.0
        else:
            pyaments = self.env['tms.payments'].search([('trans_id', '=', self.id)])
            total_payment = pyaments.compute_payments(self.currency_id) if pyaments else 0.0
            
            
        self.payment_total = total_payment
        self.residual = self.amount_total - total_payment if self.state != 'c' else 0.0
        if float_is_zero(self.residual, precision_rounding=self.currency_id.rounding):
            self.reconciled = True
        else:
            self.reconciled = False
            
    def _update_payments(self):
        self.refresh()
        self._compute_residual()
        vals = {'payment_total': self.payment_total, 'residual': self.residual, 'reconciled': self.reconciled}
        if self.state == 'd':
            self.action_confirm_itrans()
        if self.reconciled:
            vals['state'] = 'p'
        self.super_write(vals)
    
    
    def _make_cancel(self):
        if self.state not in ('p', 'o'):
            raise ValidationError(_('This receipt is going up of branch')) 
        if  self.amove_id or self.invoice_id:
            raise ValidationError(_('This receipt was posted'))
        if self.shipping_type == 4 and self.receipt_id and self.receipt_id.state == 't' and self.receipt_id.cur_branch_id == self.branch_to_id:
            self.receipt_id.no_validate(self._context).super_write({'state':'b', 'cur_branch_id': self.move_id.branch_id.id})
        
        self.write({'state': 'c', 'residual': 0.0, 'reconciled': True})
        payment_ids = self.env['tms.payments'].search([('trans_id', '=', self.id), ('amove_id', '=', False)])
        if payment_ids:
            payment_ids.write({'ignore': True})
    
    @api.model
    def _search(self, args, offset=0, limit=None, order=None, access_rights_uid=None):
        if self._context.get('not_all', None):
            branch_id = self.env.user.branch_id
            if args:
                from odoo.osv import expression
                args = expression.AND([['|', ('branch_id', '=', branch_id.id), ('branch_to_id', '=', branch_id.id)], args])
            else:
                args = ['|', ('branch_id', '=', branch_id.id), ('branch_to_id', '=', branch_id.id)]
        
        
        return super(ITrans, self)._search(args, offset=offset, limit=limit, order=order, access_rights_uid=access_rights_uid)  

    
    def copy(self, default=None):
        context =  dict(self._context)
        context.update({'copy': 1, 'id': False})
        return {
            'name': ('Copy Internal Transport'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'tms.itrans',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'context': context,
            'target': 'current'
        }
        
    @api.model
    def default_get(self, fields):
        ctx = self._context
        rec = super(ITrans, self).default_get(fields)
        if ctx.get('copy') and ctx.get('active_id'):
            r = self.browse(ctx.get('active_id'))
            rec.update({
                
                         'is_comp': r.is_comp, 
                         'partner_id': r.partner_id.id, 
                         'c_partner_id': r.partner_id.id,
                         'city_id': r.city_id.id, 
                         'branch_id': r.branch_id.id,
                         'branch_to_id': r.branch_to_id.id,
                         'move_id': r.move_id.id,
                         'amount': r.amount, 
                         'amount_tax': r.amount_tax, 
                         'amount_total': r.amount_total,
                         'shipping_type': r.shipping_type,
                         'brand_id': r.brand_id.id, 
                         'model_id': r.model_id.id,
                         'driver_expense': r.driver_expense,
                         'ffrom': r.ffrom, 
                         'to': r.to
                    })
            
        #_logger.info("Receipt default_get context: %s, rec: %s", self._context, rec)
        
        rec.pop('vehicle_id', None)
        rec['vehicle_id'] = 2336
        return rec
    
    can_change_date = fields.Boolean(compute='_can_change_any')    
    can_cancel = fields.Boolean(compute='_can_change_any')
    can_post = fields.Boolean(compute='_can_change_any')
    can_edit = fields.Boolean(compute='_can_change_any', default=False)
    can_edit_pick = fields.Boolean(compute='_can_change_any', default=False)
    
    @api.depends('state', 'amount_total', 'residual')
    
    def _can_change_any(self):
        user = self.env.user
        self.can_change_date = self.state == 'd' and self.env.user.has_group('tms.group_tms_receipt_date')
        
        self.can_cancel = self.state == 'd' or ( not self.amove_id and self.state in ('o', 'p') and (user.branch_id == self.branch_id and self.residual == 0))
        if not self.can_cancel and self.state in ('o', 'p') and (user.branch_id == self.branch_id or self.residual == 0) and user.has_group('tms.group_tms_cancel_itrans'):
            self.can_cancel = not bool(self.invoice_id)
            
        
        if not self.state or self.state == 'd':
            self.can_edit = True
        elif self.currency_id.is_zero(self.payment_total) and not self.amove_id and not self.invoice_id and self.state != 'c' and self.env.user.has_group("tms.group_tms_change_receipt_price"):
            self.can_edit = True
        
        
        self.can_edit_pick = self.is_comp and self.can_edit and self.env.user.has_group('tms.group_tms_edit_pickup_price')
        
        self.can_post = self.state in ['o', 'p'] or (self.receipt_id and self.receipt_id.state not in ['d', 'b', 'c'])
    
    
    
    def unlink(self):
        for receipt in self:
            if receipt.state != 'd':
                raise UserError(_('You can only delete receipt if its in draft state.'))
        
        super(ITrans, self).unlink()
        
    tax_id = fields.Many2one('account.tax', 'Account Tax', compute='_compute_tax_id', store=True)
    
    def _compute_tax_id(self):
        for r in self:
            r.tax_id = r.branch_id.tax_id
    

    has_entry = fields.Boolean(compute='_compute_has_entry')
    
    def action_cancel_entry(self):
        
        self.ensure_one()
        
        cr = self.env.cr
        date = self.date
        
        if date and self.amove_id:
            
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
            r.has_entry = bool(r.amove_id) or bool(r.invoice_id)
