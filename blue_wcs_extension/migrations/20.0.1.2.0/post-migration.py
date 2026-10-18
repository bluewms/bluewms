from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Additive migration: old templates, releases, fixed plans and payloads stay exact.
    for profile in env['blue.config.profile'].with_context(active_test=False).search([('hook_code', '=', 'wcs_creation')]):
        profile._record_event('migration', details='新增wcs_creation/3. 旧草稿、正式版本与固定计划保留. /3模板作为独立历史版本保留. 最新增强能力使用/4, 旧绑定兼容说明以/4升级记录为准. 人工开关和设备授权未自动更改.')
