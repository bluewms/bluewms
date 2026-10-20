{
    'name': 'BlueWMS ERP 接口管理',
    'version': '20.0.1.0.2',
    'author': '宁波宝蓝物流科技有限公司',
    'license': 'AGPL-3',
    'depends': ['stock', 'blue_extension_contract', 'blue_stock_rules', 'blue_config_asset', 'blue_ai_client'],
    'data': ['security/ir.access.csv', 'data/erp_data.xml', 'views/erp_views.xml'],
    'external_dependencies': {'python': ['requests']},
    'application': True,
    'installable': True,
}
