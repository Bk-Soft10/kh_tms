from odoo import models, fields, api, _, tools
from odoo.exceptions import UserError, ValidationError
import datetime
from dateutil.relativedelta import relativedelta
import calendar
import re
from . import common
class BatchPayment(models.Model):
    _name = "tms.batch.payment"
    
    @api.model
    def _get_branch(self):
        return self.env.user.branch_id
    
    def _get_default_journal_domain(self):
        branch_id = self.env.user.branch_id
        ids = []
        if branch_id.bank_journal_id:
            ids.append(branch_id.bank_journal_id.id)
        ICP = self.env['ir.config_parameter'].sudo()
        if self.env.user.has_group('tms.group_tms_company_accountant'):
            for jn in ('tms.company_journal_id', 'tms.discount_company_journal_id', 'tms.scratch_company_journal_id'):
                company_journal_id = ICP.get_param(jn)
                if company_journal_id:
                    ids.append(company_journal_id)
                
        
        cash_journal_id = ICP.get_param('tms.cash_journal_id')
        if cash_journal_id:
            ids.append(cash_journal_id)
            
        return [('id', 'in', ids)]
    
    branch_id = fields.Many2one('tms.branch', string='Branch', required=True, readonly=True, default=_get_branch)
    
    batch_no = fields.Char(string="Number", index=True)
    
    city_id = fields.Many2one('tms.city', related='branch_id.city_id', store=True)
    
    date = fields.Date("Payment Date", readonly=True, states={'d': [('readonly', False)], 'o': [('readonly', False)]})
    
    journal_id = fields.Many2one('account.journal', string='Payment Journal', required=True, domain=_get_default_journal_domain, readonly=True, states={'d': [('readonly', False)], 'o': [('readonly', False)]})
    partner_id = fields.Many2one('res.partner', string='Partner', required=True, readonly=True, states={'d': [('readonly', False)]}, domain=[('customer', '=', True)])
    move_id = fields.Many2one('tms.move', string='Move Payment', readonly=True, states={'d': [('readonly', False)]})
    
    contract_no = fields.Char(string='Contract No', readonly=True, states={'d': [('readonly', False)], 'o': [('readonly', False)]})
        
    receipt_id = fields.Char(compute='_compute_receipt', readonly=True, states={'d': [('readonly', False)]})
    
    payment_line_ids = fields.One2many('tms.batch.payment.line', 'batch_payment_id', readonly=True, states={'d': [('readonly', False)], 'o': [('readonly', False)]})
    
    batch_payment_history_ids = fields.One2many('tms.batch.payment.history', 'batch_payment_id', readonly=True)
    
    amount = fields.Float(readonly=True, states={'d': [('readonly', False)], 'o': [('readonly', False)]})
        
    note = fields.Char(readonly=True, states={'d': [('readonly', False)], 'o': [('readonly', False)]})
    
    
    amount_total = fields.Float(compute='_get_payment_total', readonly=True, string="Total Amount")
    payment_total = fields.Float(compute='_get_payment_total', readonly=True, string="Total Payment")
    residual = fields.Float(compute='_get_payment_total', readonly=True, string="Residual")
    
    batch_seq = fields.Integer(default=1)
    use_contract = fields.Boolean("User Contract", default=True, readonly=True, states={'d': [('readonly', False)]})
    state = fields.Selection([
            ('d','Draft'),
            ('o','Open'),
            ('p', 'Posted'),
        ], string='Status', readonly=True, default='d', copy=False)
    
    
    is_comp = fields.Boolean("Companies", readonly=True, states={'d': [('readonly', False)]})
    
    month = fields.Selection([
            ('0','0'),
            ('01','1'),
            ('02','2'),
            ('03','3'),
            ('04','4'),
            ('05','5'),
            ('06','6'),
            ('07','7'),
            ('08','8'),
            ('09','9'),
            ('10','10'),
            ('11','11'),
            ('12','12')]
        , copy=False, default='0', readonly=True, states={'d': [('readonly', False)]})
    
    all_receipt = fields.Text("Past All Receipts", readonly=True, states={'d': [('readonly', False)]})
    
    
    
    def _get_payment_total(self):
        for r in self:
            residual = 0.0
            amount_total = 0.0
            r.payment_line_ids._get_res()
            for line in r.payment_line_ids:
                residual += line.residual
                amount_total += line.amount_total
            
            r.amount_total = amount_total
            r.residual = residual
            r.payment_total =  amount_total - residual
              
    
       
    def _compute_receipt(self):
        pass
     
        
    @api.onchange('receipt_id')
    def _receipt_changed(self):
        
        if not self.receipt_id:
            return {'value': {'receipt_id': False}}
        
        batch_payment_line_obj = self.env['tms.batch.payment.line']
        
        
        qq = 'SELECT id FROM tms_receipt WHERE batch_payment_id IS NULL AND residual > 0 AND (name= %s OR receipt_no=%s) AND partner_id=%s'
        self.env.cr.execute(qq, (self.receipt_id, self.receipt_id, self.partner_id.id))
        rid = False
        for st in self.env.cr.dictfetchall():
            rid = st['id']
        
        rids = []
        if rid:
            found = False
            for line in self.payment_line_ids:
                if line.receipt_id and line.receipt_id.id == rid:
                    found = True
                    break
                else:
                    rids.append(line.id)
            if not found:
                bpl = batch_payment_line_obj.create({'batch_payment_id': self.id, 'receipt_id': rid})  
                bpl._compute_amount()
                rids.append(bpl.id)
                #self.write({'payment_line_ids': [(6, 0, rids)]})
                #self.env.cr.commit()
                return {'value': {'payment_line_ids': [(6, 0, rids)], 'receipt_id': False}}
            return {'value': {'receipt_id': False}}
        qq = 'SELECT id FROM tms_itrans WHERE batch_payment_id IS NULL AND residual > 0 AND (name= %s OR receipt_no=%s) AND partner_id=%s'
        self.env.cr.execute(qq, (self.receipt_id, self.receipt_id, self.partner_id.id))
        rid = False
        for st in self.env.cr.dictfetchall():
            rid = st['id']
        if rid:
            found = False
            for line in self.payment_line_ids:
                if line.trans_id and line.trans_id.id == rid:
                    found = True
                    break
                else:
                    rids.append(line.id)
            if not found:
                bpl = batch_payment_line_obj.create({'batch_payment_id': self.id, 'trans_id': rid})  
                bpl._compute_amount()   
                rids.append(bpl.id)
                self.write({'payment_line_ids': [(6, 0, rids)]})
                
                return {'value': {'payment_line_ids': [(6, 0, rids)], 'receipt_id': False}}        
            return {'value': {'receipt_id': False}}
        
        return {'warning': {'message': _('This receipt dose not meet the search about or not exists!')}, 'value': {'receipt_id': False} }    
        
    @api.onchange('partner_id')
    def _partner_changed(self):
        """
        if len(self.payment_line_ids):
            receipt_ids = [(3, [rec.id for rec in self.receipt_ids])]
            super(BatchReceiptPayment, self).write({'receipt_ids': receipt_ids})
        """
        vals = {'move_id': False, 'payment_line_ids': [(6, 0, [])]}
        domain = {'move_id': [('id', '=', 0)]}
        if self.partner_id:
            mdoman = [('is_comp', '=', self.partner_id.is_company)]
            mdoman.append(('branch_id', '=', self.branch_id.id))
            move_id = self.env['tms.move'].search(mdoman, limit=1)
            vals['move_id'] = move_id.id if move_id else False
            domain['move_id'] = mdoman
             
        return {'domain': domain, 'value': vals}
    
    @api.onchange('is_comp')
    def _is_comp_changed(self):
        return {'value': {'partner_id': False, 'move_id': False, 'payment_line_ids': [(6, 0, [])]},
                 'domain': {'partner_id': [('is_company', '=', self.is_comp), ('customer', '=', True)]}}
    
    
    
    def action_down_receipts(self):
        if len(self.payment_line_ids):
            self.payment_line_ids.unlink()
        
        batch_payment_line_obj = self.env['tms.batch.payment.line']
        rids = []
        
        
        receipt_domain = [ ('residual', '>', 0), ('invoice_id', '!=', False), ('batch_payment_id', '=', False), ('partner_id', '=', self.partner_id.id)]
        
         
        if self.month and self.month != '0':
            start, end = self._get_dates()
            receipt_domain += [('receipt_date', '>=', start)]
            receipt_domain += [('receipt_date', '<=', end)]
        
        if self.use_contract:
            receipt_domain.append(('contract_no', '=', self.contract_no))
            
        receipt = self.env['tms.receipt'].with_context({'current': False}).search(receipt_domain)
        
        if receipt:
            for r in receipt:
                bpl = batch_payment_line_obj.create({'batch_payment_id': self.id, 'receipt_id': r.id})
                rids.append(bpl.id)
        
        trans = self.env['tms.itrans'].with_context({'current': False}).search(receipt_domain)
        
        if trans:
            for r in trans:
                bpl = batch_payment_line_obj.create({'batch_payment_id': self.id, 'trans_id': r.id})
                rids.append(bpl.id)
        

        vals = {}
        vals['payment_line_ids'] = [(6, 0, rids)]
        super(BatchPayment, self).write(vals)
        
        self.payment_line_ids._recompute_amount()
    
    
    
    
    def cancel_payments(self):
        
        self.ensure_one()
        
        cr = self.env.cr
        cr.execute("""SELECT MIN(date) AS date FROM tms_payments WHERE batch_payment_id=%s""", (self.id,))
        date = False
        for st in cr.fetchall():
            date = st[0]
            break
        
        if date:
            
            lock_date = max(self.env.user.company_id.period_lock_date or '0000-00-00', self.env.user.company_id.fiscalyear_lock_date or '0000-00-00')
            if self.user_has_groups('account.group_account_manager'):
                lock_date = self.env.user.company_id.fiscalyear_lock_date
            if date <= (lock_date or '0000-00-00'):
                if self.user_has_groups('account.group_account_manager'):
                    message = _("You cannot add/modify entries prior to and inclusive of the lock date %s") % (lock_date)
                else:
                    message = _("You cannot add/modify entries prior to and inclusive of the lock date %s. Check the company settings or ask someone with the 'Adviser' role") % (lock_date)
                raise UserError(message)
            
            cr.execute("""DELETE FROM account_move WHERE
             id IN(SELECT amove_id FROM tms_payments WHERE amove_id IS NOT NULL and batch_payment_id=%s)""", (self.id,))
            
            
            for p in self.env['tms.payments'].search([('batch_payment_id', '=', self.id)]):
                p.unlink()
            
            super(BatchPayment, self).write({'state': 'd'})
            
            self.payment_line_ids.unlink()
            
        return True
    
    
    def action_post(self):
        batch = self
        amount = 0;
        
        #batch.payment_line_ids._recompute_amount()
        #self.env.cr.commit()
        
        if self.amount <= 0:
            raise ValidationError(_('Please enter a valid amount to post'))
        
        for line in batch.payment_line_ids:
            line._get_amount_total()
            if line.amount > line.residual:
                raise ValidationError(_('Payment made greater than the remaining %s > %s on %s' % (line.amount, line.residual, line.receipt_no)))
            amount += line.amount
                
        amount = round(amount, 2)
        
        if amount != self.amount:
            raise ValidationError(_('The submitted amount is not equal to the value of the receipts (%s != %s)') %(amount, self.amount))
        
        batch_reference = "%s-%s" %(self.batch_no, self.batch_seq)
        
        Payments = self.env['tms.payments']
        for r in batch.payment_line_ids:
            if r.amount > 0:
                
                vals = {
                    'journal_id': batch.journal_id.id,
                    'move_id' : batch.move_id.id,
                    'note': batch.note,
                    'type': 'inbound',
                    'date': self.date,
                    'payment_branch_id': self.branch_id.id,
                    'amount': r.amount,
                    'currency_id': (r.receipt_id if r.receipt_id else r.trans_id).currency_id.id,
                    'partner_id': batch.partner_id.id,
                    'receipt_id': r.receipt_id.id if r.receipt_id else False,
                    'trans_id': r.trans_id.id if r.trans_id else False,
                    'source': 1 if r.receipt_id else 3,
                    'batch_reference': batch_reference,
                    'batch_payment_id': self.id
                }
                Payments.create(vals)
        
        
        batch.payment_line_ids._recompute_amount()
        batch.payment_line_ids.write({'amount': 0.0})
                
        post_all = True
        
        for line in batch.payment_line_ids:
            if line.residual > 0:
                post_all = False
                break
        
        if self.state == 'p':
            raise ValidationError(_('The batch payment was changed out'))
        
        
        
        self.env['tms.batch.payment.history'].create({'batch_payment_id': batch.id, 
                                                      'amount': self.amount,
                                                      'date': fields.Date.today(),
                                                      'journal_id': self.journal_id.id,
                                                      'note': self.note,
                                                      'batch_reference': batch_reference})
        
        self.write({'state': 'p' if post_all else 'o', 'amount': 0.0, 'batch_seq': self.batch_seq+1, 'date': self.date if post_all else False})
    
    
    def action_recompute(self):
        self.payment_line_ids._recompute_amount()
       
    @api.model
    def create(self, vals):
        vals['branch_id'] = self.env.user.branch_id.id
        vals['batch_no'] = self.env.user.branch_id.batch_payment_seq_id.sudo()._next()
        ret = super(BatchPayment, self).create(vals) 
        ret.parse_receipt()
        return ret
    
    def write(self, vals):
        ret = super(BatchPayment, self).write(vals) 
        for r in self:
            r.parse_receipt()
        return ret
        
        
    
    def unlink(self):
        for batch in self:
            if batch.state != 'd':
                raise ValidationError(_('The batch payment was posted before'))
            if batch.payment_line_ids:
                batch.payment_line_ids.unlink()
        
        super(BatchPayment, self).unlink() 

       
    
    def name_get(self):
        result = []
        for line in self:
            result.append((line.id, line.batch_no or str(line.id)))
        return result
    
    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        if self._context.get('current', None):
            branch_id = self.env.user.branch_id
            if args:
                from odoo.osv import expression
                args = expression.AND([[ ('branch_id', '=', branch_id.id)], args])
            else:
                args = [ ('branch_id', '=', branch_id.id)]
        
        return super(BatchPayment, self)._search(args, offset=offset, limit=limit, order=order, count=count, access_rights_uid=access_rights_uid)
    
    def _get_dates(self):
        now = datetime.datetime.now()
        year = now.year
        days = calendar.monthrange(now.year, int(self.month))[1]
        """
        if int(self.month) == 2:
            days = 28
            if year % 4 == 0:
                days = 29
        """
        
        start = "%s-%s-01" % (year, self.month)
        end = "%s-%s-%s" % (year, self.month, days)
        start, end = common.dates_to_utc_timestamps(self, start, end)
        
        return start, end
    
    def parse_receipt(self):
        
        if self.all_receipt:
            batch_payment_line_obj = self.env['tms.batch.payment.line']
            ls = re.findall(r'\S+', self.all_receipt)
            
            for rname in ls:
                qq = 'SELECT id FROM tms_receipt WHERE batch_payment_id IS NULL AND residual > 0 AND receipt_no=%s AND partner_id=%s'
                self.env.cr.execute(qq, (rname, self.partner_id.id))
                rid = False
                receipt = None
                for st in self.env.cr.dictfetchall():
                    rid = st['id']
                    bpl = batch_payment_line_obj.create({'batch_payment_id': self.id, 'receipt_id': rid})
                    receipt = self.env['tms.receipt'].browse(rid)
                    
                if not rid:       
                    qq = 'SELECT id FROM tms_itrans WHERE batch_payment_id IS NULL AND residual > 0 AND receipt_no=%s AND partner_id=%s'
                    self.env.cr.execute(qq, (rname, self.partner_id.id))
                    rid = False
                    for st in self.env.cr.dictfetchall():
                        rid = st['id']
                        bpl = batch_payment_line_obj.create({'batch_payment_id': self.id, 'trans_id': rid})
                        
                        receipt = self.env['tms.itrans'].browse(rid)
                    
                if not rid:
                    raise ValidationError(_('This receipt (%s) dose not meet the search about or not exists!') % (rname,))
                
                if not receipt.invoice_id:
                    raise ValidationError(_('This receipt (%s) is not invoiced!') % (rname,))
            
            self.write({'all_receipt': False})
    
class BatchPaymentLine(models.Model):
    _name = "tms.batch.payment.line"   
    _order = "date"
    
    batch_payment_id = fields.Many2one('tms.batch.payment')
    
    receipt_id = fields.Many2one('tms.receipt')
    trans_id = fields.Many2one('tms.itrans')
    
    amount_total = fields.Float(compute='_compute_amount', store=True, readonly=True)
    residual = fields.Float(compute='_compute_amount', store=True, readonly=True)
            
    amount = fields.Float()
    
    receipt_no = fields.Char(compute='_get_receipt_no', readonly=True)
    
    source_type = fields.Char(compute='_get_source_type', readonly=True)
    
    state = fields.Char(compute='_get_status', readonly=True)
    
    car_id = fields.Char(compute='_get_amount_total', readonly=True)
    car_model = fields.Char(compute='_get_amount_total', readonly=True)
    
    date = fields.Date(compute='_compute_date', store=True)
    
    
    @api.model
    def create(self, vals):
        ret = super(BatchPaymentLine, self).create(vals)
        if ret.receipt_id:
            ret.receipt_id.sudo().write({'batch_payment_id': vals['batch_payment_id']})
        elif ret.trans_id:
            ret.trans_id.sudo().write({'batch_payment_id': vals['batch_payment_id']})
        return ret
    
    
    def unlink(self):
        for r in self:
            if r.receipt_id:
                r.receipt_id.sudo().write({'batch_payment_id': False})
            elif r.trans_id:
                r.trans_id.sudo().write({'batch_payment_id': False})
        
        return super(BatchPaymentLine, self).unlink()
    
    
    
    def _get_receipt_no(self):
        for r in self:
            r.receipt_no = r.receipt_id.receipt_no if r.receipt_id else r.trans_id.receipt_no
    
    
    def _get_source_type(self):
        for r in self:
            if r.receipt_id:
                r.source_type = _('Receipt')
            elif r.trans_id:
                r.source_type = _('Internal Trans')

    
        
    def _get_status(self):
        
        rdict = False
        idict = False
        for r in self:
            if r.receipt_id:
                if not rdict:
                    rdict = dict(r.receipt_id._fields['state'].selection)
                r.state = rdict.get(r.receipt_id.state)
            elif r.trans_id:
                if not idict:
                    idict = dict(r.trans_id._fields['state'].selection)
                r.state = idict.get(r.trans_id.state)
    
    
       
    def _get_amount_total(self):
        for r in self:
            if r.receipt_id:
                r.amount_total = r.receipt_id.amount_total
                r.residual = r.receipt_id.residual
                r.car_id = r.receipt_id.car_id
                r.car_model = r.receipt_id.model_id.name
            elif r.trans_id:
                r.amount_total = r.trans_id.amount_total
                r.residual = r.trans_id.residual
                r.car_id = r.trans_id.car_id
                r.car_model = r.trans_id.model_id.name
     
       
    def _get_res(self):
        for r in self:
            if r.receipt_id:
                r.amount_totalx = r.receipt_id.amount_total
                r.residualy = r.receipt_id.residual
                r.resid_amount = r.receipt_id.residual
                r.amount_amount = r.receipt_id.amount_total
    
       
    def _get_amount_amount(self):
        for r in self:
            if r.receipt_id:
                r.resid_amount = r.receipt_id.residual
    
    
    def _compute_amount(self):
        for r in self:
            if r.receipt_id:
                r.amount_total = r.receipt_id.amount_total
                r.residual = r.receipt_id.residual
            elif r.trans_id:
                r.amount_total = r.trans_id.amount_total
                r.residual = r.trans_id.residual
            
            r.amount = r.residual
        
    
    def _recompute_amount(self):
        for r in self:
            amount_total = 0
            residual = 0
            if r.receipt_id:
                amount_total = r.receipt_id.amount_total
                residual = r.receipt_id.residual
            elif r.trans_id:
                amount_total = r.trans_id.amount_total
                residual = r.trans_id.residual
            r.write({'amount_total': amount_total, 'residual': residual, 'amount': residual})          

    
    
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
    
    @api.depends('receipt_id', 'trans_id')
    def _compute_date(self):
        for r in self:
            r.date = (r.receipt_id or r.trans_id).date

class BatchPaymentAmount(models.Model):
    _name = "tms.batch.payment.history" 
    batch_payment_id = fields.Many2one('tms.batch.payment')
    batch_reference = fields.Char(readonly=True, string='Reference')
    amount = fields.Float(string="Amount")
    journal_id = fields.Many2one('account.journal', string='Payment Journal')
    date = fields.Date(default=fields.Date.context_today, string='Date')
    note = fields.Char(string='Note')
    