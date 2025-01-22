import pytz
import datetime
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError


class Company(models.Model):
    _inherit = "res.company"

    sec_id = fields.Many2one('ir.sequence', string='Receipt Sequence', copy=False)
    tz = fields.Selection(related='partner_id.tz')
    tz_offset = fields.Char(compute='_compute_tz_offset', string='Timezone offset', invisible=True)
    
    @api.model
    def create(self, vals):
        c = super(Company, self).create(vals)
        seq = {
            'name': c.name,
            'implementation': 'no_gap',
            'prefix': "%s0000" % str(c.id),
            'padding': 8,
            'number_increment': 1,
            'use_date_range': False,
        }
        seq['company_id'] = c.id
        seq = self.env['ir.sequence'].create(seq)
        c.write({'sec_id': seq.id})
        
        return c
    
    @api.depends('tz')
    def _compute_tz_offset(self):
        for company in self:
            company.tz_offset = datetime.datetime.now(pytz.timezone(company.tz or 'GMT')).strftime('%z')
                
    """
    exit_sequence_id = fields.Many2one('ir.sequence', string='Entry Sequence',
        help="This field contains the information related to the numbering of receipt exit.", copy=False)
    
    
    
    @api.model
    def create(self, vals):
        vals.update({'exit_sequence_id': self.sudo()._create_sequence(vals['code'], 'exit-%s' % vals['name']).id})
        branch = super(Company, self).create(vals)
        return branch
    
    @api.multi
    def write(self, vals):
        for c in self:
            if not c.exit_sequence_id :
                seq = self.sudo()._create_sequence(c.id, c.name)
                vals.update({'exit_sequence_id': seq.id})
            
        result = super(Company, self).write(vals)
        return result
    
    
    
    
    def _create_sequence(self, code, name, company_id=False):
        
        prefix = str(code)
        seq = {
            'name': name,
            'implementation': 'no_gap',
            'prefix': prefix,
            'padding': 0,
            'number_increment': 1,
            'use_date_range': False,
        }
        if company_id:
            seq['company_id'] = company_id
        seq = self.env['ir.sequence'].create(seq)
        return seq  
    """