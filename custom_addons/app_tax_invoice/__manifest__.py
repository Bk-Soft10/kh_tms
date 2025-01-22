{
    'name': "Electronic Invoice - Accounting",
    'author': 'BK-Software',
    'company': 'TBS',
    'category': 'accounting',
    'version': '1.0',
    'license': 'OPL-1',
    'summary': 'Electronic Invoice Tax - Accounting',
    'description': 'Electronic Invoice Tax - Accounting',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'reports/invoice_qr_report.xml',
    ],
}
