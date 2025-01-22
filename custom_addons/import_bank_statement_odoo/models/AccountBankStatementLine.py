from odoo import models, _, exceptions

class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'

    def action_open_related_account_move(self):
        """Opens the related account move for this bank statement."""
        # Loop through statement lines and get the related move_id (journal entry)
        for line in self.line_ids:
            if line.move_id:
                return {
                    'name': _('Journal Entry'),
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'res_model': 'account.move',
                    'res_id': line.move_id.id,
                    'target': 'current',
                }
        # If no move_id found, raise an error
        raise exceptions.UserError(_("No related journal entry found for this bank statement."))
