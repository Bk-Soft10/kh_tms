from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class BatchReceiptPost(models.Model):
    _name = "tms.batch.receipt.post"
    _order = "id desc"
    @api.model
    def _get_branch(self):
        return self.env.user.branch_id
    
    
    def _get_default_journal_domain(self):
        branch_id = self.env.user.branch_id
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
            
        return [('id', 'in', ids)]
    
    branch_id = fields.Many2one('tms.branch', string='Branch', required=True, readonly=True, default=_get_branch)
    
    batch_no = fields.Char(string="Number", index=True)
    
    city_id = fields.Many2one('tms.city', related='branch_id.city_id', store=True)
    
    journal_id = fields.Many2one('account.journal', string='Payment Journal',  domain=_get_default_journal_domain,)
    partner_id = fields.Many2one('res.partner', string='Partner', required=True,  domain=[('is_company', '=', True)])
            
    receipt_id = fields.Char(compute='_compute_receipt',)
    
    post_line_ids = fields.One2many('tms.batch.receipt.post.line', 'batch_post_id',)
                
    note = fields.Char(readonly=True, states={'d': [('readonly', False)]})
    
    
    state = fields.Selection([
            ('d','Draft'),
            ('o','Open'),
            ('p', 'Posted'),
        ], string='Status', readonly=True, default='d', copy=False)
    
    resv2_name = fields.Char(string="Actual Recipient", required=True,)
    resv2_id = fields.Char(string="ID", copy=False, required=True,)
    resv2_mobile = fields.Char(string="Mobile", required=True,)
    
    is_comp = fields.Boolean(compute='_is_comp')
    
    date = fields.Date(compute='_compute_date')
    branch_name = fields.Char(related='branch_id.name')
    
    
    def _compute_date(self):
        self.date = fields.Date.to_string(fields.Date.from_string(self.create_date)) if self.create_date else False
    
       
    def _compute_receipt(self):
        for rec in self:
            rec.receipt_id = ' 0 '
        return ' ok'
        pass
    
       
    def _is_comp(self):
        self.is_comp = self.partner_id and self.partner_id.is_company
    
    @api.onchange('partner_id')
    def _partner_changed(self):
        is_comp = self.partner_id and self.partner_id.is_company
        return {'value': {'is_comp': is_comp, 'post_line_ids': [(6, 0, [])]}}
    
    
    @api.onchange('receipt_id')
    def _receipt_changed(self):
        
        if not self.receipt_id:
            return {'value': {'receipt_id': False}}
        
        active_id = self._origin.id
        
        batch_post_line_obj = self.env['tms.batch.receipt.post.line']
        qq = 'SELECT id FROM tms_receipt WHERE state=%s AND (name= %s OR receipt_no=%s) AND partner_id=%s'
        self.env.cr.execute(qq, ('a', self.receipt_id, self.receipt_id, self.partner_id.id))
        rid = False
        for st in self.env.cr.dictfetchall():
            rid = st['id']
        
        rids = []
        if rid:
            found = False
            for line in self.post_line_ids:
                if line.receipt_id and line.receipt_id.id == rid:
                    found = True
                    break
                else:
                    rids.append(line.id)
            if not found:
                bpl = batch_post_line_obj.create({'batch_post_id':active_id, 'receipt_id': rid})  
                bpl._compute_amount()
                rids.append(bpl.id)
                self.write({'post_line_ids': [(6, 0, rids)]})
                #self.env.cr.commit()
                return {'value': {'post_line_ids': [(6, 0, rids)], 'receipt_id': False}}
            return {'value': {'receipt_id': False}}
        
        return {'warning': {'message': _('This receipt dose not meet the search about or not exists!')}, 'value': {'receipt_id': False} }    
        
    
    
    def action_down_receipts(self):
        if len(self.post_line_ids):
            self.post_line_ids.unlink()
        
        batch_post_line_obj = self.env['tms.batch.receipt.post.line']
        rids = []        
        receipt_domain = [('partner_id', '=', self.partner_id.id), ('state', '=', 'a'), ('cur_branch_id', '=', self.env.user.branch_id.id)]
        
        receipt = self.env['tms.receipt'].search(receipt_domain)
        
        if receipt:
            for r in receipt:
                bpl = batch_post_line_obj.create({'batch_post_id': self.id, 'receipt_id': r.id})
                rids.append(bpl.id)
                
        vals = {}
        vals['post_line_ids'] = [(6, 0, rids)]
        super(BatchReceiptPost, self).write(vals)
            
    @api.depends('post_line_ids.residual')
    
    def action_post(self):
        batch = self
        amount = 0;
        
        
        for line in batch.post_line_ids:
            if line.amount > line.residual:
                raise ValidationError(_('Payment made greater than the remaining %s > %s on %s' % (line.amount, line.residual, line.receipt_no)))
            amount += line.amount
        
        
        batch = self
        res = {
            'posted_date': fields.Datetime.now(),
            'posted_by': self.env.uid,
            'resv2_name': batch.resv2_name,
            'resv2_mobile': batch.resv2_mobile,
            'resv2_id': batch.resv2_id,
            }
        
        
        Payments = self.env['tms.payments']
        for r in batch.post_line_ids:
            if r.amount > 0:
                if not self.journal_id:
                    raise ValidationError(_('Please select Journal before payments'))
                vals = {
                    'journal_id': batch.journal_id.id,
                    'communication': batch.note,
                    'type': 'inbound',
                    'amount': r.amount,
                    'currency_id': r.receipt_id.currency_id.id,
                    'partner_id': batch.partner_id.id,
                    'receipt_id': r.receipt_id.id,
                    'source': 1
                }
                Payments.create(vals)
            if r.receipt_id.state != 'e':
                r.receipt_id.action_post(res)
                         
        post_all = True
        batch.post_line_ids._compute_amount()
        for line in batch.post_line_ids:
            if line.residual > 0:
                post_all = False
                break
        
        if not post_all and not batch.partner_id.is_company:
            raise ValidationError(_('Please make all payments before validate'))
            
        
        if self.state == 'p':
            raise ValidationError(_('The batch payment was changed out'))
                
        self.write({'state': 'p'})
        
    
    def action_recompute(self):
        if self.post_line_ids:
            self.post_line_ids._compute_amount()
            
    
    def unlink(self):
        for batch in self:
            if batch.state != 'd':
                raise ValidationError(_('The batch receipt was posted before'))
            if batch.post_line_ids:
                batch.post_line_ids.unlink()
        
        super(BatchReceiptPost, self).unlink() 
    
    
    @api.model
    def create(self, vals):
        vals['branch_id'] = self.env.user.branch_id.id
        # vals['batch_no'] = self.env.user.branch_id.batch_post_seq_id.sudo()._next()
        ret = super(BatchReceiptPost, self).create(vals) 
        ret.write({'batch_no':  self.env.user.branch_id.batch_post_seq_id.sudo()._next()})
        if self.post_line_ids:
            self.post_line_ids._compute_amount()
        
        return ret
          
    
    def write(self, vals):
        ret = super(BatchReceiptPost, self).write(vals) 
        for r in self:
            if r.post_line_ids:
                r.post_line_ids._compute_amount()
        
        return ret
       
       
    
    def name_get(self):
        result = []
        for line in self:
            result.append((line.id, line.batch_no or str(line.id)))
        
        return result

    @api.model
    def _search(self, args, offset=0, limit=None, order=None,  access_rights_uid=None):
        if self._context.get('current', None):
            branch_id = self.env.user.branch_id
            if args:
                from odoo.osv import expression
                args = expression.AND([[ ('branch_id', '=', branch_id.id)], args])
            else:
                args = [ ('branch_id', '=', branch_id.id)]
        
        return super(BatchReceiptPost, self)._search(args, offset=offset, limit=limit, order=order, access_rights_uid=access_rights_uid)

    
    def action_print_report(self):
        return self.env.ref('tms.action_print_btach_post').report_action(self) 

    
    def action_select_receipts(self):
        self.ensure_one()
        context =  dict(self._context)
        context.update({'branch_id': self.branch_id.id, 'selector': 1})
        return {
            'name': _('Select Receipts'),
            'type': 'ir.actions.act_window',
            'res_model': 'tms.batch.receipt.post.selector',
            'view_type': 'form',
            'view_mode': 'form',
            'context': context,
            'target': 'new',
        }

class BatchPostLine(models.Model):
    _name = "tms.batch.receipt.post.line"   
    
    batch_post_id = fields.Many2one('tms.batch.receipt.post')
    
    receipt_id = fields.Many2one('tms.receipt', required=True)
    
    amount_total = fields.Float(compute='_compute', store=True, readonly=True)
    residual = fields.Float(compute='_compute',store=True, readonly=True)
            
    amount = fields.Float()
    
    receipt_no = fields.Char(related='receipt_id.receipt_no', readonly=True)
        
    #state = fields.Selection(related='receipt_id.state', readonly=True)
    
    car_id = fields.Char(related='receipt_id.car_id', readonly=True)
    car_model = fields.Many2one('tms.cmodel', related='receipt_id.model_id')
    
    
    
    @api.model
    def create(self, vals):
        _logger.info(" Create BatchPostLine:%s", vals)
        receipt_id = self.env['tms.receipt'].browse(vals['receipt_id'])
        vals.update({'amount_total': receipt_id.amount_total, 'residual': receipt_id.residual})
        ret = super(BatchPostLine, self).create(vals)
        
        return ret
    
    
    def unlink(self):
        return super(BatchPostLine, self).unlink()
    
    
    @api.depends('receipt_id')
    
    def _compute(self):
        for r in self:
            r.amount_total = r.receipt_id.amount_total
            r.residual = r.receipt_id.residual
        
    @api.depends('receipt_id')
    
    def _compute_amount(self):
        for r in self:
            r.write({'amount_total': r.receipt_id.amount_total, 'residual': r.receipt_id.residual})
    

class BatchPostRecieptSelector(models.TransientModel):
    _name = 'tms.batch.receipt.post.selector'


    def _get_receipt_domain(self):
        active_id = self.env.context.get('active_id')
        if not active_id:
            return [('id', '=', 0)]
        batch = self.env['tms.batch.receipt.post'].browse(active_id)[0]
        
        domain = [('state', 'in', ('a', 't')), ('cur_branch_id', '=', batch.branch_id.id), ('partner_id', '=', batch.partner_id.id)]
        
        return []
        return domain
     
       
    receipt_ids = fields.Many2many('tms.receipt', 'tms_batch_receipt_post_rel', 'bid', 'rid', 'Receipts',
                                    context={'selector': True}, domain=_get_receipt_domain) #
    
    
    
    def select_receipts(self):
        #trips = self.env['tms.trip']
        #[data] = self.read()
        
        active_id = self.env.context.get('active_id')
        
        
        if not active_id:
            raise UserError(_('No active batch for this selection'))
                        
        batch = self.env['tms.batch.receipt.post'].browse(active_id)[0]
        
        
        branch_id = self.env.user.branch_id
        
        
        #ids = self.receipt_ids.mapped('id')
        
        batch_post_line_obj = self.env['tms.batch.receipt.post.line']
        #receipt_obj = self.env['tms.receipt']
        
        #receipts = receipt_obj.browse(self.receipt_ids.mapped('id'))
        
        #for receipt in self.env['tms.trip'].browse(data['receipt_ids']):
        for receipt_id in self.receipt_ids:
            
            if receipt_id.state not in ['a', 't']:
                raise UserError(_('The receipt (%s) is not in arrival nor transient')% (receipt_id.name,))
            
            bpl = batch_post_line_obj.create({'batch_post_id': active_id, 'receipt_id': receipt_id.id})
        
        if self.receipt_ids:    
            ids = tuple(self.receipt_ids.mapped('id'))
            self._cr.execute("DELETE FROM tms_batch_receipt_post_rel WHERE rid IN %s", (ids,))
        #trips.compute_sheet()
        return {'type': 'ir.actions.act_window_close'}
