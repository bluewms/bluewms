{
    'name': 'BlueWMS 库存盘点',
    'summary': '独立盘点单、实盘明细、差异与原生库存调整追溯',
    'version': '20.0.1.0.0',
    'author': '宁波宝蓝物流科技有限公司, ForgeFlow',
    'license': 'LGPL-3',
    'depends': ['stock', 'mail'],
    'data': ['security/ir.access.csv', 'data/stock_inventory_data.xml', 'views/stock_inventory_views.xml', 'views/res_config_settings_views.xml'],
    'installable': True,
    'application': False,
}
