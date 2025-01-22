from datetime import time as datetime_time
from dateutil import relativedelta

from odoo import api, fields, models, tools, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from . import common

from odoo.tools.misc import formatLang, format_date
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, pycompat
from odoo.tools.safe_eval import safe_eval

import logging

_logger = logging.getLogger(__name__)

class BranchTarget(models.Model):
    _name = 'tms.branch.target'
    
    name = fields.Char(readonly=True)
    
    state = fields.Selection([
            ('d','Draft'),
            ('p', 'Posted'),
        ], string='Status', readonly=True, default='d', copy=False)
    
    
    month = fields.Selection([
            ("1", "1"),
            ("2", "2"),
            ("3", "3"),
            ("4", "4"),
            ("5", "5"),
            ("6", "6"),
            ("7", "7"),
            ("8", "8"),
            ("9", "9"),
            ("10", "10"),
            ('11', "11"),
            ('12', "12")
            ], required=True, readonly=True, states={'d': [('readonly', False)]})
    
    year = fields.Selection([
        ("2018", "2018"),
        ("2019", "2019"),
        ("2020", "2020"),
        ("2021", "2021"),
        ("2022", "2022"),
        ("2023", "2023"),
        ('2024', "2024"),
        ("2025", "2025"),
        ("2026", "2026"),
        ('2027', "2027")
        ], required=True, readonly=True, states={'d': [('readonly', False)]})
    
    
    vdate = fields.Integer()
    
    target = fields.Float(compute='_compute_target', store=True)
    
    line_ids = fields.One2many('tms.branch.target.line', 'branch_target_id', readonly=True, states={'d': [('readonly', False)]})
    
    
    _sql_constraints = [
            ('branch_target_uniq', 'unique(month, year)', 'The target already exists!'),
        ]
    
    @api.model
    def create(self, vals):
        
        vmonth = int(vals['month'])
        vyear = int(vals['year'])
            
        name = "%s/" % vmonth
        
        if vmonth < 10:
            name = "0%s/" % vmonth
        name = name + str(vyear)
        vals['name'] = name
        vals['vdate'] = int(str(vyear) + (("0%s" % vmonth) if vmonth < 10 else str(vmonth)))
        
        return models.Model.create(self, vals)
    
    
    
    def write(self, values):
        
        vmonth = 0
        vyear = 0
        
        if 'month' in values:
            vmonth = int(values['month'])
        
        if 'year' in values:
            vyear = int(values['year'])
                
        if vmonth > 0 or vyear > 0:
            if vyear == 0:
                vyear = int(self[0].year)
        
            if vmonth == 0:
                vmonth = int(self[0].month)  
            
            name = "%s/" % vmonth
    
            if vmonth < 10:
                name = "0%s/" % vmonth
                
            values['vdate'] = int(str(vyear) + (("0%s" % vmonth) if vmonth < 10 else str(vmonth)))
                
            name = name + str(vyear)
            values['name'] = name
            
            #raise ValidationError("%s" % values)
            
        models.Model.write(self, values)
    
    
    def action_post(self):
        self.state = 'p'
    
    
    def action_create_target_lines(self):
        branch_ids = self.env['tms.branch'].search([('costcenter1_id', "!=", False)])
        self.line_ids = [(0, 0, {'branch_id': b.id, 'month': self.month, 'year': self.year}) for b in branch_ids]
    
    
    @api.depends('line_ids.target')
    
    def _compute_target(self):
        for s in self:
            s.target = sum([l.target for l in s.line_ids])
        
    
class BranchTargetLine(models.Model):
    _name = 'tms.branch.target.line'  
    
    branch_target_id = fields.Many2one('tms.branch.target', required=True)
    
    branch_id = fields.Many2one('tms.branch', required=True)
    
    vdate = fields.Integer(related='branch_target_id.vdate', store=True)
    
    target = fields.Float()
    
    
    _sql_constraints = [
            ('branch_target_line_uniq', 'unique(branch_target_id, branch_id)', 'The branch already exists!'),
        ]
    
    