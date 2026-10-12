{
    'name': 'BlueWMS 可编辑上架策略',
    'summary': '保留原生规则、整托盘容量、跨产品批次号补充限制与版本回滚',
    'version': '20.0.1.2.0',
    'author': '宁波宝蓝物流科技有限公司',
    'website': 'https://www.bluewms.com',
    'license': 'AGPL-3',
    'depends': ['blue_config_asset', 'blue_stock_rules'],
    'data': ['security/ir.access.csv',
             'data/blue_scene_template_data.xml', 'data/blue_scene_template_capability_data.xml', 'views/blue_config_profile_views.xml',
             'views/stock_putaway_rule_views.xml', 'views/stock_picking_views.xml', 'wizard/blue_putaway_preview_views.xml'],
    'installable': True,
}
