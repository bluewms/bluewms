def migrate(cr, version):
    # Keep old stored flags before turning their names into compatibility aliases.
    cr.execute('ALTER TABLE stock_picking_type ADD COLUMN IF NOT EXISTS auto_create_wcs_request_execute boolean')
    cr.execute('ALTER TABLE stock_picking_type ADD COLUMN IF NOT EXISTS is_auto_validate boolean')
    cr.execute('UPDATE stock_picking_type SET auto_create_wcs_request_execute = COALESCE(blue_wcs_auto_create, false), is_auto_validate = COALESCE(blue_wcs_auto_validate, false)')
