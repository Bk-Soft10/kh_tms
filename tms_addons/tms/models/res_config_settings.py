# -*- coding: utf-8 -*-
from ast import literal_eval
from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    income_account_id = fields.Many2one("account.account", "Income Account")
    trade_income_account_id = fields.Many2one("account.account", "Trade Income Account")
    fair_income_account_id = fields.Many2one("account.account", "Fair Income Account")
    gov_income_account_id = fields.Many2one("account.account", "Governmental Income Account")
    ground_income_account_id = fields.Many2one("account.account", "Ground Income Account")
    
    pickup_account_id = fields.Many2one("account.account", "Pickup Cost Account")
    
    
    advance_income_account_id = fields.Many2one("account.account", "Advance Income Account")
    expense_account_id = fields.Many2one("account.account", "Expense Account")
    discount_account_id = fields.Many2one("account.account", "Discount Account")
    
    receipt_journal_id = fields.Many2one('account.journal', 'Receipt Journal', domain=[('type', '=', 'sale')])
    trans_journal_id = fields.Many2one('account.journal', 'Internal Trans Journal', domain=[('type', '=', 'sale')])
    invoice_journal_id = fields.Many2one('account.journal', 'Invoice Journal', domain=[('type', '=', 'sale')])
    cash_journal_id = fields.Many2one('account.journal', 'Cash Journal', domain=[('type', '=', 'cash')])
    company_journal_id = fields.Many2one('account.journal', 'Company Journal', domain=[('type', '=', 'cash')])
    discount_company_journal_id = fields.Many2one('account.journal', 'Discount Company Journal', domain=[('type', '=', 'cash')])
    scratch_company_journal_id = fields.Many2one('account.journal', 'Scratch Company Journal', domain=[('type', '=', 'cash')])
    
    driver_expense_journal_id = fields.Many2one('account.journal', 'Driver Expense Journal', domain=[('type', '=', 'general')])
    transport_journal_id = fields.Many2one('account.journal', 'Trip Journal', domain=[('type', '=', 'general')])
    
    tms_receipt_product_id = fields.Many2one("product.product", "Transport Product ")
    
    allowed_plate_number_chars = fields.Text(string="Allowed Plate Number Chars")
    new_receipt_msg = fields.Text(string="New Receipt Message")
    arrival_msg = fields.Text(string="Arrival Message")
    thanks_msg = fields.Text(string="Thanks Message")
    

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()
        
        aa = self.env['account.account']
        aj = self.env['account.journal'].sudo()
        
        income_account_id = literal_eval(ICPSudo.get_param('tms.income_account_id', default='False'))
        if income_account_id and not aa.browse(income_account_id).exists():
            income_account_id = False
        
        trade_income_account_id = literal_eval(ICPSudo.get_param('tms.trade_income_account_id', default='False'))
        if trade_income_account_id and not aa.browse(trade_income_account_id).exists():
            trade_income_account_id = False
            
        fair_income_account_id = literal_eval(ICPSudo.get_param('tms.fair_income_account_id', default='False'))
        if fair_income_account_id and not aa.browse(fair_income_account_id).exists():
            fair_income_account_id = False
            
        gov_income_account_id = literal_eval(ICPSudo.get_param('tms.gov_income_account_id', default='False'))
        if gov_income_account_id and not aa.browse(gov_income_account_id).exists():
            gov_income_account_id = False
            
        ground_income_account_id = literal_eval(ICPSudo.get_param('tms.ground_income_account_id', default='False'))
        if ground_income_account_id and not aa.browse(ground_income_account_id).exists():
            ground_income_account_id = False
        
        pickup_account_id = literal_eval(ICPSudo.get_param('tms.pickup_account_id', default='False'))
        if pickup_account_id and not aa.browse(pickup_account_id).exists():
            pickup_account_id = False
        
        advance_income_account_id = literal_eval(ICPSudo.get_param('tms.advance_income_account_id', default='False'))
        if advance_income_account_id and not aa.browse(advance_income_account_id).exists():
            advance_income_account_id = False
        
        expense_account_id = literal_eval(ICPSudo.get_param('tms.expense_account_id', default='False'))
        if expense_account_id and not aa.browse(expense_account_id).exists():
            expense_account_id = False
        
        discount_account_id = literal_eval(ICPSudo.get_param('tms.discount_account_id', default='False'))
        if discount_account_id and not aa.browse(discount_account_id).exists():
            discount_account_id = False
            
        
        receipt_journal_id = literal_eval(ICPSudo.get_param('tms.receipt_journal_id', default='False'))
        if receipt_journal_id and not aj.browse(receipt_journal_id).exists():
            receipt_journal_id = False
            
        trans_journal_id = literal_eval(ICPSudo.get_param('tms.trans_journal_id', default='False'))
        if trans_journal_id and not aj.browse(trans_journal_id).exists():
            trans_journal_id = False
            
        invoice_journal_id = literal_eval(ICPSudo.get_param('tms.invoice_journal_id', default='False'))
        if invoice_journal_id and not aj.browse(invoice_journal_id).exists():
            invoice_journal_id = False
            
        cash_journal_id = literal_eval(ICPSudo.get_param('tms.cash_journal_id', default='False'))
        if cash_journal_id and not aj.browse(cash_journal_id).exists():
            cash_journal_id = False
        
        company_journal_id = literal_eval(ICPSudo.get_param('tms.company_journal_id', default='False'))
        if company_journal_id and not aj.browse(company_journal_id).exists():
            company_journal_id = False
            
        discount_company_journal_id = literal_eval(ICPSudo.get_param('tms.discount_company_journal_id', default='False'))
        if discount_company_journal_id and not aj.browse(discount_company_journal_id).exists():
            discount_company_journal_id = False
            
        scratch_company_journal_id = literal_eval(ICPSudo.get_param('tms.scratch_company_journal_id', default='False'))
        if scratch_company_journal_id and not aj.browse(scratch_company_journal_id).exists():
            scratch_company_journal_id = False
            
        transport_journal_id = literal_eval(ICPSudo.get_param('tms.transport_journal_id', default='False'))
        if transport_journal_id and not aj.browse(transport_journal_id).exists():
            transport_journal_id = False
        
        driver_expense_journal_id = literal_eval(ICPSudo.get_param('tms.driver_expense_journal_id', default='False'))
        if driver_expense_journal_id and not aj.browse(driver_expense_journal_id).exists():
            driver_expense_journal_id = False
        
        
        allowed_plate_number_chars = ICPSudo.get_param('tms.allowed_plate_number_chars')
        new_receipt_msg = ICPSudo.get_param('tms.new_receipt_msg')
        arrival_msg = ICPSudo.get_param('tms.arrival_msg')
        thanks_msg = ICPSudo.get_param('tms.thanks_msg')
        res.update(
            income_account_id=income_account_id,
            trade_income_account_id=trade_income_account_id,
            fair_income_account_id=fair_income_account_id,
            gov_income_account_id=gov_income_account_id,
            ground_income_account_id=ground_income_account_id,
            pickup_account_id=pickup_account_id,
            advance_income_account_id=advance_income_account_id,
            expense_account_id=expense_account_id,
            discount_account_id=discount_account_id,
            receipt_journal_id=receipt_journal_id,
            trans_journal_id=trans_journal_id,
            invoice_journal_id=invoice_journal_id,
            cash_journal_id=cash_journal_id,
            company_journal_id=company_journal_id,
            discount_company_journal_id=discount_company_journal_id,
            scratch_company_journal_id=scratch_company_journal_id,
            transport_journal_id=transport_journal_id,
            driver_expense_journal_id=driver_expense_journal_id,
            allowed_plate_number_chars=allowed_plate_number_chars,
            new_receipt_msg=new_receipt_msg,
            arrival_msg=arrival_msg,
            thanks_msg=thanks_msg)
        return res

    
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        ICPSudo = self.env['ir.config_parameter'].sudo()
        
        ICPSudo.set_param('tms.income_account_id', self.income_account_id.id)
        ICPSudo.set_param('tms.trade_income_account_id', self.trade_income_account_id.id)
        ICPSudo.set_param('tms.fair_income_account_id', self.fair_income_account_id.id)
        ICPSudo.set_param('tms.gov_income_account_id', self.gov_income_account_id.id)
        ICPSudo.set_param('tms.ground_income_account_id', self.ground_income_account_id.id)
        ICPSudo.set_param('tms.pickup_account_id', self.pickup_account_id.id)
        
        ICPSudo.set_param('tms.advance_income_account_id', self.advance_income_account_id.id)
        ICPSudo.set_param('tms.expense_account_id', self.expense_account_id.id)
        ICPSudo.set_param('tms.discount_account_id', self.discount_account_id.id)
        
        ICPSudo.set_param('tms.receipt_journal_id', self.receipt_journal_id.id)
        ICPSudo.set_param('tms.trans_journal_id', self.trans_journal_id.id)
        ICPSudo.set_param('tms.invoice_journal_id', self.invoice_journal_id.id)
        ICPSudo.set_param('tms.cash_journal_id', self.cash_journal_id.id)
        ICPSudo.set_param('tms.company_journal_id', self.company_journal_id.id)
        ICPSudo.set_param('tms.discount_company_journal_id', self.discount_company_journal_id.id)
        ICPSudo.set_param('tms.scratch_company_journal_id', self.scratch_company_journal_id.id)
        ICPSudo.set_param('tms.transport_journal_id', self.transport_journal_id.id)
        ICPSudo.set_param('tms.driver_expense_journal_id', self.driver_expense_journal_id.id)
        
        ICPSudo.set_param('tms.allowed_plate_number_chars', self.allowed_plate_number_chars)
        ICPSudo.set_param('tms.new_receipt_msg', self.new_receipt_msg)
        ICPSudo.set_param('tms.arrival_msg', self.arrival_msg)
        ICPSudo.set_param('tms.thanks_msg', self.thanks_msg)
        
