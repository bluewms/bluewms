import json


SNAPSHOT_KEY = 'blue_web_theme.original_records'
RECORD_FIELDS = {
    'stock.menu_product_variant_config_stock': ('parent_id', 'sequence', 'name'),
    'stock.menu_action_production_lot_form': ('parent_id', 'sequence', 'name'),
    'stock.menu_package': ('parent_id', 'sequence', 'name'),
    'stock.menu_action_location_form': ('parent_id', 'sequence', 'name'),
    'stock.menu_stock_inventory_control': ('active',),
    'stock.product_template_action_product': ('view_mode',),
}


def _pre_init_menu_snapshot(env):
    snapshots = {}
    for external_id, names in RECORD_FIELDS.items():
        record = env.ref(external_id)
        snapshots[external_id] = {
            name: record[name].id or False if name == 'parent_id' else record[name]
            for name in names
        }
    env['ir.config_parameter'].set_str(SNAPSHOT_KEY, json.dumps(snapshots))


def _uninstall_restore_menus(env):
    snapshots = json.loads(env['ir.config_parameter'].get_str(SNAPSHOT_KEY, '{}'))
    for external_id, values in snapshots.items():
        if external_id not in RECORD_FIELDS:
            continue
        record = env.ref(external_id, raise_if_not_found=False)
        if record:
            record.write({name: value for name, value in values.items() if name in RECORD_FIELDS[external_id]})
    env['ir.config_parameter'].search([('key', '=', SNAPSHOT_KEY)]).unlink()
