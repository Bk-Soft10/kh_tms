# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

{
    'name': 'West Coast Invoice',
    'version': '17.0.0.0',
    'category': 'Account',
    'license': 'OPL-1',
    'summary': 'Allow to print pdf report of Journal Entries.',
    'description': """
    
    """,
    'author': 'Muhammad Faizal NS',
    'depends': ['base', 'account'],
    'data': [
        'report/report_journal_entries.xml',
        'report/report_journal_entries_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}

