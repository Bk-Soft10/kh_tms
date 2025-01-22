import time
import calendar
from datetime import datetime
from datetime import time as datetime_time
from dateutil import relativedelta

from odoo import api, fields, models, tools, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from . import common

from odoo.tools.misc import formatLang, format_date
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, pycompat
from odoo.tools.safe_eval import safe_eval


class TmsCommission(models.Model):
    _name = 'tms.commission'
    _order = "id desc"
    
    code = fields.Char(required=True)
    branch_id = fields.Many2one("tms.branch", required=True)
    amount = fields.Float()
    
    
    
    @api.constrains('code')
    def _check_code(self):
        for c in self:
            if c.code:
                count = self.search([('id', '!=', c.id if c.id else 0), ('code', '=', c.code)], limit=1, count=True)
                if count > 0:
                    raise ValidationError(_('Commission Code already exist'))
    
    @api.model
    def get_branch_info(self, with_user=True):
        user = self.env.user
        branch = user.branch_id
        ramount = rcount = iamount = icount = 0
        # self.sudo(user)
        uramount = urcount =  uiamount = uicount = 0
        
        now = datetime.now()
        #days = calendar.monthrange(now.year, now.month)[1]
        ds = "%s" % now.day if now.day > 9 else "0%s" % now.day
        ms = "%s" % now.month if now.month > 9 else "0%s" % now.month
        
        d1 = "%s-%s-01" % (now.year, ms)
        d2 = "%s-%s-%s" % (now.year, ms, ds)   
        #days = calendar.monthrange(now.year, int(now.month))[1]
        #d1, d2 = common.dates_to_utc_timestamps(self, d1, d2)
        
        q = """SELECT SUM(
                     CASE
                         WHEN r.shipping_type=2 THEN ROUND(COALESCE(.6 * r.amount_untaxed,0.0), 2)
                         ELSE ROUND(COALESCE(r.amount_untaxed,0.0), 2)
                     END) AS amount, count(*)
            FROM tms_receipt r WHERE amount_untaxed > 0 
            AND r.date >=%s AND r.date <=%s AND state NOT IN('c', 'd')
            AND branch_id=%s"""
        self._cr.execute(q, (d1, d2, branch.id))
        for st in self._cr.fetchall():
            ramount = round(st[0] or 0)
            rcount = round(st[1] or 0)
        
        q = """SELECT SUM(amount) AS amount, count(*) 
        FROM tms_itrans r WHERE amount > 0.1
        AND r.date >=%s AND r.date <=%s AND state NOT IN('c', 'd')
        AND branch_id=%s"""
        self._cr.execute(q, (d1, d2, branch.id))
        for st in self._cr.fetchall():
            iamount = round(st[0] or 0)
            icount = round(st[1] or 0)
        
        if with_user:
            q = """SELECT SUM(
                    CASE
                         WHEN r.shipping_type=2 THEN ROUND(COALESCE(.6 * r.amount_untaxed,0.0), 2)
                         ELSE ROUND(COALESCE(r.amount_untaxed,0.0), 2)
                    END) AS amount, count(*) FROM tms_receipt r WHERE amount_total > 0 
            AND r.date >=%s AND r.date <=%s AND state NOT IN('c', 'd') AND create_uid=%s"""
            self._cr.execute(q, (d1, d2, user.id))
            for st in self._cr.fetchall():
                uramount = round(st[0] or 0)
                urcount = round(st[1] or 0)
            
            q = """SELECT SUM(amount), count(*) FROM tms_itrans r WHERE 
            r.date >=%s AND r.date <=%s AND state NOT IN('c', 'd') AND amount > 0.01 AND create_uid=%s"""
            self._cr.execute(q, (d1, d2, user.id))
            for st in self._cr.fetchall():
                uiamount = round(st[0] or 0)
                uicount = round(st[1] or 0)
            
        branch_amount = ramount + iamount
        branch_count = rcount + icount
        
        user_amount = uramount + uiamount
        user_count = urcount + uicount
        
        percent = int(branch_amount / branch.minimum_target * 100) if branch.minimum_target > 0 else 0
        progress = min(percent, 100)
        cclass = 'bg-red'
        if percent < 50:
            pass
        elif percent < 70:
            cclass = 'bg-arrival'
        elif percent < 90:
            cclass = 'bg-trans'
        elif percent <= 101:
            cclass = 'bg-posted'
        else:
            cclass = 'tbg-road'
            
        commission = {
            'target': branch.minimum_target,
            'percent': percent,
            'progress': progress,
            'ramount': ramount,
            'rcount': rcount,
            'iamount': iamount,
            'icount': icount,
            'uramount': uramount,
            'urcount': urcount,
            'uiamount': uiamount,
            'uicount': uicount,
            'branch_amount': branch_amount,
            'branch_count': branch_count,
            'user_amount': user_amount,
            'user_count': user_count,
            'class': cclass
            }
        
        return commission
    
    
class BranchTarget(models.Model):
    _name = 'tms.branch.target'
    _order = "date desc"
    
    date = fields.Date(requred=True, readonly=True, states={'d': [('readonly', False)]})
    state = fields.Selection([('draft', 'Draft'), ('posted', 'Posted')], readonly=True)
    branch_target_line_ids = fields.One2many("tms.branch.target.line", "branch_target_id", states={'d': [('readonly', False)]})
    
    
    @api.constrains('date')
    def _check_date(self):
        for c in self:
            date = fields.Date.from_string(c.date)
            if date.day != 1:
                raise ValidationError(_("The date should be at first day of month"))
            count = self.search([('date', '=', c.date)], count=True)
            if count > 1:
                raise ValidationError(_('This target of this date already exists!'))
    
    
    def write_branches(self):
        
        date = fields.Date.from_string(self.date)
        
        if date.day != 1:
            raise UserError(_("The date should be at first day of month"))
        
        self.write({'branch_target_line_ids': False})
        commands = []
        branches = self.env['tms.branch'].search([('costcenter1_id', '!=', False)])
        for branch in branches:
            commands.append((0, False, {'branch_id': branch.id, 'date': self.date, 'target': 0}))
                
        self.write({'branch_target_line_ids': commands})
        
    
    def name_get(self):
        names = []
        for l in self:
            date = fields.Date.from_string(self.date)
            names.append((l.id, format_date(self.env, date.strftime(DEFAULT_SERVER_DATE_FORMAT), date_format='MMM YYYY')))
        return names
    
    def write_commission(self, receipt_ids, state='register'):
        user = self.env.user
        #branch_target_line_ids
        
        
        #baselocaldict = {'rules': rules, 'payslip': payslips, 'worked_days': worked_days, 'inputs': inputs} 
        
        
        
    
    
class BranchTargetLine(models.Model):
    _name = 'tms.branch.target.line'
    
    branch_target_id = fields.Many2one("tms.branch.target")
    date = fields.Date()
    branch_id = fields.Many2one("tms.branch", "Branch")
    target = fields.Float() 
    

class CommissionRule(models.Model):
    _name = 'tms.commission.rule'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True,
        help="The code of salary rules can be used as reference in computation of other rules. "
             "In that case, it is case sensitive.")
    sequence = fields.Integer(required=True, index=True, default=5,
        help='Use to arrange calculation sequence')
    quantity = fields.Char(default='1.0',
        help="It is used in computation for percentage and fixed amount. "
             "For e.g. A rule for Meal Voucher having fixed amount of "
             u"1€ per worked day can have its quantity defined in expression "
             "like worked_days.WORK100.number_of_days.")
    active = fields.Boolean(default=True,
        help="If the active field is set to false, it will allow you to hide the salary rule without removing it.")
    condition_select = fields.Selection([
        ('none', 'Always True'),
        ('range', 'Range'),
        ('python', 'Python Expression')
    ], string="Condition Based on", default='none', required=True)
    condition_range = fields.Char(string='Range Based on', default='contract.wage',
        help='This will be used to compute the % fields values; in general it is on basic, '
             'but you can also use categories code fields in lowercase as a variable names '
             '(hra, ma, lta, etc.) and the variable basic.')
    condition_python = fields.Text(string='Python Condition', required=True,
        default='''
                    # Available variables:
                    #----------------------
                    # payslip: object containing the payslips
                    # employee: hr.employee object
                    # contract: hr.contract object
                    # rules: object containing the rules code (previously computed)
                    # categories: object containing the computed salary rule categories (sum of amount of all rules belonging to that category).
                    # worked_days: object containing the computed worked days
                    # inputs: object containing the computed inputs

                    # Note: returned value have to be set in the variable 'result'

                    result = rules.NET > categories.NET * 0.10''',
        help='Applied this rule for calculation if condition is true. You can specify condition like basic > 1000.')
    condition_range_min = fields.Float(string='Minimum Range', help="The minimum amount, applied for this rule.")
    condition_range_max = fields.Float(string='Maximum Range', help="The maximum amount, applied for this rule.")
    amount_select = fields.Selection([
        ('percentage', 'Percentage (%)'),
        ('fix', 'Fixed Amount'),
        ('code', 'Python Code'),
    ], string='Amount Type', index=True, required=True, default='fix', help="The computation method for the rule amount.")
    amount_fix = fields.Float(string='Fixed Amount', digits=dp.get_precision('Payroll'))
    amount_percentage = fields.Float(string='Percentage (%)', digits=dp.get_precision('Payroll Rate'),
        help='For example, enter 50.0 to apply a percentage of 50%')
    amount_python_compute = fields.Text(string='Python Code',
        default='''
                    # Available variables:
                    #----------------------
                    # payslip: object containing the payslips
                    # employee: hr.employee object
                    # contract: hr.contract object
                    # rules: object containing the rules code (previously computed)
                    # categories: object containing the computed salary rule categories (sum of amount of all rules belonging to that category).
                    # worked_days: object containing the computed worked days.
                    # inputs: object containing the computed inputs.

                    # Note: returned value have to be set in the variable 'result'

                    result = contract.wage * 0.10''')
    amount_percentage_base = fields.Char(string='Percentage based on', help='result will be affected to a variable')
    note = fields.Text(string='Description')

    #TODO should add some checks on the type of result (should be float)
    
    def _compute_rule(self, localdict):
        """
        :param localdict: dictionary containing the environement in which to compute the rule
        :return: returns a tuple build as the base/amount computed, the quantity and the rate
        :rtype: (float, float, float)
        """
        self.ensure_one()
        if self.amount_select == 'fix':
            try:
                return self.amount_fix, float(safe_eval(self.quantity, localdict)), 100.0
            except:
                raise UserError(_('Wrong quantity defined for salary rule %s (%s).') % (self.name, self.code))
        elif self.amount_select == 'percentage':
            try:
                return (float(safe_eval(self.amount_percentage_base, localdict)),
                        float(safe_eval(self.quantity, localdict)),
                        self.amount_percentage)
            except:
                raise UserError(_('Wrong percentage base or quantity defined for salary rule %s (%s).') % (self.name, self.code))
        else:
            try:
                safe_eval(self.amount_python_compute, localdict, mode='exec', nocopy=True)
                return float(localdict['result']), 'result_qty' in localdict and localdict['result_qty'] or 1.0, 'result_rate' in localdict and localdict['result_rate'] or 100.0
            except:
                raise UserError(_('Wrong python code defined for salary rule %s (%s).') % (self.name, self.code))

    
    def _satisfy_condition(self, localdict):
        """
        @param contract_id: id of hr.contract to be tested
        @return: returns True if the given rule match the condition for the given contract. Return False otherwise.
        """
        self.ensure_one()

        if self.condition_select == 'none':
            return True
        elif self.condition_select == 'range':
            try:
                result = safe_eval(self.condition_range, localdict)
                return self.condition_range_min <= result and result <= self.condition_range_max or False
            except:
                raise UserError(_('Wrong range condition defined for salary rule %s (%s).') % (self.name, self.code))
        else:  # python code
            try:
                safe_eval(self.condition_python, localdict, mode='exec', nocopy=True)
                return 'result' in localdict and localdict['result'] or False
            except:
                raise UserError(_('Wrong python condition defined for salary rule %s (%s).') % (self.name, self.code))


    
    
class UserCommissionRule(models.Model):
    _name = 'tms.user.commission.rule' 
    
    user_id = fields.Many2one("res.users", "User")
    branch_id = fields.Many2one("tms.branch", "Branch")
    commission_rule_id = fields.Many2one("tms.commission.rule", "Commission Rule")
    
    amount = fields.Float(digits=dp.get_precision('Payroll'))
    quantity = fields.Float(digits=dp.get_precision('Payroll')) 
    

class Branch(models.Model):
    _inherit = 'tms.branch'
    
    #user_commission_rule_ids = 
    
    
          
class BrowsableObject(object):
    def __init__(self, user_id, dict, env):
        self.user_id = user_id
        self.dict = dict
        self.env = env

    def __getattr__(self, attr):
        return attr in self.dict and self.dict.__getitem__(attr) or 0.0        


class Commission(BrowsableObject):
    """a class that will be used into the python code, mainly for usability purposes"""

    def sum(self, code, from_date, to_date=None):
        if to_date is None:
            to_date = fields.Date.today()
        self.env.cr.execute("""SELECT sum(case when hp.credit_note = False then (pl.total) else (-pl.total) end)
                    FROM hr_payslip as hp, hr_payslip_line as pl
                    WHERE hp.employee_id = %s AND hp.state = 'done'
                    AND hp.date_from >= %s AND hp.date_to <= %s AND hp.id = pl.slip_id AND pl.code = %s""",
                    (self.employee_id, from_date, to_date, code))
        res = self.env.cr.fetchone()
        return res and res[0] or 0.0        