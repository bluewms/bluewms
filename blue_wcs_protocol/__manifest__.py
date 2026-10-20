{
    'name': 'BlueWMS 可编辑设备协议',
    'version': '20.0.1.1.1',
    'author': '宁波宝蓝物流科技有限公司',
    'license': 'AGPL-3',
    'depends': ['blue_extension_contract', 'blue_wcs_base', 'blue_config_asset', 'blue_ai_client'],
    'data': ['data/protocol_definition.xml', 'views/wcs_equipment_category_views.xml', 'views/wcs_request_views.xml'],
    'external_dependencies': {'python': ['requests']},
    'installable': True,
}
