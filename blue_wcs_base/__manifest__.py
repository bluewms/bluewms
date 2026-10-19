{
    'name': 'BlueWMS WCS 基础', 'version': '20.0.1.4.1',
    'author': '宁波宝蓝物流科技有限公司', 'license': 'AGPL-3',
    'depends': ['blue_stock_rules', 'mail'],
    'data': ['security/ir.access.csv', 'data/wcs_stage_data.xml', 'data/ir_cron_data.xml', 'views/wcs_views.xml'],
    'external_dependencies': {'python': ['requests']},
    'application': True, 'installable': True,
}
