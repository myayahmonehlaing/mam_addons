# -*- coding: utf-8 -*-
{
    'name': "Mingalar Aung Myae Expense",

    'summary': """
        Expense Approval""",

    'description': """
        Expense Approval
    """,

    'author': "SME Intellect Co. Ltd",
    'website': "https://www.smeintellect.com/",
    'category': 'HR Expense',
    'version': '0.1',

    'depends': ['hr_expense'],

    'data': [

        'views/hr_expense_view.xml',
        'views/res_company_views.xml',
        'views/res_config_setting_view.xml',
        'data/mail_activity_data.xml',
        'security/ir.model.access.csv',

    ],
    'license': 'LGPL-3',

}
