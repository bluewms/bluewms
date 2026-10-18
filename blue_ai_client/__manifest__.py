{
    'name': '宝蓝 AI 云端连接',
    'summary': '原生 Wiki 知识,用户与业务 Task 绑定,代码草稿工具',
    'version': '20.0.1.4.0',
    'author': '宁波宝蓝物流科技有限公司',
    'website': 'https://www.bluewms.com',
    'license': 'LGPL-3',
    'depends': ['muk_ai', 'blue_config_asset', 'mail'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/ir.access.csv',
        'data/blue_ai_data.xml',
        'views/blue_ai_connection_views.xml',
        'views/muk_ai_provider_views.xml',
        'views/res_config_settings_views.xml',
        'views/blue_config_profile_views.xml',
        'views/blue_ai_business_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'blue_ai_client/static/src/code_chat/code_chat.js',
            'blue_ai_client/static/src/code_chat/code_chat.xml',
            'blue_ai_client/static/src/code_chat/code_chat.scss',
        ],
    },
    'installable': True,
    'application': False,
}
