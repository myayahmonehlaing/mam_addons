# -*- coding: utf-8 -*-
{
    'name': "Mingalar Aung Myae Purchase",

    'summary': """
        Purchase """,

    'description': """
        Purchase 
    """,

    'author': "SME Intellect Co. Ltd",
    'website': "https://www.smeintellect.com/",
    'category': 'Purchase Management',
    'version': '0.1',

    'depends': ['purchase','purchase_stock','mam_stock'],

    'data': [
        'security/ir.model.access.csv',
        'wizard/purchase_refuse_reason_views.xml',
        'views/purchase_view.xml',
        'views/res_company_views.xml',
        'views/res_config_setting_view.xml',
        'data/mail_activity_data.xml',
    ],
    'license': 'LGPL-3',
}
