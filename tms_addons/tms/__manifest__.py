# -*- coding: utf-8 -*-
{
    'name': "tms",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    # 'depends': ['base','portal','account'],
        'depends': ["base","hr","hr_contract","hr_fleet","analytic","account_asset","account",  "web_tour"],


    # always loaded
    'data': [
        'security/tms_security.xml',
        'data/rep.xml',
        # 'views/assets.xml',
        'wizard/trip_receipt_selection_view.xml',
        'views/trip_view.xml',
        'views/config_view.xml',
        'views/receipt_view.xml',
        # 'views/itrans_view.xml',
        # 'views/res_config_settings_views.xml',
        # 'views/hr_view.xml',
        'views/partner_view.xml',
        'views/users_view.xml',
        # 'views/payment_view.xml',
        'views/batch_receipt_post_view.xml',
        'views/batch_receipt_print_view.xml',
        # 'views/batch_payment_view.xml',
        # 'views/tax_view.xml',
        # 'views/scheduler_view.xml',
        'views/dashboard_view.xml',
        # 'views/jr_view.xml',
        # 'views/res_company_view.xml',
        'views/tms_menu.xml',
        # 'views/branch_target_views.xml',
        # 'reports/layout.xml',
        # 'reports/reports_view.xml',
        # 'reports/report_receipt.xml',
        # 'reports/report_receipt_exit.xml',
        # 'reports/report_receipt_voucher.xml',
        # 'reports/report_ground_voucher.xml',
        # 'reports/report_itrans_voucher.xml',
        # 'reports/report_itrans_route.xml',
        # 'reports/report_trip.xml',
        # 'reports/report_trip_route.xml',
        # 'reports/report_batch_post.xml',
        # 'reports/report_batch_print.xml',
        'security/ir.model.access.csv',
    ],
    'web.assets_backend': [
            '/tms/static/src/js/dashboard.js',
            '/tms/static/src/js/widgets.js',
        ],
    'web.assets_frontend': [
            '/tms/static/src/css/style.css',

    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'assets': {
         'web.assets_frontend': [
              'tms/static/src/css/style.css',
         ],
        'web.assets_backend': [
            '/tms/static/src/js/custom_dashboard.js',
            '/tms/static/src/xml/custom_dashboard.xml',
            # '/tms/static/src/js/test.js',
            # '/tms/static/src/js/test.xml',
        ],
    },


    
}
