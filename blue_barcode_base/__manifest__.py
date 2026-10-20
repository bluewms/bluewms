{
    'name': 'BlueWMS 条码作业',
    'version': '20.0.1.0.0',
    'author': '宁波宝蓝物流科技有限公司',
    'license': 'AGPL-3',
    'depends': ['stock', 'web', 'barcodes', 'barcodes_gs1_nomenclature', 'blue_stock_rules'],
    'data': ['security/ir.access.csv', 'views/barcode_views.xml'],
    'assets': {'web.assets_backend': ['blue_barcode_base/static/src/**/*']},
    'application': True,
    'installable': True,
}
