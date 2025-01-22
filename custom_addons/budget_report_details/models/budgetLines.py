import logging
from odoo import models, fields, api


_logger = logging.getLogger(__name__)

class CrossoveredBudgetLines(models.Model):
    _inherit = 'budget.lines'

    def action_view_related_invoices(self):
        self.ensure_one()
        budget = self.budget_id


        analytic_account_ids = budget.budget_line.mapped('analytic_account_id').ids

        # Get all analytic accounts used in this budget

        # Prepare the domain to search for invoices
        domain = [
            ('invoice_date', '>=', budget.date_from),
            ('invoice_date', '<=', budget.date_to),
            ('move_type', 'in', ['out_invoice', 'in_invoice', 'out_refund', 'in_refund']),
            ('line_ids.analytic_distribution', 'in', analytic_account_ids),



        ]



            # Search for invoices based on the domain
        #invoices = self.env['account.move'].search(domain)


        #print(domain)

            # Log invoice details
        #for invoice in invoices:
        #    print(invoice.id+"--"+ invoice.invoice_date+"---"+ invoice.amount_total+"---"+invoice.state)

        return {
            'name': f'Invoices Related to Budget {budget.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': domain,
            'context': {
                'group_by': 'invoice_date',
                'create': False,  # Disable creation of new records
                'edit': False,  # Disable editing of existing record
            },
            'target': 'current',  # Opens in the current window/tab
            'flags': {'action_buttons': True},  # Ensur
        }

    class CrossoveredBudget(models.Model):
        _inherit = 'budget.budget'

        def action_view_related_invoices(self):
            self.ensure_one()
            return self.budget_line[0].action_view_related_invoices()