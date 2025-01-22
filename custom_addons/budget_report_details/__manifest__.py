{
    'name': ' Budget Report Details Customization',
    'version': '1.0',
    'category': 'Budget Report Details Management',
    'summary': 'Create Budget Report Line Details in Budget Account ',
    'depends': ['base_account_budget','analytic'],
    'data': [
        'security/ir.model.access.csv',
        'views/budget_view.xml',

    ],
    'installable': True,
    'application': False,
}