from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)

class BatchReceiptPrint(models.Model):
    _name = "tms.batch.receipt.print"
    _order = "id desc"
    @api.model
    def _get_branch(self):
        return self.env.user.branch_id
    
    batch_no = fields.Char(string="Number", index=True)
    
    branch_id = fields.Many2one('tms.branch', string='Branch', required=True, readonly=True, default=_get_branch)
        
    partner_id = fields.Many2one('res.partner', string='Partner', required=True, readonly=True, states={'d': [('readonly', False)]}, domain=[('customer', '=', True)])
            
    receipt_id = fields.Char(compute='_compute_receipt', search='_search_receipt_no', readonly=True, states={'d': [('readonly', False)]})
    
    print_line_ids = fields.One2many('tms.batch.receipt.print.line', 'batch_print_id', readonly=True, states={'d': [('readonly', False)]})
                
    note = fields.Char(readonly=True, states={'d': [('readonly', False)]})
    
    is_comp = fields.Boolean("Companies", readonly=True, states={'d': [('readonly', False)]})
    
    
    
    state = fields.Selection([
            ('d','Draft'),
            ('p', 'Printed'),
        ], string='Status', readonly=True, default='d', copy=False)
    
    resv_name = fields.Char(string="Recipient", required=True, readonly=True, states={'d': [('readonly', False)]})
    resv_mobile = fields.Char(string="Mobile", required=True, readonly=True, states={'d': [('readonly', False)]})
            
    date = fields.Date(compute='_compute_date')
    branch_name = fields.Char(related='branch_id.name')
    
    receipt_from = fields.Char("Receipt From", readonly=True, states={'d': [('readonly', False)]})
    receipt_to = fields.Char("Receipt To", readonly=True, states={'d': [('readonly', False)]})
    
    is_internal = fields.Boolean("Is Internal")
    
    
    
    def _compute_date(self):
        self.date = fields.Date.to_string(fields.Date.from_string(self.create_date)) if self.create_date else False
    
       
    def _compute_receipt(self):
        self.is_comp = self.partner_id and self.partner_id.is_company
    
    @api.onchange('partner_id')
    def _partner_changed(self):
        is_comp = self.partner_id and self.partner_id.is_company
        return {'value': {'is_comp': is_comp, 'print_line_ids': [(6, 0, [])]}}
    
    @api.onchange('is_comp')
    def _is_comp_changed(self):
        return {'value': {'partner_id': False, 'print_line_ids': [(6, 0, [])]},
                 'domain': {'partner_id': [('is_company', '=', self.is_comp), ('customer', '=', True)]}}
    
    
    def _search_receipt_no(self, operator, value):
        qq = """SELECT p.id FROM  tms_batch_receipt_print_line l 
                INNER JOIN tms_batch_receipt_print p ON p.id=l.batch_print_id 
                INNER JOIN tms_receipt r ON r.id=l.receipt_id 
                WHERE r.receipt_no=%s OR r.name=%s"""
        ids = []
        self._cr.execute(qq, (value, value))
        for st in self._cr.fetchall():
            ids.append(st[0])
            
        return [('id', "in", ids)]
    
    
    @api.onchange('receipt_id')
    def _receipt_changed(self):
        
        if not self.receipt_id:
            return {'value': {'receipt_id': False}}
        
        active_id = self._origin.id
        
        batch_print_line_obj = self.env['tms.batch.receipt.print.line']
        qq = 'SELECT id FROM tms_receipt WHERE state=%s AND (name= %s OR receipt_no=%s) AND partner_id=%s'
        self.env.cr.execute(qq, ('b', self.receipt_id, self.receipt_id, self.partner_id.id))
        rid = False
        for st in self.env.cr.dictfetchall():
            rid = st['id']
        
        rids = []
        if rid:
            found = False
            for line in self.print_line_ids:
                if line.receipt_id and line.receipt_id.id == rid:
                    found = True
                    break
                else:
                    rids.append(line.id)
            if not found:
                bpl = batch_print_line_obj.create({'batch_print_id':active_id, 'receipt_id': rid})  
                bpl._compute_amount()
                rids.append(bpl.id)
                self.write({'print_line_ids': [(6, 0, rids)]})
                #self.env.cr.commit()
                return {'value': {'print_line_ids': [(6, 0, rids)], 'receipt_id': False}}
            return {'value': {'receipt_id': False}}
        
        return {'warning': {'message': _('This receipt dose not meet the search about or not exists!')}, 'value': {'receipt_id': False} }    
        
    
    
    def action_down_receipts(self):
        if len(self.print_line_ids):
            self.print_line_ids.unlink()
        receipt = []
        trans = []
        batch_print_line_obj = self.env['tms.batch.receipt.print.line']
        if self.receipt_from or self.receipt_to:
            
            if not self.receipt_from:
                self.receipt_from = self.receipt_to
            elif not self.receipt_to:
                self.receipt_to = self.receipt_from
                
            ids = []
            qq = "SELECT id FROM tms_receipt WHERE partner_id=%s AND receipt_no::bigint>=%s AND receipt_no::bigint<=%s" % (self.partner_id.id, self.receipt_from, self.receipt_to)
            self._cr.execute(qq)
            for st in self._cr.fetchall():
                ids.append(st[0])
            if ids:
                receipt = self.env['tms.receipt'].browse(ids)
            else:
                ids = []
                qq = "SELECT id FROM tms_itrans WHERE partner_id=%s AND receipt_no::bigint>=%s AND receipt_no::bigint<=%s" % (self.partner_id.id, self.receipt_from, self.receipt_to)
                self._cr.execute(qq)
                for st in self._cr.fetchall():
                    ids.append(st[0])
                if ids:
                    trans = self.env['tms.itrans'].browse(ids)
            
            #raise ValidationError("partner_id: %s, ids: %s, receipt count: %s, q: %s" % (self.partner_id.id, ids, len(receipt), qq))
        else:
            receipt_domain = [('partner_id', '=', self.partner_id.id), ('state', '=', 'b')]
            receipt = self.env['tms.receipt'].search(receipt_domain)
            if not receipt:
                trans = self.env['tms.itrans'].search([('partner_id', '=', self.partner_id.id), ('state', 'not in', ('d', 'c'))])
        
        rids = []
        for r in receipt:
            bpl = batch_print_line_obj.create({'batch_print_id': self.id, 'receipt_id': r.id})
            rids.append(bpl.id)
    
        for r in trans:
            bpl = batch_print_line_obj.create({'batch_print_id': self.id, 'trans_id': r.id})
            rids.append(bpl.id)
        
        vals = {}
        vals['print_line_ids'] = [(6, 0, rids)]
        super(BatchReceiptPrint, self).write(vals)
            
    @api.depends('print_line_ids.residual')
    
    def action_post(self):
        if self.state != 'p':
            self.write({'state': 'p'})
        
        
    
    def action_recompute(self):
        if self.print_line_ids:
            self.print_line_ids._compute_amount()
            
    
    def unlink(self):
        for batch in self:
            if batch.state != 'd':
                raise ValidationError(_('The batch receipt was printed before'))
            if batch.print_line_ids:
                batch.print_line_ids.unlink()
        
        super(BatchReceiptPrint, self).unlink() 
    
    
    @api.model
    def create(self, vals):
        vals['branch_id'] = self.env.user.branch_id.id
        vals['batch_no'] = self.env.user.branch_id.next_sequence('batch_print_seq_id')
        
        ret = super(BatchReceiptPrint, self).create(vals) 
        if self.print_line_ids:
            self.print_line_ids._compute_amount()
        
        return ret
          
    
    def write(self, vals):
        ret = super(BatchReceiptPrint, self).write(vals) 
        for r in self:
            if r.print_line_ids:
                r.print_line_ids._compute_amount()
        
        return ret
       
       
    
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
        
        return super(BatchReceiptPrint, self)._search(args, offset=offset, limit=limit, order=order, count=count, access_rights_uid=access_rights_uid)

    
    def action_print_report(self):
        return self.env.ref('tms.action_print_btach_print').report_action(self) 
    
    
    def action_print(self):
        return self.env.ref('tms.action_print_btach_print').report_action(self) 

    
    def action_select_receipts(self):
        self.ensure_one()
        context =  dict(self._context)
        context.update({'branch_id': self.branch_id.id, 'selector': 1,
                         'is_internal': self.is_internal, 'default_is_internal': self.is_internal})
        return {
            'name': _('Select Receipts'),
            'type': 'ir.actions.act_window',
            'res_model': 'tms.batch.receipt.print.selector',
            'view_type': 'form',
            'view_mode': 'form',
            'context': context,
            'target': 'new',
        }
    

class BatchPrintLine(models.Model):
    _name = "tms.batch.receipt.print.line"   
    
    
    batch_print_id = fields.Many2one('tms.batch.receipt.print')
    
    receipt_id = fields.Many2one('tms.receipt')
    trans_id = fields.Many2one('tms.itrans')
    
    amount_total = fields.Float(compute='_compute', store=True, readonly=True)
    residual = fields.Float(compute='_compute',store=True, readonly=True)
    payment = fields.Float(compute='_compute',store=True, readonly=True)
    receipt_no = fields.Char(compute='_compute', readonly=True)
    branch_to_id = fields.Many2one('tms.branch', related='receipt_id.branch_to_id')
    pay_branch_id = fields.Many2one('tms.branch', compute='_compute')
    
    #state = fields.Selection(related='receipt_id.state', readonly=True)
    
    car_id = fields.Char(compute='_compute', readonly=True)
    car_model = fields.Many2one('tms.cmodel', compute='_compute', readonly=True)
    

    
    @api.model
    def create(self, vals):
        receipt_id =  self.env['tms.receipt'].browse(vals['receipt_id']) if 'receipt_id' in vals else self.env['tms.itrans'].browse(vals['trans_id'])
        vals.update({'amount_total': receipt_id.amount_total, 'residual': receipt_id.residual,
                      'payment': receipt_id.payment_total})
        ret = super(BatchPrintLine, self).create(vals)
        return ret
    
    
    def unlink(self):
        return super(BatchPrintLine, self).unlink()
    
    
    @api.depends('receipt_id', 'trans_id')
    
    def _compute(self):
        for r in self:
            rs = r.receipt_id if r.receipt_id else r.trans_id
            r.amount_total = rs.amount_total
            r.residual = rs.residual
            r.payment = rs.payment_total
            r.car_id = rs.car_id
            r.car_model = rs.model_id
            r.receipt_no = rs.receipt_no
            r.pay_branch_id = rs.pay_branch_id if r.receipt_id else rs.branch_id
            
        
    @api.depends('receipt_id', 'trans_id')
    
    def _compute_amount(self):
        for r in self:
            rs = r.receipt_id if r.receipt_id else r.trans_id
            r.write({'amount_total': rs.amount_total, 'residual': rs.residual,
                      'payment': rs.payment_total})

class BatchRecieptPrintSelector(models.TransientModel):
    _name = 'tms.batch.receipt.print.selector'


    def _get_receipt_domain(self):
        active_id = self.env.context.get('active_id')
        batch = self.env['tms.batch.receipt.print'].browse(active_id)
        if not active_id or batch.is_internal:
            return [('id', '=', 0)]
        batch = self.env['tms.batch.receipt.print'].browse(active_id)[0]
        
        domain = [('state', '=', 'b'), ('cur_branch_id', '=', batch.branch_id.id), ('partner_id', '=', batch.partner_id.id)]
        
        return domain
    
    def _get_itrans_domain(self):
        active_id = self.env.context.get('active_id')
        internal = self.env.context.get('internal')
        batch = self.env['tms.batch.receipt.print'].browse(active_id)
        if not active_id or not batch.is_internal:
            return [('id', '=', 0)]
        
        
        domain = [('state', 'not in', ('d', 'c')), ('branch_id', '=', batch.branch_id.id), ('partner_id', '=', batch.partner_id.id)]
        
        return domain
    
     
       
    receipt_ids = fields.Many2many('tms.receipt', 'tms_batch_receipt_print_rel', 'bid', 'rid', 'Receipts',
                                    context={'selector': True}, domain=_get_receipt_domain) #
    
    
    trans_ids = fields.Many2many('tms.itrans', 'tms_batch_itrans_print_rel', 'bid', 'rid', 'ITrans',
                                    context={'selector': True}, domain=_get_itrans_domain) #
    
    is_internal = fields.Boolean(readonly=True, compute='_get_source')
    
    
    def _get_source(self):
        is_internal = bool(self.env.context.get('internal'))
        for r in self:
            r.is_internal = is_internal
    
    
    def select_receipts(self):
        #trips = self.env['tms.trip']
        #[data] = self.read()
        
        active_id = self.env.context.get('active_id')
        
        
        if not active_id:
            raise UserError(_('No active batch for this selection'))
                        
        batch = self.env['tms.batch.receipt.print'].browse(active_id)[0]
        
                
        batch_print_line_obj = self.env['tms.batch.receipt.print.line']
        
        #batch_print_line_obj.search([('receipt_id', 'not in')])
        #dic = batch_print_line_obj.search_read([('receipt_id', 'not in', ids)], ['receipt_id'])
        
        #receipt_obj = self.env['tms.receipt']
        
        #receipts = receipt_obj.browse(self.receipt_ids.mapped('id'))
        
        #for receipt in self.env['tms.trip'].browse(data['receipt_ids']):
        if self.receipt_ids: 
            receipt_ids = batch.mapped("print_line_ids.receipt_id.id")
            for receipt_id in self.receipt_ids:
                if receipt_id in receipt_ids:
                    continue
                if receipt_id.state != 'b':
                    raise UserError(_('The receipt (%s) is not in branch')% (receipt_id.name,))
                
                bpl = batch_print_line_obj.create({'batch_print_id': active_id, 'receipt_id': receipt_id.id})
               
            ids = tuple(receipt_ids)
            self._cr.execute("DELETE FROM tms_batch_receipt_print_rel WHERE rid IN %s", (ids,))
            
        
        if self.trans_ids: 
            trans_ids = batch.mapped("print_line_ids.trans_id.id")
            for trans_id in self.mapped("trans_ids.id"):
                if trans_id in trans_ids:
                    continue
                
                bpl = batch_print_line_obj.create({'batch_print_id': active_id, 'trans_id': trans_id})
               
            ids = tuple(trans_ids)
            self._cr.execute("DELETE FROM tms_batch_itrans_print_rel WHERE rid IN %s", (ids,))
        
        
        #trips.compute_sheet()
        return {'type': 'ir.actions.act_window_close'}

    