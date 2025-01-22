from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import float_is_zero
import json
import datetime 
class ReceiptScheduler(models.Model):
    _inherit = "tms.receipt"
    
    
    def precess_grounds(self):
        ground_id = self.env['tms.ground'].search([], limit=1)
        
        receipts = self.search([('state', '=', 'a'), ('is_comp', '!=', True)])
        currency_id = self._default_currency()
        for r in receipts:
            if r.branch_to_id.costcenter1_id:
                r.precess_grounds_price(currency_id, ground_id)
            
    
    def compute_grounds_price(self):
        if self.is_comp:
            return
        ground_id = self.env['tms.ground'].search([], limit=1)
        if ground_id:
            has_ground = self.precess_grounds_price(self.currency_id, ground_id)
            if has_ground:
                self._cr.commit()
    
    
    @api.depends('arrival_date')        
    def _compute_grounds(self):
        if self.is_comp:
            return
        ground_id = self.env['tms.ground'].search([], limit=1)
        if ground_id:
            days, gp_price = self._get_ground_price_0(ground_id)
            amount = 0;
            for ds in gp_price:
                amount += ds[0] * ds[1]
            
            #if True:
            #    raise ValidationError("%s" % (gp_price,))
            
            #amount = amount/100
            ground_amount = self.currency_id.round(amount)
            am = ground_amount
            if am <= self.ground_discount:
                am -= self.ground_discount
            
            ground_amount_tax = self._compute_tax_to(am, self.branch_to_id)
            ground_total = ground_amount + ground_amount_tax
            self.ground_amount = ground_amount
            self.ground_amount_tax = ground_amount_tax
            self.ground_total = ground_total
            self.ground_days = days
    
    
    def precess_grounds_price(self, currency_id, ground_id):
        days, gp_price = self._get_ground_price_0(ground_id)
        #days = (datetime.datetime.now() - fields.Datetime.from_string(self.arrival_date)).days      
        
        amount = 0;
        for ds in gp_price:
            amount += ds[0] * ds[1]
            
        #if True:
        #    raise ValidationError("%s, amount: %s" % (gp_price, amount))
        
        ground_amount = currency_id.round(amount)
        if ground_amount <= self.ground_discount:
            ground_amount -= self.ground_discount
        
        if ground_amount > 0:
            am = ground_amount
            if am >= self.ground_discount:
                am -= self.ground_discount
            ground_amount_tax = self._compute_tax_to(am, self.branch_to_id)
            ground_total = ground_amount + ground_amount_tax
            
            self.super_write({'ground_amount': ground_amount, 
                           'ground_amount_tax': ground_amount_tax,
                           'ground_total': ground_total,
                           'ground_days': days,
                           'tax_g_id': self.branch_to_id.tax_id.id}) 
            return True
        return False
        
            
    def _get_ground_price_0(self, ground_id):
        
        if self.state != 'a' or not self.arrival_date:
            return 0, []
        now = datetime.datetime.now()
        days = (now - fields.Datetime.from_string(self.arrival_date)).days        
        days1 = self.expected_arrival and (now - fields.Datetime.from_string(self.expected_arrival)).days or days
        
        if days1 < days:
            days = days1
        dd = days
        glist = []
        if days > 0 and ground_id:
            gg = None
            od = 0
            ls = 0
            for g in ground_id.ground_ids:
                ds = dd - g.days
                if ds > 0:
                    glist.append([g.days, g.price])
                    ls = g.price
                else:
                    glist.append([dd, g.price])
                    dd = 0
                    break
                dd -= g.days
            
            if dd > 0:
                glist.append([dd, ls])
        else:
            days = 0
        
        return days, glist
    
    @api.onchange('ground_discount')
    def _ground_discount_changed(self):
        res = {}
        discount = self.ground_discount/self.ground_amount * 100.0 if self.ground_amount > 0 else 0
        max_discount = self.env.user.max_discount
        if discount > max_discount:
            res['warning'] = {'message':  _('You can only set max discount to (%s) %s' % (str(max_discount), '%'))}
            ground_amount_tax = self._compute_tax_to(self.ground_amount, self.branch_to_id)
            ground_total = self.ground_amount + ground_amount_tax
            res['value'] = {'ground_discount': 0.0, 'ground_total': ground_total, 'ground_amount_tax': ground_amount_tax}
        else:
            ground_amount_tax = self._compute_tax_to(self.ground_amount - self.ground_discount, self.branch_to_id)
            ground_total = self.ground_amount + ground_amount_tax - self.ground_discount
            res['value'] = {'ground_total': ground_total, 'ground_amount_tax': ground_amount_tax}
        return res
    
    def _update_ground_payments(self):
        ground_payment = self._get_ground_payment()
        self.super_write({'ground_payment': ground_payment})
        
        
    
    @api.depends('payment_move_line_ids.amount_residual')
    def _get_payment_info_JSON(self):
        self.payments_widget = json.dumps(False)
        if self.payment_move_line_ids:
            info = {'title': _('Less Payment'), 'outstanding': False, 'content': self._get_payments_vals()}
            self.payments_widget = json.dumps(info)


    @api.model
    def _get_payments_vals(self):
        if not self.payment_move_line_ids:
            return []
        payment_vals = []
        currency_id = self.currency_id
        for payment in self.payment_move_line_ids:
            payment_currency_id = False
            if self.type == 'n': #normal type
                amount = sum([p.amount for p in payment.matched_debit_ids if p.debit_move_id in self.ac_move_id.line_ids])
                amount_currency = sum(
                    [p.amount_currency for p in payment.matched_debit_ids if p.debit_move_id in self.ac_move_id.line_ids])
                if payment.matched_debit_ids:
                    payment_currency_id = all([p.currency_id == payment.matched_debit_ids[0].currency_id for p in
                                               payment.matched_debit_ids]) and payment.matched_debit_ids[
                                              0].currency_id or False
            elif self.type == 'r': # Refund type
                amount = sum(
                    [p.amount for p in payment.matched_credit_ids if p.credit_move_id in self.ac_move_id.line_ids])
                amount_currency = sum([p.amount_currency for p in payment.matched_credit_ids if
                                       p.credit_move_id in self.ac_move_id.line_ids])
                if payment.matched_credit_ids:
                    payment_currency_id = all([p.currency_id == payment.matched_credit_ids[0].currency_id for p in
                                               payment.matched_credit_ids]) and payment.matched_credit_ids[
                                              0].currency_id or False
            # get the payment value in invoice currency
            if payment_currency_id and payment_currency_id == self.currency_id:
                amount_to_show = amount_currency
            else:
                date = fields.Date.from_string(fields.Date.from_string(self.receipt_date))
                amount_to_show = payment.company_id.currency_id.with_context(date=date).compute(amount, self.currency_id)
            if float_is_zero(amount_to_show, precision_rounding=self.currency_id.rounding):
                continue
            payment_ref = payment.move_id.name
            if payment.move_id.ref:
                payment_ref += ' (' + payment.move_id.ref + ')'
            payment_vals.append({
                'name': payment.name,
                'journal_name': payment.journal_id.name,
                'amount': amount_to_show,
                'currency': currency_id.symbol,
                'digits': [69, currency_id.decimal_places],
                'position': currency_id.position,
                'date': payment.date,
                'payment_id': payment.id,
                'account_payment_id': payment.payment_id.id,
                'invoice_id': 0,
                'move_id': payment.move_id.id,
                'ref': payment_ref,
            })
        return payment_vals            
   
    
    
    def resend_sms(self):
        receipts = self.search([('state', '=', 'a'), ('is_comp', '!=', True), ('receipt_date', '>', '2018-03-02 00:00:00') ])
        for r in receipts:
            r.action_arrival()
        #s.super_write({'state': 'c', 'cancel_no': cancel_no, 'cancel_date': cancel_date, 'cancel_by': self.env.user.id,
        #                   'residual': 0, 'reconciled': True})
        