{
    'name': 'HR Customization',
    'version': '1.0',
    'category': 'Employee Management',
    'summary': 'Add custom fields to Employee Management',
    'depends': ['base','hr'],
    'data': [
        'views/employee_custom_fields_view.xml',
        'views/hr_employee_views.xml'
    ],
    'installable': True,
    'application': False,
}