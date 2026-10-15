from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Existing line/route records are retained for audit. Carry defaults into the original WCS tab.
    for route in env['wcs.route'].with_context(active_test=False).search([]):
        operation = route.picking_type_id
        values = {}
        if not operation.equipment_id:
            values.update(equipment_id=route.equipment_id.id, equipment_category_id=route.equipment_id.category_id.id,
                          task_type=route.equipment_id.task_type, wcs_request_mode=route.mode,
                          is_create_wcs_by_container=True)
        if route.mode == 'relay':
            values['wcs_secondary_equipment_id'] = route.second_equipment_id.id
            # Do not guess a real stock location from a free-text legacy station code.
        if values:
            operation.write(values)
        if not route.source_id.agv_map_point:
            route.source_id.agv_map_point = route.source_point
        if not route.destination_id.agv_map_point:
            route.destination_id.agv_map_point = route.destination_point
    for profile in env['blue.config.profile'].search([('hook_code', '=', 'wcs_creation')]):
        active = profile.active_release_id.version_id
        if active and active.contract == 'wcs_creation/1' and profile.draft_code == active.code_text and profile.draft_tests == active.test_cases:
            # A released copy already preserves the exact old code. Prepare, never publish, the replacement draft.
            profile.action_load_example()
            profile._record_event('migration', details='已保留旧版发布及线路资料. 创建配置已准备新版草稿, 请重新试算验证并发布.')
