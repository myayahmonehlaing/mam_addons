# -*- coding: utf-8 -*-
{
    'name': "Mingalar Aung Myae Account",

    'summary': """
        Account """,

    'description': """
        Account Advance / Expense / Approval
    """,

    'author': "SME Intellect Co. Ltd",
    'website': "https://www.smeintellect.com/",
    'category': 'Account Management',
    'version': '0.1',

    'depends': ['base','account','hr_expense','mrp_account','account_asset'],

    'data': [
        'wizard/account_move_refuse_reason_view.xml',
        'views/account_move_view.xml',
        'views/hr_expense_sheet_view.xml',
        'views/res_company_views.xml',
        'views/account_asset_views.xml',
        'views/res_config_setting_view.xml',
        'data/mail_activity_data.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/account_menu_items.xml',
    ],
    'license': 'LGPL-3',
}
