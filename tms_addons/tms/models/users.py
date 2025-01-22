
from odoo import models, fields, api, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError

class Users(models.Model):

    _inherit = "res.users"
    
    @api.model
    def _get_branch(self):
        return self.env.user.branch_id
    
    all_branches = fields.Boolean(string="All Branches", default=False)
    
    multi_branch = fields.Boolean(string="Multi Branch", default=False)
    
    branch_id = fields.Many2one('tms.branch', string="Branch", default=_get_branch, context={'user_preference': True})
    
    branch_ids = fields.Many2many('tms.branch', 'tms_branch_users_rel', 'user_id', string="Branches", default=_get_branch)
    
    emp_code = fields.Char(string="Code")
    
    max_discount = fields.Float(default=20, string='Max Discount')
    
    @api.onchange('multi_branch')
    def _multi_branch_changed(self):
        if not self.multi_branch:
            return {'value': {'branch_id': False, 'branch_ids': False, 'all_branches': False}} 
        return {}
    
    @api.onchange('all_branches')
    def _all_branch_changed(self):
        if self.multi_branch:
            return {'value': {'branch_ids': False, 'multi_branch': False}} 
        return {}
    
    
    @api.constrains('branch_id', 'branch_ids')
    def _check_branch(self):
        if any(not user.all_branches and  user.branch_ids and user.branch_id and user.branch_id not in user.branch_ids for user in self):
            raise ValidationError(_('The chosen branch is not in the allowed branches for this user'))
    
    def change_current_branch(self, branch_id):
        
        return self.write({'branch_id': branch_id})
    
    @api.model
    def create(self, vals):
        user = super(Users, self).create(vals)
        user.partner_id.sudo().write({'active': user.active,'user_id': user.id, 'email': vals['email']})
        return user
    
    
    
    def write(self, values):
        if self == self.env.user and not self.all_branches and 'branch_id' in values and values['branch_id'] not in self.env.user.branch_ids.ids:
            del values['branch_id']    
            # safe fields only, so we write as super-user to bypass access rights
            self = self.sudo()
        if 'max_discount' in values and (values['max_discount'] > 100 or values['max_discount'] < 0):
            raise ValidationError(_('The discount should be between 0 and 100'))
        res = super(Users, self).write(values)
        """
        for user in self:
            if user.partner_id.customer:
                user.partner_id.sudo().write({'customer': False})
        """
        return res
    
    
