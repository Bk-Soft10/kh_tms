{
    'name': 'RG Customization',
    'version': '1.0',
    'category': 'RG Management',
    'summary': 'Add custom fields to all modules in system',
    'depends': ['base','account','contacts'],
    'data': [
        'views/account_move_views.xml',
        'views/res_partner_view.xml',
        'views/res_company_view.xml',
    ],
    'installable': True,
    'application': False,
}