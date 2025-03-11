# -*- coding: utf-8 -*-
{
    'name': "Mingalar Aung Myae Budget",

    'summary': """
        Budget """,

    'description': """
        Account Budget
    """,

    'author': "SME Intellect Co. Ltd",
    'website': "https://www.smeintellect.com/",
    'category': 'HR Expense',
    'version': '0.1',

    'depends': ['account_budget','project_account_budget'],

    'data': [
        'security/account_budget_security.xml',
        'views/account_budget_views.xml',
        'security/ir.model.access.csv',

    ],
    'license': 'LGPL-3',

}
