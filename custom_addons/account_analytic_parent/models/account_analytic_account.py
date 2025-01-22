from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"
    _parent_name = "parent_id"
    _parent_store = True
    _order = "complete_name"

    parent_path = fields.Char(index=True, unaccent=False)
    parent_id = fields.Many2one(
        string="Parent Analytic Account",
        comodel_name="account.analytic.account",
        index=True,
        ondelete="cascade",
    )
    child_ids = fields.One2many(
        string="Child Accounts",
        comodel_name="account.analytic.account",
        inverse_name="parent_id",
        copy=True,
    )
    complete_name = fields.Char(
        compute="_compute_complete_name", recursive=True, store=True
    )
    total_debit = fields.Monetary(
        string="Total Debit", compute="_compute_total_debit_credit", store=True
    )
    total_credit = fields.Monetary(
        string="Total Credit", compute="_compute_total_debit_credit", store=True
    )

    @api.depends("debit", "credit", "child_ids.total_debit", "child_ids.total_credit")
    def _compute_total_debit_credit(self):
        for account in self:
            account.total_debit = account.debit + sum(account.child_ids.mapped("total_debit"))
            account.total_credit = account.credit + sum(account.child_ids.mapped("total_credit"))

    @api.depends("child_ids.line_ids.amount")
    def _compute_debit_credit_balance(self):
        """
        Warning, this method overwrites the standard because the hierarchy
        of analytic account changes
        """
        res = super()._compute_debit_credit_balance()

        ResCurrency = self.env["res.currency"]
        AccountAnalyticLine = self.env["account.analytic.line"]
        user_currency_id = self.env.user.company_id.currency_id

        # Re-compute only accounts with children
        for account in self.filtered("child_ids"):
            domain = [("account_id", "child_of", account.id)]

            credit_groups = AccountAnalyticLine.read_group(
                domain=domain + [("amount", ">=", 0.0)],
                fields=["currency_id", "amount"],
                groupby=["currency_id"],
                lazy=False,
            )
            credit = sum(
                map(
                    lambda x: ResCurrency.browse(x["currency_id"][0])._convert(
                        x["amount"],
                        user_currency_id,
                        self.env.user.company_id,
                        fields.Date.today(),
                    ),
                    credit_groups,
                )
            )

            debit_groups = AccountAnalyticLine.read_group(
                domain=domain + [("amount", "<", 0.0)],
                fields=["currency_id", "amount"],
                groupby=["currency_id"],
                lazy=False,
            )
            debit = sum(
                map(
                    lambda x: ResCurrency.browse(x["currency_id"][0])._convert(
                        x["amount"],
                        user_currency_id,
                        self.env.user.company_id,
                        fields.Date.today(),
                    ),
                    debit_groups,
                )
            )

            account.debit = abs(debit)
            account.credit = credit
            account.balance = account.credit - account.debit
        return res

    # ... [rest of the methods remain unchanged]

    def get_total_debit_credit(self):
        self.ensure_one()
        return {
            'total_debit': self.total_debit,
            'total_credit': self.total_credit
        }


    @api.constrains("parent_id")
    def check_recursion(self):
        for account in self:
            if not super(AccountAnalyticAccount, account)._check_recursion():
                raise UserError(_("You can not create recursive analytic accounts."))
        return True

    @api.onchange("parent_id")
    def _onchange_parent_id(self):
        for account in self:
            account.partner_id = account.parent_id.partner_id

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for account in self:
            if account.parent_id:
                account.complete_name = _("%(parent)s / %(own)s") % {
                    "parent": account.parent_id.complete_name,
                    "own": account.name,
                }
            else:
                account.complete_name = account.name

    @api.constrains("active")
    def check_parent_active(self):
        for account in self.filtered(
            lambda a: a.active
            and a.parent_id
            and a.parent_id not in self
            and not a.parent_id.active
        ):
            raise UserError(
                _("Please activate first parent account %s")
                % account.parent_id.complete_name
            )

    @api.depends("complete_name", "code", "partner_id.commercial_partner_id.name")
    def _compute_display_name(self):
        for analytic in self:
            name = analytic.complete_name
            if analytic.code:
                name = f"[{analytic.code}] {name}"
            if analytic.partner_id:
                name = _("%(name)s - %(partner)s") % {
                    "name": name,
                    "partner": analytic.partner_id.commercial_partner_id.name,
                }
            analytic.display_name = name

    def write(self, vals):
        if self and "active" in vals and not vals["active"]:
            self.mapped("child_ids").write({"active": False})
        return super().write(vals)
