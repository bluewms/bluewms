{
    'name': 'BlueWMS 盘点 ERP 关联',
    'summary': '将盘点差异同步事件关联到独立盘点单',
    'version': '20.0.1.0.0',
    'author': '宁波宝蓝物流科技有限公司',
    'license': 'LGPL-3',
    'depends': ['blue_stock_inventory', 'blue_erp_interface'],
    'data': ['views/stock_inventory_views.xml'],
    'installable': True,
    'auto_install': True,
}
