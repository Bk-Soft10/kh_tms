from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, AccessDenied
from odoo.tools.misc import formatLang
from odoo.tools.misc import format_date
from . import common


import logging
_logger = logging.getLogger(__name__)

class tms_abstract_payment(models.AbstractModel):
    _name = "tms.abstract.payments"
    _description = "Contains the logic shared between models which allows to register payments"
    _order = "id desc"
    

    type = fields.Selection([('outbound', 'Refound Money'), ('inbound', 'Receive Money')], string='Payment Type', required=True)
    partner_id = fields.Many2one('res.partner', string='Partner')
    receipt_id = fields.Many2one('tms.receipt')
    trans_id = fields.Many2one('tms.itrans')
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.user.company_id.currency_id)
    company_currency_id = fields.Many2one('res.currency', string='Company Currency', compute="_compute_amount_c", store=True, required=True, default=lambda self: self.env.user.company_id.currency_id)
    amount = fields.Monetary(string='Payment Amount', currency_field='company_currency_id', required=True)
    amount_currency = fields.Monetary(string='Amount Currency', currency_field='currency_id', compute="_compute_amount_c", store=True, default=0.0, required=True)
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True, copy=False, index=True)
    journal_id = fields.Many2one('account.journal', string='Payment Journal', required=True, domain=[('type', 'in', ('bank', 'cash'))])
    company_id = fields.Many2one('res.company', related='journal_id.company_id', string='Company', readonly=True)
    reference = fields.Char(string='Memo', index=True)
    note = fields.Char(size=300)
    source = fields.Selection([
        ('1', 'Receipt Payment'), 
        ('2', 'Ground Payment'),
        ('3', 'Internal Trans Payment'),], default='1')
    
    posted = fields.Boolean(default=False)
    
    receipt_branch_id = fields.Many2one('tms.branch', required=True)
    payment_branch_id = fields.Many2one('tms.branch', required=True)
    
    
    
    def _compute_amount_c(self):
        for p in self:
            p.amount_currency = p.amount
            p.company_currency_id = p.currency_id
    
    #move_id = fields.Many2one('tms.move', string='Mode Id', readonly=True, required=True)
    
    
    @api.constrains('amount')
    def _check_amount(self):
        if self.amount < 0:
            raise ValidationError(_('The payment amount cannot be negative.'))


    @api.onchange('journal_id')
    def _onchange_journal(self):
        if self.journal_id:
            self.currency_id = self.journal_id.currency_id or self.company_id.currency_id
            # Set default payment method (we consider the first to be the default one)
            payment_methods = self.type == 'inbound' and self.journal_id.inbound_payment_method_ids or self.journal_id.outbound_payment_method_ids
            # Set payment method domain (restrict to methods enabled for the journal and to selected payment type)
            type = self.type in ('outbound', 'transfer') and 'outbound' or 'inbound'
            
            if 'receipt_id' in self:
                type = 'inbound'
            
            return {'domain': {'payment_method_id': [('type', '=', type), ('id', 'in', payment_methods.ids)]}}
        return {}

    
    @api.model
    def _compute_residual(self, receipt, source, type, journal_id=None):
        payment_currency = self.currency_id or \
                           (journal_id and (journal_id.currency_id or journal_id.company_id.currency_id)) or receipt.currency_id
        
        residual = 0;
        if type == 'inbound':
            if source != 2:
                #_logger.info("receipt: %s", receipt) 
                receipt._compute_residual() 
                residual = receipt.residual         
            else:
                residual = receipt.currency_id.round(receipt.ground_total - receipt._get_ground_payment() )
        
        else:
            if source != 2: 
                if source == 1 and receipt.shipping_type == 2 and receipt.state not in ('c', 'b'):
                    residual = receipt.return_price
                else:
                    receipt._compute_residual() 
                    residual = receipt.amount_total - receipt.residual
            else:
                residual = receipt._get_ground_payment() 
        
        residual_currency = residual        
        if receipt.currency_id != payment_currency:
            residual_currency = receipt.currency_id.with_context(date=self.date).compute( residual, payment_currency)
   
        return residual_currency, payment_currency
    
    
    def compute_payments(self, currency_id):
        total_payment = 0.0
        for line in self:
            sign = 1 if line.type == 'inbound' else -1
            total_payment += line.amount * sign
        
#        total_payment = currency_id.round(total_payment)
                  
        return total_payment
    

        
class tms_register_payments(models.TransientModel):
    _name = "tms.register.payments"
    _inherit = 'tms.abstract.payments'
    _description = "Register payments on multiple receipts"

    def _get_default_journal_domain(self):
        source = self._context.get('source', False)
        active_id = self._context.get('active_id')
        if not active_id:
            return []
        branch_id = self.env.user.branch_id
        receipt = self.env[ source == 3  and 'tms.itrans' or 'tms.receipt'].browse(active_id)[0]            
        ids = []
        #if branch_id.bank_journal_id:
        #    ids.append(branch_id.bank_journal_id.id)
        ICP = self.env['ir.config_parameter'].sudo()
        if self.env.user.has_group('tms.group_tms_company_accountant'):
            company_journal_id = ICP.get_param('tms.company_journal_id')
            if company_journal_id:
                ids.append(company_journal_id)
        
        cash_journal_id = ICP.get_param('tms.cash_journal_id')
        if cash_journal_id:
            ids.append(cash_journal_id)
        
        #for j in obj_journal.search([('company_cash', '=', False), ('default_cash', '=', True), ('type', '=', 'cash')], limit=1):
        #    ids.append(j.id)
        
        return [('id', 'in', ids)]

    receipt_id = fields.Many2one('tms.receipt', string='Receipts', copy=False)
    journal_id = fields.Many2one('account.journal', string='Payment Journal', required=True, domain=_get_default_journal_domain)
    payment_by = fields.Char()
    batch_payment_id = fields.Many2one('tms.batch.payment', readonly=True)

    @api.onchange('receipt_id')
    def _onchange_receipt(self):
        
        branch_id = self.receipt_id.pay_branch_id 
        domain = {}
        
        return {'domain': domain}

    @api.onchange('amount_currency')
    def _onchange_amount_currency(self):
        if self.company_currency_id == self.currency_id or not self.currency_id:
            return {'value': {'amount': self.amount_currency}} 
        amount = self.company_currency_id.with_context(date=self.date).compute( self.amount_currency, self.currency_id)
        return {'value': {'amount': amount}} 

    @api.onchange('journal_id')
    def _onchange_journal(self):
        journal_id = self.journal_id
        amount_currency = self.amount_currency
        amount = self.amount
        currency_id = journal_id.currency_id or self.company_currency_id if journal_id else self.company_currency_id
        if self.company_currency_id == currency_id:
            amount_currency = currency_id.with_context(date=self.date).compute(amount, self.company_currency_id)
        return {'value': {'currency_id': currency_id, 'amount_currency': amount_currency}}
    

    @api.model
    def default_get(self, fields):
        rec = super(tms_register_payments, self).default_get(fields)
        active_id = self._context.get('active_id')

        # Check for selected receipts ids
        if not active_id:
            raise UserError(_("Programmation error: wizard action executed without active_id in context."))

        
        source = self._context.get('source', False)
        type = self._context.get('type', 'inbound')
        no_cancel = self._context.get('no_cancel', False)
        
        if not source and 'source' in rec:
            source = rec['source']
                    
        #_logger.info("source: %s", source)
        
        receipt = self.env[ source == 3  and 'tms.itrans' or 'tms.receipt'].browse(active_id)[0]

        
        residual, payment_currency = self._compute_residual(receipt, source, type, self.journal_id)

        rec.update({
            'amount': residual,
            'amount_currency': residual,
            'currency_id': payment_currency.id,
            'company_currency_id': receipt.currency_id.id,
            'partner_id': receipt.partner_id.id,
            'note': receipt.name,
            'source': source,
            'type': type,
            'payment_branch_id': self.env.user.branch_id.id
        })
        if source == 3:
            rec['trans_id'] = receipt.id
        else:
            rec['receipt_id'] = receipt.id
        
        
        return rec
 
    
    def get_payments_vals(self):

        receipt = self.receipt_id or self.trans_id
        amount = self.amount
        type = 'inbound'
        #move_id = self.env['tms.move'].search([('type', '=', 'p'), ('branch_id', '=', receipt.pay_branch_id.id)], limit=1)
        source = self._context.get('source') 
        payment_currency = self.currency_id  
        #important because the amount field is readonly
        if self.type == 'outbound':
            amount, payment_currency = self._compute_residual(receipt, self.source, self.type, self.journal_id)   
                
        vals = {
            'journal_id': self.journal_id.id,
            'note': self.note,
            'type': self.type,
            'amount': self.amount,
            'amount_currency': self.amount_currency,
            'currency_id': payment_currency.id,
            'partner_id': receipt.partner_id.id,
            'date': self.date,
            'source': self.source,
            'payment_branch_id': self.env.user.branch_id.id,
            'payment_by': self.payment_by
        }
        
        if self.receipt_id:
            vals['receipt_id'] = receipt.id
        else:
            vals['trans_id'] = receipt.id
            
        return vals

    
    def create_payments(self):
        _logger.info("create_payments create_payments create_payments")
        Payment = self.env['tms.payments'].with_context(self._context)
        payment = Payment.create(self.get_payments_vals())
    
    @api.model
    def create(self, vals):
        if 'source' not in vals:
            vals['source'] = self._context.get('source')
        
        _logger.info("create payments source: %s, context source: %s", vals['source'], self._context.get('source'))
        
        if not isinstance(vals['source'], int):
            vals['source'] = 1
        active_id = self._context.get('active_id')
        
        receipt_id =None
        trans_id = None
        if vals['source'] == 3:
            trans_id = self.env['tms.itrans'].browse(active_id)
            vals['receipt_branch_id'] = trans_id.branch_id.id
        else:
            receipt_id = self.env['tms.receipt'].browse(active_id)  
            vals['receipt_branch_id'] = receipt_id.branch_id.id
        vals['payment_branch_id'] = self.env.user.branch_id.id
        
        ret = super(tms_register_payments, self).create(vals)
        return ret
    
        #payment.post()
        

class Payments(models.Model):
    _name = "tms.payments"
    _inherit = 'tms.abstract.payments'
    _order = "id desc"
    
    dest = fields.Char(readonly=True, compute='_compute_receipt', store=True)
    receipt_no = fields.Char(readonly=True, compute='_compute_receipt', store=True)
    rname = fields.Char(readonly=True, compute='_compute_receipt', store=True)
    car_id = fields.Char(readonly=True, compute='_compute_receipt', store=True)
    cancelled = fields.Boolean(string='Cancelled', readonly=True, default=False)
    
    can_cancel = fields.Boolean(compute='_can_cancel')
    can_edit = fields.Boolean(compute='_can_edit')
    
    branch_name = fields.Char(related='payment_branch_id.name', readonly=True)
     
    is_cache = fields.Boolean(string='Cache', store=True, readonly=True)
    
    sign = fields.Integer(compute='_compute_sign', store=True, readonly=True)
    amove_id = fields.Many2one("account.move", "Journal Entry", readonly=True, ondelete='set null')
    
    batch_reference = fields.Char(readonly=True)
    return_cancelled = fields.Boolean("Return Cancelled")
    ignore = fields.Boolean(readonly=True)
    balance = fields.Monetary(string="Amount", compute='_store_balance', store=True, currency_field='company_currency_id')
    
    payment_by = fields.Char()
    batch_payment_id = fields.Many2one("tms.batch.payment", "Batch Payment", readonly=True)
    
    
    @api.depends('amount', 'sign')
    def _store_balance(self):
        for line in self:
            line.balance = line.amount * line.sign
    
    @api.depends('receipt_id', 'trans_id')
    
    def _compute_receipt(self):
        for r in self:
            receipt =  r.receipt_id or r.trans_id
            r.receipt_no = r.receipt_id.receipt_no if r.receipt_id else r.trans_id.receipt_no
            r.rname = receipt.name
            r.car_id = receipt.car_id
            if r.source == 2:
                r.dest =''
            elif receipt.branch_to_id:
                r.dest =  receipt.branch_to_id.name
            else:
                r.dest = receipt.to
    
    @api.depends('type')
    
    def _compute_sign(self):
        for r in self:
            r.sign = 1 if r.type == 'inbound' else -1
    
        
    @api.model
    def create(self, vals):
        
        source = vals['source']
        amount = vals.get('amount')
        amount_currency = vals.get('amount')
        
        if not amount:
            amount = amount_currency
            vals['amount'] = amount
        
        if not amount_currency:
            amount_currency = amount
            vals['amount_currency'] = amount_currency
        
        type = vals['type']
    
        
        receipt_id =None
        trans_id = None
        receipt = None
        if source == 3:
            receipt = trans_id = self.env['tms.itrans'].with_context(dict(self._context)).browse(vals['trans_id'])
        else:
            receipt = receipt_id = self.env['tms.receipt'].with_context(dict(self._context)).browse(vals['receipt_id'])    
            if source == 1 and receipt.shipping_type == 1:
                receipt = receipt_id
        
        #if receipt and not receipt.invoice_id and type == 'inbound' and receipt.shipping_type == 1:
        #    raise ValidationError(_('This receipt (%s) is not invoiced yet!') % (receipt.name,))
        
        receipt =  receipt_id or trans_id
        
        if 'partner_id' not in vals:
            vals['partner_id'] = receipt.partner_id.id
        
        
        move_id = False 
        move_domain = False   
        if 'move_id' in vals:
            move_id = self.env['tms.move'].browse(vals['move_id'])
        else:
            move_domain = [('is_comp', '=',  receipt.is_comp),
                            ('branch_id', '=',  self.env.user.branch_id.id),
                            ('is_manual', '=',  False)]
            move_id = self.env['tms.move'].search(move_domain, limit=1)
        
        if not move_id:
            raise UserError(_("Please configure move settings for payments! %s") % move_domain)
        
        sequence_id = move_id.payment_sec_id if type == 'inbound' else move_id.cancel_payment_sec_id
        
        vals['reference'] = sequence_id.sudo()._next()
        
        if 'batch_reference' in vals and 'date' in vals:
            pass
        else:
            vals['date'] = self.env.user.has_group('tms.group_tms_payment_date') and vals.get('date') or  fields.Date.context_today(self)
        
        vals['rname'] = receipt.name
        vals['receipt_no'] = receipt_id.receipt_no if receipt_id else trans_id.receipt_no
        
        
        dest = ''
        if source == 2:
            dest =''
        elif receipt.branch_to_id:
            dest =  receipt.branch_to_id.name
        elif trans_id:
            dest = trans_id.to
        vals['dest'] = dest
        
        has_is_cache = 'is_cache' in vals and type != 'inbound'
        
        vals['sign'] = 1 if type == 'inbound' else -1
        
        is_cache = vals['is_cache'] if has_is_cache else False
        
        receipt_branch_id = receipt.branch_to_id if source == 2 else receipt.branch_id
        
        payment_branch_id = self.env['tms.branch'].browse(vals['payment_branch_id']) if vals.get('payment_branch_id', False) else self.env.user.branch_id
        
        #raise ValidationError("is_cache:%s, has_is_cache: %s" % (vals.get('is_cache'), has_is_cache))
        if not is_cache and receipt_branch_id == payment_branch_id:
            r_date = receipt.receipt_date
            p_date = vals['date']
            is_cache = common.is_same_date(self, r_date, p_date)
        
        #raise ValidationError("is_cache:%s, r_date: %s, p_date: %s, receipt_branch_id: %s, payment_branch_id: %s, b_eq: %s" % ( is_cache, receipt.receipt_date, vals['date'], receipt_branch_id, payment_branch_id, receipt_branch_id==payment_branch_id))
        
        if vals['sign'] == -1:
            vals['is_cache'] = is_cache
        else:
            vals['is_cache'] = is_cache and receipt_branch_id == payment_branch_id
        
        vals['balance'] = vals['amount'] * vals['sign']
        vals['receipt_branch_id'] = receipt_branch_id.id
        vals['payment_branch_id'] = payment_branch_id.id
        
        currency_id = self.env['res.currency'].browse(vals['currency_id'])
        
        
        residual = amount;
        residual_currency = amount_currency
        cancel_return = False
        if not self._context.get('no_cancel', False):
            if type == 'inbound':
                if source != 2:
                    receipt._compute_residual() 
                    residual = receipt.residual         
                else:
                    residual = receipt.currency_id.round(receipt.ground_total - receipt._get_ground_payment() )
            else:
                if source != 2:
                    if source == 1 and receipt.shipping_type == 2 and receipt.state not in ('c', 'b'):
                        residual = receipt.return_price
                        cancel_return = True
                    else:
                        receipt._compute_residual() 
                        residual = receipt.amount_total - receipt.residual;
                else:
                    residual = receipt._get_ground_payment() 
        
            if receipt.currency_id != currency_id:
                residual_currency = receipt.currency_id.with_context(date=vals['date']).compute(residual, currency_id)
            else:
                residual_currency = residual
            
            if amount_currency > residual_currency:
                raise UserError(_("The given amount %s is grater than the remaining %s for receipt %s") % (amount_currency, residual_currency, receipt.name,) )   
        
        if cancel_return:
            vals['return_cancelled'] = True
            
        ret = super(Payments, self).create(vals)
        
        if source != 2 : 
            if type == 'inbound' or self._context.get('no_cancel'):
                receipt._update_payments()
                if receipt_id and receipt_id.receipt_no != ret.receipt_no:
                    ret.sudo().write({'receipt_no': receipt_id.receipt_no})
                elif trans_id and trans_id.receipt_no != ret.receipt_no:
                    ret.sudo().write({'receipt_no': trans_id.receipt_no})
            else:
                if cancel_return:
                    receipt._cancel_return()
                else:
                    receipt._make_cancel()
        else:
            receipt._update_ground_payments()
        
        return ret
    
    
    def write(self, vals):
        ret = super(Payments, self).write(vals)
        if 'amount' in vals:
            for s in self:
                if s.amove_id:
                    raise UserError(_("This payment was posted!"))
                """
                receipt_id = s.receipt_id or s.trans_id 
                                    
                if s.type == 'outbound' and  receipt_id.amove_id:
                    raise UserError(_("The receipt was posted!"))
                """    
            
    
    def unlink(self):
        
        if not self.env.user.has_group("tms.group_tms_admin"):
            raise UserError(_("Access denied"))
        
        receipts = []
        grounds = []
        for p in self:
            if p.source in(1, 3):
                receipts.append(p.receipt_id or p.trans_id)
            elif p.source == 2:
                grounds.append(p.receipt_id)
        
        super(Payments, self).unlink()
        
        for r in receipts:
            r._update_payments()
        
        for r in grounds:
            r._update_ground_payments()
        
                
    
    @api.model
    def super_create(self, vals):
        return super(Payments, self).create(vals)
        
    
    
    def super_write(self, vals):
        return super(Payments, self).write(vals)
    
    
    def action_print_voucher(self):
        self.ensure_one()
        if self.source == 1:
            return self.env.ref('tms.action_print_receipt_voucher').report_action(self)
        if self.source == 2:
            return self.env.ref('tms.action_print_ground_voucher').report_action(self)
        if self.source == 3:
            return self.env.ref('tms.action_print_itrans_voucher').report_action(self)
    
    
    def _can_cancel(self):
        has_prem = self.env.user.has_group('tms.group_tms_cancel_payment')
        for p in self:
            p.can_cancel = False
            if has_prem and not p.cancelled and p.type == 'inbound':
                if p.receipt_id:
                    if p.source == 2:
                        p.can_cancel = not bool(p.amove_id)
                    else:
                        p.can_cancel = (p.receipt_id.state not in ('d', 'c', 'e'))
                        #if not p.can_cancel and (p.receipt_id.state not in ['c', 'e']) \
                        #   and p.receipt_id.shipping_type not in [1,2]:
                        #    p.can_cancel =True
                elif p.trans_id:
                    p.can_cancel = (p.trans_id.state not in ('c', 'e') )
    
    
    def _can_edit(self):
        for p in self:
            p.can_edit = not p.amove_id and self.env.user.has_group("tms.group_tms_edit_payment")
        
        
    @api.depends('can_cancel')
    
    def cancel_payment(self, vals):
        
        if not self.can_cancel:
            raise AccessDenied('You have not permission to do this action')
        
        ignore = vals['journal_id'] == self.journal_id.id and not bool(self.amove_id)
        
        self.write({'cancelled': True, 'ignore': ignore})
        
        journal_id = self.env['account.journal'].browse(vals['journal_id'])
        
        receipt = self.receipt_id or self.trans_id
        amount_currency = self.amount
        journal_currency_id = journal_id.currency_id or receipt.currency_id
        
        date = vals['date'] if 'date' in vals and vals['date'] else fields.Date.context_today(self)
        
        if journal_currency_id != receipt.currency_id:
            amount_currency = receipt.currency_id.with_context(date=date).compute( self.amount, journal_id.currency_id)
        
        vals = dict(vals)
        
        if 'payment_branch_id' in vals and not vals['payment_branch_id']:
            del vals['payment_branch_id']
        
        vals.update({'source': self.source, 'type': 'outbound', 'is_cache': self.is_cache,
                     'currency_id': journal_currency_id.id, 'company_currency_id': receipt.currency_id.id,
                     'partner_id': self.partner_id.id, 'receipt_id':  self.receipt_id.id,
                    'trans_id':  self.trans_id.id,  'amount': self.amount, 'amount_currency': amount_currency,
                    'balance':self.amount * -1, 'org_date': self.date, 'ignore': ignore})
        
        self.with_context(self._context).create(vals)
        
    
    def action_show_cancel_payment(self):
        self.ensure_one()
        context =  dict(self._context)
        context['source'] = -1
        return {
            'name': ('Cancel Payment'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'tms.payment.cancel',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'context': context,
            'target': 'new'
        } 
        
    
    def action_show_edit_payment(self):
        self.ensure_one()
        context =  dict(self._context)
        return {
            'name': ('Edit Payment'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'tms.payment.edit',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'context': context,
            'target': 'new'
        }     
    
    @api.depends('can_edit')
    def edit(self, vals):
        amount = vals['amount']
        journal_id = vals['journal_id']
        
        if not self.can_edit:
            raise AccessDenied(_("Access Denied"))
        
        if vals['amount'] > self.amount:
            raise ValidationError(_("The amount should be less than or equals %s") % (self.amount,))
        
        if amount == self.amount:
            #raise ValidationError("%s" %(vals,))
            super(Payments, self).write(vals)
        else:
            rem = abs(self.amount - amount)
            balance = amount * self.sign
            rembalance = rem * self.sign
            payment_branch_id = vals['payment_branch_id'] if 'payment_branch_id' in vals and vals['payment_branch_id'] else self.payment_branch_id.id 
            
            if self.amount_currency == self.amount:
                amount_currency = rem
            else:
                amount_currency = self.amount_currency * rem/self.amount
                        
            receipt =  self.receipt_id or self.trans_id
            
            move_domain = [('is_comp', '=',  receipt.is_comp),
                            ('branch_id', '=',  payment_branch_id),
                            ('is_manual', '=',  False)]
            move_id = self.env['tms.move'].search(move_domain, limit=1)
            
            if not move_id:
                raise UserError(_("Please configure move settings for payments! %s") % move_domain)
            
            sequence_id = move_id.payment_sec_id if self.type == 'inbound' else move_id.cancel_payment_sec_id
            date = vals['date'] if 'date' in vals and vals['date'] else self.date
            data = {'amount': amount, 'amount_currency': self.amount_currency - amount_currency, 'journal_id': journal_id,
                    'source': self.source, 'type': self.type, 'sign': self.sign, 'is_cache': self.is_cache,
                    'currency_id': self.currency_id.id, 'company_currency_id': self.currency_id.id,
                    'partner_id': self.partner_id.id, 'receipt_id':  self.receipt_id.id,'trans_id':  self.trans_id.id,
                    'date': date, 'cancelled': self.cancelled, 'reference': sequence_id._next(),
                    'payment_branch_id': self.payment_branch_id.id, 'receipt_branch_id': self.receipt_branch_id.id,
                    'receipt_no': receipt.receipt_no, 'rname': receipt.name, 'balance': balance}
            
            payment = super(Payments, self).create(data)
            
            self.write({'amount': rem, 'balance': rembalance, 'amount_currency': amount_currency})
            
            query = 'UPDATE "%s" SET create_uid=%s WHERE id=%s' % ( self._table, self.create_uid.id, payment.id)
            self._cr.execute(query)
    
    
    def open_source_form(self):
        context = self._context.copy()
        return {
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'tms.receipt' if self.receipt_id else 'tms.itrans',
                'view_id': False,
                'type': 'ir.actions.act_window',
                'context': context,
                'target': 'current',
                'res_id':self.receipt_id.id if self.receipt_id else self.trans_id.id,
            }
    
    @api.model
    def _get_default_form_view0(self):
        """ Generates a default single-line form view using all fields
        of the current model.

        :returns: a form view as an lxml document
        :rtype: etree._Element
        """
        #from lxml import etree
        readonly = not self.env.user.has_group('tms.group_tms_admin')
        from lxml.builder import E
        group = E.group(col="4")
        for fname, field in self._fields.items():
            
            r = "1" if field.readonly and readonly else "0"
            if field.automatic:
                continue
            elif field.type in ('one2many', 'many2many', 'text', 'html'):
                group.append(E.newline())
                group.append(E.field(name=fname, colspan="4", readonly=r))
                group.append(E.newline())
            else:
                group.append(E.field(name=fname, readonly=r))
        group.append(E.separator())
        return E.form(E.sheet(group, string=self._description))
    
    @api.model
    def fields_get(self, allfields=None, attributes=None):
        readonly = not self.env.user.has_group('tms.group_tms_admin')
        
        fields = models.Model.fields_get(self, allfields=allfields, attributes=attributes)
        
        if fields.get('amove_id') and not self.env.user.has_group('account.group_account_user'):
            fields.pop('amove_id')
        
        for name, des in fields.items():
            des['readonly'] = True if des.get('readonly', False) else readonly
        return  fields
    
    
    def get_pay_by(self):
        return self.payment_by if self.payment_by else self.partner_id.name
    
    
    def update_move_date_maturity(self):
        q = """SELECT p.amove_id, CASE WHEN source=1 THEN (SELECT "date" FROM tms_receipt WHERE id=p.receipt_id )
                      WHEN source=2 THEN (SELECT "date" FROM tms_itrans WHERE id=p.trans_id )
                 END AS rdate 
            FROM tms_payments p
            INNER JOIN account_move m on m.id=p.amove_id
            WHERE source in(1,3) 
            AND m.model_type in(6,7)
            GROUP BY amove_id, rdate"""
        
        cr = self.env.cr
        cr.execute(q)
        for (move_id, rdate) in cr.fetchall():
            if not rdate:
                continue
            qq = """UPDATE account_move_line SET date_maturity=%s WHERE move_id=%s"""
            cr.execute(qq, (rdate, move_id))
            
        
           
    def update_move_date_maturity1(self):
        q = """SELECT p.amove_id, CASE WHEN source=1 THEN (SELECT "date" FROM tms_receipt WHERE id=p.receipt_id )
                      WHEN source=2 THEN (SELECT "date" FROM tms_itrans WHERE id=p.trans_id )
                 END AS rdate 
            FROM tms_payments p
            INNER JOIN account_move m on m.id=p.amove_id
            WHERE source in(1,3) 
            AND m.model_type in(6,7)
            GROUP BY amove_id, rdate"""
        
        cr = self.env.cr
        cr.execute(q)
        for (move_id, rdate) in cr.fetchall():
            if not rdate:
                continue
            qq = """UPDATE account_move_line SET date_maturity=%s WHERE move_id=%s"""
            cr.execute(qq, (rdate, move_id))        
    
    has_entry = fields.Boolean(compute='_compute_has_entry')
    
    def action_cancel_entry(self):
        
        self.ensure_one()
        
        
        date = self.date
        
        if date and self.amove_id:
            cr = self.env.cr
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
        
        self.unlink()    
            
        return True
    
    
    def _compute_has_entry(self):
        for r in self:
            r.has_entry = bool(r.amove_id)
            
                
class PaymentCancel(models.TransientModel):
    _name = "tms.payment.cancel"
    
    def _get_default_journal_domain(self):
        source = self._context.get('source', False)
        active_id = self._context.get('active_id')
        if not active_id:
            return []
        if not source or source == -1:
            p = self.env['tms.payments'].browse(active_id)
            receipt = p.receipt_id or p.trans_id
        else:
            #branch_id = self.env.user.branch_id
            receipt = self.env[ source == 3  and 'tms.itrans' or 'tms.receipt'].browse(active_id)[0]
               
        ids = []
        #if branch_id.bank_journal_id:
        #    ids.append(branch_id.bank_journal_id.id)
        ICP = self.env['ir.config_parameter'].sudo()
        if receipt and receipt.is_comp and self.env.user.has_group('tms.group_tms_company_accountant'):
            company_journal_id = ICP.get_param('tms.company_journal_id')
            if company_journal_id:
                ids.append(company_journal_id)
        
        cash_journal_id = ICP.get_param('tms.cash_journal_id')
        if cash_journal_id:
            ids.append(cash_journal_id)
        
        #for j in obj_journal.search([('company_cash', '=', False), ('default_cash', '=', True), ('type', '=', 'cash')], limit=1):
        #    ids.append(j.id)
        
        return [('id', 'in', ids)]
        
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.user.company_id.currency_id)
    journal_id = fields.Many2one('account.journal', string='Payment Journal', required=True, domain=_get_default_journal_domain)
    date = fields.Date(string='Date')
    payment_branch_id = fields.Many2one('tms.branch')
    note = fields.Char(size=300)
    payment_by = fields.Char()
    
    def action_cancel_payment(self):
        ctx = dict(self._context)
        ctx['no_cancel'] = True
        payment = self.env['tms.payments'].with_context(ctx).browse(self._context.get('active_id'))
        
        payment.cancel_payment({'currency_id': self.currency_id.id if self.currency_id else False,
                                'journal_id': self.journal_id.id, 'payment_branch_id': self.payment_branch_id.id,
                                'date': self.date, 'note': self.note, 'payment_by': self.payment_by})
        
    @api.model
    def default_get(self, fields):
        rec = super(PaymentCancel, self).default_get(fields)
        payment = self.env['tms.payments'].browse(self._context.get('active_id'))
        rec['date'] = payment.date
        rec['payment_by'] = payment.payment_by
        return rec
    
class PaymentEdit(models.TransientModel):
    _name = "tms.payment.edit"
    
    def _get_default_journal_domain(self):
        source = self._context.get('source', False)
        active_id = self._context.get('active_id')
        if not active_id:
            return []
        #branch_id = self.env.user.branch_id
        #receipt = self.env[ source == 3  and 'tms.itrans' or 'tms.receipt'].browse(active_id)[0]            
        ids = []
        #if branch_id.bank_journal_id:
        #    ids.append(branch_id.bank_journal_id.id)
        ICP = self.env['ir.config_parameter'].sudo()
        if self.env.user.has_group('tms.group_tms_company_accountant'):
            company_journal_id = ICP.get_param('tms.company_journal_id')
            if company_journal_id:
                ids.append(company_journal_id)
        
        cash_journal_id = ICP.get_param('tms.cash_journal_id')
        if cash_journal_id:
            ids.append(cash_journal_id)
        
        #for j in obj_journal.search([('company_cash', '=', False), ('default_cash', '=', True), ('type', '=', 'cash')], limit=1):
        #    ids.append(j.id)
        
        return [('id', 'in', ids)]
    payment_id = fields.Many2one('tms.payments', string='Currency', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, related='payment_id.company_currency_id')
    journal_id = fields.Many2one('account.journal', string='Payment Journal', required=True, domain=_get_default_journal_domain)
    amount = fields.Monetary(string='Payment Amount', currency_field='currency_id', required=True)
    note = fields.Char(size=300)
    is_cache = fields.Boolean("Is Cache")
    date = fields.Date(string='Payment Date')
    payment_branch_id = fields.Many2one('tms.branch')
        
    @api.depends('can_cancel')
    
    def action_edit_payment(self):
        payment = self.env['tms.payments'].browse(self._context.get('active_id'))
        payment_branch_id = self.payment_branch_id.id or payment.payment_branch_id.id
        rec = {'amount': self.amount, 'journal_id': self.journal_id.id, 'date': self.date or payment.date,
               'payment_branch_id':payment_branch_id, 'is_cache': self.is_cache, 'note': self.note}
        payment.edit(rec)
    

    
    @api.model
    def default_get(self, fields):
        rec = super(PaymentEdit, self).default_get(fields)
        payment = self.env['tms.payments'].browse(self._context.get('active_id'))
        rec['payment_id'] = payment.id
        rec['amount'] = payment.amount
        rec['date'] = payment.date
        rec['is_cache'] = payment.is_cache
        rec['journal_id'] = payment.journal_id.id
        rec['payment_branch_id'] = payment.payment_branch_id.id
        rec['note'] = payment.note
        return rec
        
