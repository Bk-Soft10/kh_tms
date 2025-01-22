# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)

class TripRecieptSelector(models.TransientModel):
    _name = 'tms.trip.receipt.selector'
    _description = 'Generate trips for all selected receipts'


    def _get_receipt_domain(self):
        params = self._context.get('params')
        active_id = self._context.get('active_id')
        # active_id = params['trip']
        _logger.info("--------------self._context---"+str(self._context))
        _logger.info("--------------self._context---"+str(self.env.context))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))

        # if not active_id:
        #     return [('id', '=', 0)]
        states = ('state', 'in', ['b', 't'])
        trip = self.env['tms.trip'].browse(active_id)
        
        #trip_route_count= self.env['tms.receipt.route'].search([('trip_id','=', active_id)], count=True)
        domain = [('id', '=', 0)]
        if trip.is_internal:
            if trip.internal_type =='1':
                domain = [('state', '=', 'b'), ('trip_id', '=', False), ('cur_branch_id', '=', self.env.user.branch_id.id)]
            elif trip.internal_type =='2':
                domain = [('state', '=', 'a'), ('partner_id', '=', trip.partner_id.id), ('trip_id', '=', False), ('cur_branch_id', '=', self.env.user.branch_id.id)]
        else:
            domain = [states, ('trip_id', '=', False), ('cur_branch_id', '=', self.env.user.branch_id.id)]
        
        _logger.info("_get_receipt_domain is_internal: %s, internal_type: %s", trip.is_internal, trip.internal_type)
        
        #if True:
        #    raise ValidationError("_get_receipt_domain is_internal: %s, internal_type: %s" % (trip.is_internal, trip.internal_type))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        _logger.info("--------------active_id---"+str(active_id))
        return domain
     
       
    

    receipt_ids = fields.Many2many('tms.receipt', 'tms_trip_route_receipt_rel', 'trip_id', 'receipt_id', 'Receipts',
                                    context={'selector': True}, domain=_get_receipt_domain)
    
    
    receipt_id = fields.Char(store=False)
    
    @api.onchange('receipt_id')
    def _receipt_changed(self):
        if not self.receipt_id:
            return {}
        active_id = self._context.get('active_id')
        branch_id = self.env.user.branch_id
        trip = self.env['tms.trip'].browse(active_id)
        
        if trip.is_internal:
            if trip.internal_type ==1:
                q = 'SELECT id FROM tms_receipt WHERE state=%s AND trip_id IS NULL AND cur_branch_id = %s AND (name = %s OR receipt_no = %s)'
                self.env.cr.execute(q, ('b', branch_id.id, self.receipt_id, self.receipt_id,))
            elif trip.internal_type ==2:
                q = 'SELECT id FROM tms_receipt WHERE state=%s AND partner_id=%s AND trip_id IS NULL AND cur_branch_id = %s AND (name = %s OR receipt_no = %s)'
                self.env.cr.execute(q, ('a', trip.partner_id.id, branch_id.id, self.receipt_id, self.receipt_id,))
        else: 
            q = 'SELECT id FROM tms_receipt WHERE state IN %s AND trip_id IS NULL AND cur_branch_id = %s AND (name = %s OR receipt_no = %s)'
            self.env.cr.execute(q, (('b', 't') , branch_id.id, self.receipt_id, self.receipt_id,))
        
        
        receipt_id = None
        for st in self.env.cr.dictfetchall():
            receipt_id = st['id']
            break
        
        if not receipt_id:
            return {'warning': {'message': 'The receipt not exists !'}, 'value':{'receipt_id': False}}
        
        
        for r in self.receipt_ids:
            if r.id == receipt_id:
                return
        
        ids = self.receipt_ids.mapped('id')
        newids = []
        newids.extend(ids)
        newids.append(receipt_id)
        rec = self.env['tms.receipt'].search([('id','=',receipt_id)])
        rec[0].write({'trip_id': active_id})
        
        return {'value': {'receipt_ids': [(6, 0, newids)], 'receipt_id': False}}
        
    

    def compute_trip(self):
        #trips = self.env['tms.trip']
        #[data] = self.read()
        
        active_id = self._context.get('active_id')
        
        
        if not active_id:
            raise UserError(_('No active trip for this selection'))
                        
        trip = self.env['tms.trip'].browse(active_id)
        
        active_route_id = trip._get_current_route()
        
        branch_id = self.env.user.branch_id
        
        #if not active_route_id:
        #    raise UserError(_("You must select trip route(s) to generate receipt trip(s)."))
        
        #_logger.info("***** Upload receipts: %s ", self.receipt_ids.mapped('id'))
        
        now = fields.Datetime.now()
        
        receipt_route_obj = self.env['tms.receipt.route']
        #receipt_obj = self.env['tms.receipt']
        
        #receipts = receipt_obj.browse(self.receipt_ids.mapped('id'))
        
        #for receipt in self.env['tms.trip'].browse(data['receipt_ids']):
        for receipt_id in self.receipt_ids:
            #slip_data = self.env['hr.payslip'].onchange_receipt_id(from_date, to_date, receipt.id, contract_id=False)
            if receipt_id.cur_branch_id.id != branch_id.id or trip.cur_branch_id.id != branch_id.id:
                raise UserError(_('The receipt (%s) currently in the different branch than the current trip branch')% (receipt_id.name,))
            
            if trip.is_internal:
                if trip.internal_type == 1 and receipt_id.state != 'b':
                    raise UserError(_('The receipt (%s) is not in branch') % (receipt_id.name,))
                elif trip.internal_type == 2 and receipt_id.state != 'a':
                    raise UserError(_('Just choose arrival receipts, Please check the receipt [%s] or remove it from this trip')  % (receipt_id.name))
            elif receipt_id.state not in ['b', 't']:
                raise UserError(_('The receipt (%s) is not in branch nor transient') % (receipt_id.name,))
            
            if  receipt_id.trip_id:
                raise UserError(_('The receipt (%s) already uploaded to another trip')% receipt_id.name )
            

            receipt_id.no_validate(self._context).super_write({'trip_id': active_id})
            # write({'trip_id': active_id})
            _logger.info(active_id)
            _logger.info("active_id")
            res = {
                'receipt_id': receipt_id.id, #receipt.id for the first case
                'trip_id': active_id,
                'trip_route_id': active_route_id.id if active_route_id else False,
                'state': 'u', #state up
                'up_date': now
            }
            receipt_route_obj.create(res)
        if self.receipt_ids:   
            ids = tuple(self.receipt_ids.mapped('id'))
            self._cr.execute("DELETE FROM tms_trip_route_receipt_rel WHERE receipt_id IN %s", (ids,))
        #trips.compute_sheet()
        return {'type': 'ir.actions.act_window_close'}
