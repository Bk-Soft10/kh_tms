# -*- coding: utf-8 -*-
{
    'name': "Payroll Customization",

    'summary': """
        Updates on Payroll module""",

    'description': """
        Updates on Payroll module
    """,

    'author': "Mutwkil Faisal",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Human Resources/Payroll',
    'version': '1.1',

    # any module necessary for this one to work correctly
    'depends': ['om_hr_payroll'],  #hr_payroll

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/templates.xml',
    ],
    
}
