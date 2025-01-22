import ast
from odoo import models, fields, api, exceptions, _
from odoo.exceptions import MissingError, UserError, ValidationError, AccessError

from odoo.osv.expression import get_unaccent_wrapper

import logging

_logger = logging.getLogger(__name__)

class PartnerPriceList(models.Model):
    _name = 'tms.partner.price.list'
    _order = 'city_from_id'
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, domain=[('is_company','=',True), ('is_customer','=',True)])
    city_from_id = fields.Many2one('tms.city', string='From City', required=True)
    city_to_id = fields.Many2one('tms.city', string='To City', required=True)
    freight_state_id = fields.Many2one('tms.freight.state', string='Freight State', required=True)
    price = fields.Monetary(string="Price", currency_field='currency_id', required=True) 
    deal = fields.Integer(string='Deal', default=-1)
    deal_used = fields.Integer(string='Deal Used', readonly=True)
    with_tax = fields.Boolean(string="With Tax", default=False)
    currency_id = fields.Many2one('res.currency', related='partner_id.currency_id', string="Company Currency", store=False, readonly=True)
    
    
    
    _sql_constraints = [
        ('part_fr_price_list_uq', 'unique(partner_id, city_to_id, city_from_id, freight_state_id)', 'City price for the fright state already exists')]

    @api.onchange('city_from_id')
    def _city_from_chenged(self):
        return {'domain': {'city_to_id': [('id','!=',self.city_from_id.id)]}} if self.city_from_id else {} 

    
    @api.constrains('city_from_id', 'city_to_id')
    def _check_city(self):
        for r in self:
            if r.city_from_id == r.city_to_id:
                raise ValidationError(_('Don\'t put same city on one line'))

    
    def _set_history_price(self, id, city_from_id, city_to_id, freight_state_id, value):
        ''' Store the standard price change in order to be able to retrieve the cost of a product for a given date'''
        PriceHistory = self.env['tms.partner.price.history']
        for product in self:
            PriceHistory.create({
                'partner_price_id': id,
                'city_from_id': city_from_id.id,
                'city_to_id': city_to_id.id,
                'freight_state_id': freight_state_id.id,
                'value': value,
            })

    
    def get_history_price(self, city_from_id, city_to_id, date=None):
        history = self.env['tms.partner.price.history'].search([
            ('city_from_id', '=', city_from_id),
            ('city_to_id', 'in', self.ids),
            ('datetime', '<=', date or fields.Datetime.now())], order='datetime desc,id desc', limit=1)
        return history.cost or 0.0
    
    
class Partner(models.Model):
    _inherit = 'res.partner'
    
    def _get_default_country(self):
        return self.env.user.company_id.country_id
    
    # @api.model
    # def _commercial_fields(self):
    #     return super(Partner, self)._commercial_fields() +  ['property_income_account_id']
    
    
    name = fields.Char(index=True, required=True)
    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict')
    ssn = fields.Char("Partner Id", copy=False)
    
    tms_price_list_ids = fields.One2many('tms.partner.price.list', 'partner_id', string='Freight Price List', copy=True)
        
    use_contract = fields.Boolean(default=False, string="Use Contract")
    
    tax_license = fields.Char(string='Tax License ID')
    
    pay_branch_id = fields.Many2one('tms.branch', string='Payment Branch')
    
    allow_debit = fields.Boolean(string='Allow Debit')
    
    is_trans = fields.Boolean(string='Individual Client Transfer')
    
    receipt_count = fields.Integer(compute='_compute_receipt_count')
    
    itrans_count = fields.Integer(compute='_compute_itrans_count')
    
    #property_income_account_id = fields.Many2one("account.account", "Income Account", company_dependent=True)
    
    shipper_type = fields.Selection([ ("1", 'Individual'),
                                       ("2", 'Trade'),
                                       ("3", 'Fair'),
                                       ("4", 'Governmental')])
    
    is_blocked = fields.Boolean()
    
    @api.model
    @api.returns('self', lambda value:value.id)
    def create(self, vals):
        name = vals['name'].replace(' ', '') if 'name' in vals else False
        name = name.replace("(", "").replace(")", "") if name else False
        if self._context.get('is_trans'):
            vals['is_trans'] = True
            vals['shipper_type'] = '1'
            if not name or len(name) ==0 or not name.replace(' ', '').isalpha():
                raise ValidationError(_("Please enter valid name!"))
            if self.search([('name', '=', name), ('is_company', '=', True)]):
                raise ValidationError(_("The you entered already exist!"))
        
        
        vals['name'] = vals['name'].replace('  ', ' ').strip()
        ssn = vals['ssn'] if 'ssn' in vals else False
        
        if ssn and (not ssn.isdigit() or  len(ssn) > 10):
            raise ValidationError(_("Please enter valid ID!"))
        
        p = super(Partner, self).create(vals)
        
        if p.is_company and p.shipper_type not in (False, "2", "3", "4"):
            raise UserError(_("Please set correct shipper type according partner type (Commercial, Fair or Governmental)!"))
    
        if not p.is_company and p.shipper_type not in (False, "1"):
            raise UserError(_("Please set correct shipper type to individual!"))
        
        #user = self.env['res.users'].search([('')])   
        return p    
    
    
    def write(self, vals):
        if vals.get('name'):
            name = vals['name'].replace(' ', '')
        
        if 'name' in vals and self._context.get('is_trans'):
            if not self.env.user.has_group("tms.group_tms_admin"):
                raise UserError(_("You have no right to edit client name!!"))                
            
            
            name = name.replace("(", "").replace(")", "") 
            if len(name) == 0 or not name.isalpha():
                raise ValidationError(_("Please enter valid name!"))
                        
        ssn = vals['ssn'] if 'ssn' in vals else False
        if ssn and (not ssn.isdigit() or len(ssn) > 10):
            raise ValidationError(_("Please enter valid ID!"))
        
        #mobile = vals['mobile'] if 'mobile' in vals else False
        #if mobile and (not mobile.isdigit() or len(mobile) > 10):
        #    raise ValidationError("Please enter valid mobile!")
        
        ret = super(Partner, self).write(vals)
        
        if 'is_company' in vals or 'shipper_type' in vals:
            for p in self:
                
                if p.is_company and p.shipper_type not in (False, "2", "3", "4"):
                    raise UserError(_("Please set correct shipper type according partner type (Commercial, Fair or Governmental)!"))
            
                if not p.is_company and p.shipper_type not in (False, "1"):
                    raise UserError(_("Please set correct shipper type to individual!"))
        
        return ret    
    
    
    @api.constrains('ssn')
    def _check_ssn(self):
        for partner in self:
            if partner.ssn:
                count = self.search([('id', '!=', partner.id if partner.id else 0), ('ssn', '=', partner.ssn)], limit=1)
                if len(count) > 0:
                    raise ValidationError(_('SSN already exist'))


    @api.model
    def default_get(self, fields):
        fields = super(Partner, self).default_get(fields)
        
        if self._context.get('is_trans') and fields.get('name') :
            fields['ssn'] = fields['name']
            fields['name'] = False
        return fields

    
    # def name_get(self):
    #     res = []
    #     for partner in self:
    #         name = partner.name or ''

    #         if partner.company_name or partner.parent_id:
    #             if not name and partner.type in ['invoice', 'delivery', 'other']:
    #                 name = dict(self.fields_get(['type'])['type']['selection'])[partner.type]
    #             if not partner.is_company:
    #                 name = "%s, %s" % (partner.commercial_company_name or partner.parent_id.name, name)
    #         if self._context.get('show_address_only'):
    #             name = partner._display_address(without_company=True)
    #         if self._context.get('show_address'):
    #             name = name + "\n" + partner._display_address(without_company=True)
    #         name = name.replace('\n\n', '\n')
    #         name = name.replace('\n\n', '\n')
    #         if self._context.get('ssn') and partner.ssn:
    #             #name = "%s * %s " % (partner.ssn, name)
    #             pass
    #         if self._context.get('mobile') and partner.mobile:
    #             name = "%s (%s) " % (name, partner.mobile)
    #         if self._context.get('show_email') and partner.email:
    #             name = "%s <%s>" % (name, partner.email)
    #         if self._context.get('html_format'):
    #             name = name.replace('\n', '<br/>')
    #         res.append((partner.id, name))
    #     return res
        
    # @api.model
    # def name_search(self, name, args=None, operator='ilike', limit=100):
    #     if args is None:
    #         args = []
    #     if name and operator in ('=', 'ilike', '=ilike', 'like', '=like'):
    #         self.check_access_rights('read')
    #         where_query = self._where_calc(args)
    #         self._apply_ir_rules(where_query, 'read')
    #         from_clause, where_clause, where_clause_params = where_query.get_sql()
    #         where_str = where_clause and (" WHERE %s AND " % where_clause) or ' WHERE '

    #         # search on the name of the contacts and of its company
    #         search_name = name
    #         if operator in ('ilike', 'like'):
    #             search_name = '%%%s%%' % name
    #         if operator in ('=ilike', '=like'):
    #             operator = operator[1:]

    #         unaccent = get_unaccent_wrapper(self.env.cr)

    #         query = """SELECT id
    #                      FROM res_partner
    #                   {where} ({ssn} {operator} {percent}
    #                        OR {mobile} {operator} {percent}
    #                        OR {email} {operator} {percent}
    #                        OR {display_name} {operator} {percent}
    #                        OR {reference} {operator} {percent}
    #                        OR {vat} {operator} {percent})
    #                        -- don't panic, trust postgres bitmap
    #                  ORDER BY {display_name} {operator} {percent} desc,
    #                           {display_name}
    #                 """.format(where=where_str,
    #                            operator=operator,
    #                            ssn=unaccent('ssn'),
    #                            mobile=unaccent('mobile'),
    #                            email=unaccent('email'),
    #                            display_name=unaccent('display_name'),
    #                            reference=unaccent('ref'),
    #                            percent=unaccent('%s'),
    #                            vat=unaccent('vat'),)

    #         where_clause_params += [search_name]*7
    #         if limit:
    #             query += ' limit %s'
    #             where_clause_params.append(limit)
    #         self.env.cr.execute(query, where_clause_params)
    #         partner_ids = [row[0] for row in self.env.cr.fetchall()]

    #         if partner_ids:
    #             return self.browse(partner_ids).name_get()
    #         else:
    #             return []
    #     return super(Partner, self)._name_search(name, args, operator=operator, limit=limit) 
    
    
    
    def _compute_receipt_count(self):
        self.receipt_count = self.env['tms.receipt'].search_count([('partner_id', '=', self.id)]) if self.is_company or self.is_trans else 0
        
    
    def _compute_itrans_count(self):
        self.itrans_count = self.env['tms.itrans'].search_count([('partner_id', '=', self.id)]) if self.is_company or self.is_trans else 0
        
    
    
    def action_view_partner_receipts(self):
        [action] = self.env.ref('tms.action_tms_receipt_comp' if self.is_company else 'tms.action_tms_receipt_indev').read()
        action['domain'] = [('partner_id', '=', self.id)]
        action['views'] = [[False, 'list'], [False, 'form']] #important to view as list view
        ctx = ast.literal_eval(action.get('context')) if action.get('context') else {}
        ctx['edit'] = 1
        ctx['current'] = True
        ctx['search_default_r_30_days'] = 0
        ctx['default_partner_id'] = self.id
        action['context'] = ctx
        return action
    
    
    def action_view_partner_itrans(self):
        [action] = self.env.ref('tms.action_tms_itrans').read()
        action['domain'] = [('partner_id', '=', self.id)]
        action['views'] = [[False, 'list'], [False, 'form']] #important to view as list view
        ctx = ast.literal_eval(action.get('context')) if action.get('context') else {}
        ctx['edit'] = 1
        ctx['current'] = True
        ctx['search_default_r_30_days'] = 0
        ctx['default_partner_id'] = self.id
        ctx['default_is_comp'] = self.is_company
        action['context'] = ctx
        return action
        
            