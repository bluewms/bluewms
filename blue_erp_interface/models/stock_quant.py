import uuid

from odoo import models


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def _apply_inventory(self, date=None):
        self.flush_recordset()
        if self.ids:
            self.env.cr.execute('SELECT id FROM stock_quant WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(self.ids)])
            self.invalidate_recordset(['quantity', 'inventory_quantity'])
        snapshots = {}
        # Read only exact published count interfaces for these companies and locations.
        interfaces = self.env['blue.erp.interface'].search([
            ('kind', '=', 'inventory'), ('active', '=', True), ('profile_id.active_release_id', '!=', False),
            ('company_id', 'in', self.company_id.ids), ('inventory_location_ids', 'in', self.location_id.ids)])
        for quant in self:
            if quant.uom_id.compare(quant.inventory_quantity - quant.quantity, 0) == 0:
                continue
            for interface in interfaces.filtered(lambda i: i.company_id == quant.company_id and quant.location_id in i.inventory_location_ids):
                snapshots.setdefault(interface.id, []).append({
                    'product_code': quant.product_id.default_code or '', 'uom': quant.product_id.uom_id.with_context(lang=None).name,
                    'lot': quant.lot_id.name or '', 'location_code': quant.location_id.barcode or '',
                    'package': quant.package_id.name or '', 'owner_code': quant.owner_id.ref or '',
                    'book_quantity': quant.quantity, 'counted_quantity': quant.inventory_quantity,
                    'difference_quantity': quant.inventory_quantity - quant.quantity})
        result = super()._apply_inventory(date=date)
        for interface in interfaces:
            rows = snapshots.get(interface.id)
            if rows:
                self.env['blue.erp.event']._enqueue(interface, interface.profile_id.active_release_id,
                    'inventory', rows, 'inventory:%s' % uuid.uuid4())
        return result
