def migrate(cr, version):
    # Preserve legacy columns as historical data, but stop requiring obsolete scope.
    cr.execute('ALTER TABLE blue_config_profile ALTER COLUMN warehouse_id DROP NOT NULL')
    cr.execute('ALTER TABLE blue_config_profile ALTER COLUMN picking_type_id DROP NOT NULL')
    cr.execute('ALTER TABLE blue_config_profile ALTER COLUMN root_location_id DROP NOT NULL')
    cr.execute('ALTER TABLE blue_config_profile DROP CONSTRAINT IF EXISTS blue_config_profile_scope_unique')
    # Old transient previews cannot supply the newly required native rule.
    cr.execute('DELETE FROM blue_putaway_preview')
