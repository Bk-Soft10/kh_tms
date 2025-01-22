# -*- coding: utf-8 -*-
{
    'name': "Employee General Settlement",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,
    'category': 'Human Resources',
    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'om_hr_payroll'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/hr_payroll_demo.xml',
        'data/ir_sequence.xml',
        'views/hr_settlement_type.xml',
        'views/hr_employee_settlement.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
