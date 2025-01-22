
from odoo import api, exceptions, fields, models, _
from ..sms import sender,account,sms,utilities
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError
import logging
_logger = logging.getLogger(__name__)

class SmsLog(models.Model):
    _name = 'tms.sms.log'
    _order = "id desc"
    
    mobile = fields.Char("Mobile")
    msg = fields.Text("Message")
    response = fields.Char("Response", size=300)
    date = fields.Datetime("Date")
    state = fields.Selection([("1", "Success"), ("2", "Error"), ("3", "Unknown")], default='3', type='integer')
    partner_id = fields.Many2one('res.partner')
    
    ref = fields.Reference(selection='_selection_target_model')
    
    def send(self):
        status = 3
        response = False
        try:
            auth = utilities.MobilyApiAuth('smb', 'asQW123')
            sender = sms.MobilySMS(auth, [self.mobile], 'SMB', self.msg)
            response = sender.send()
            status = 1
        except Exception as e:
            if isinstance(e, utilities.MobilyApiError):
                response = e.msg_arabic or e.msg_english
            else:
                response = "{0}".format(e)
            status = 2
        
        self.write({'date': fields.Datetime.now(), 'response': response, 'state': status})
        
        return status
    
    
    @api.model
    def _selection_target_model(self):
        models = self.env['ir.model'].search([])
        return [(model.model, model.name) for model in models]
    
    
    def tms_action_send_sms(self):
        auth = utilities.MobilyApiAuth('smb', 'asQW123')
        ICP = self.env['ir.config_parameter'].sudo()    
        new_receipt_msg = ICP.get_param('tms.new_receipt_msg')
        try:
            new_receipt_msg = new_receipt_msg.format(self.car_id, self.name, self.branch_id.name, self.branch_to_id.name) 
            sender = sms.MobilySMS(auth, [self.resv1_mobile], 'SMB', new_receipt_msg)
        except Exception as e:
            raise ValidationError("{0}".format(e))
            return
        try:
            response = sender.send()
            self.post_receipt_message("Sending New Receipt SMS to (%s) success"% (self.resv1_name,))
        except Exception as e:
            if isinstance(e, utilities.MobilyApiError):
                self.post_receipt_message("Sending New Receipt SMS to (%s) error: %s"% (self.resv1_name, e.msg_arabic or e.msg_english))
                raise ValidationError(e.msg_arabic or e.msg_english)
            self.post_receipt_message("Sending New Receipt SMS to (%s) error: %s"% (self.resv1_name, "{0}".format(e)))
            raise ValidationError("{0}".format(e))
        
        
    def tms_action_send_post_sms(self):
        _logger.error("Try to Sending Arrival SMS")
        auth = utilities.MobilyApiAuth('smb', 'asQW123')
        
        ICP = self.env['ir.config_parameter'].sudo()    
        new_receipt_msg = ICP.get_param('tms.arrival_msg')
        try:
            new_receipt_msg = new_receipt_msg.format(self.car_id, self.branch_to_id.name, self.branch_to_id.address or '') 
            sender = sms.MobilySMS(auth, [self.resv1_mobile], 'SMB', new_receipt_msg)
        except Exception as e:
            return 'error'
        try:
            response = sender.send()
            self.post_receipt_message("Sending Arrival SMS to (%s) success"% (self.resv1_name,), commit=False)
        except Exception as e:
            if isinstance(e, utilities.MobilyApiError):
                self.post_receipt_message("Sending Arrival SMS to (%s) error: %s"% (self.resv1_name, e.msg_arabic or e.msg_english), commit=False)
                _logger.error("Error Sending Arrival SMS :%s" %(e.msg_english,))
                return
            self.post_receipt_message("Sending Arrival SMS to (%s) error: %s"% (self.resv1_name, "{0}".format(e)), commit=False)
            _logger.error("Error Sending Arrival SMS")
            
            #raise ValidationError("{0}".format(e))
        