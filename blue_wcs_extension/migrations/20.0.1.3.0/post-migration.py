from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for profile in env['blue.config.profile'].with_context(active_test=False).search([('hook_code', '=', 'wcs_creation')]):
        profile._record_event('migration', details='新增/4全部行决策、位置映射及同数据多任务. 旧草稿/正式版本/绑定和人工开关保留, 不自动发布. /1兼容原线路过滤并复核人工设备和模式; /2兼容旧编排并复核人工设备授权; /3保持原合同. 完整新能力请新建/4配置并试算发布.')
