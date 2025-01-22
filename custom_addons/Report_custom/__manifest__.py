{
    'name': 'Report Customization',
    'version': '17.0.1.0.1',
    'category': 'Account Report Management',
    'summary': 'Add Report account to account module',
    'depends': ['account' , 'sale' ,'purchase'],
    'data': [
         'Reports/Radioactive_template.xml',
         'Reports/west_cost_template.xml',
         'Reports/custom_Tex_invoice_byatcrop.xml',
         'Reports/quotation_template.xml',
         'Reports/purchase_order_template.xml',
         'Reports/quotation_purchase_order.xml',
         'views/custom_report_action.xml',

    ],
    'installable': True,
    'application': False,
}