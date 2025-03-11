# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Mingalar Aung Myae Stock",

    'summary': """
           Inventory Backdate Operations Control""",

    'description': """
         The following operations are currently supported with backdate including accounting entries
          1.Stock Transfer
          2.Inventory Adjustment
          4.Stock Scrapping
        """,

    'author': "SME Intellect Co. Ltd",
    'website': "https://www.smeintellect.com/",
    'category': 'Inventory Management',
    'version': '0.1',
    'depends': ['stock','stock_account','stock_landed_costs'],
    'data': [
        'views/stock_views.xml',
        'report/report_stockpicking_operations.xml',
        'views/mam_region_view.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
