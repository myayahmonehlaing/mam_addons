# -*- coding: utf-8 -*-
{
    'name': "Mingalar Aung Myay Sale",

    'summary': "Sale Order Custom for MAM",

    'description': """
Customization for Sale Order Mingalar Aung Myay
    """,

    'author': "SMEi",
    'website': "https://www.smeintellect.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Sale',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'product', 'sale_stock','sale_margin','mam_stock'],

    # always loaded
    'data': [
        'security/security.xml',
        'views/sale_order_views.xml',
        'views/product_views.xml',

    ],
    "license": "AGPL-3",
    "application": True,
    "installable": True,
    "auto_install": False,
}

