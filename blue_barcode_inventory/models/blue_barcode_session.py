from odoo import fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.blue_barcode_base.models.guard import digest, quantity


class BlueBarcodeSession(models.Model):
    _inherit = 'blue.barcode.session'

    kind = fields.Selection(selection_add=[('inventory', '盘库')], ondelete={'inventory': 'cascade'})
    inventory_id = fields.Many2one('stock.inventory', check_company=True, ondelete='restrict')

    def _check_target(self):
        if self.kind != 'inventory':
            return super()._check_target()
        self.inventory_id._counter()
        if self.inventory_id.company_id != self.company_id or self.inventory_id.state != 'in_progress':
            raise UserError(self.env._('盘库单已结束或公司不符.'))
        return self.env['stock.picking']

    def _rows(self):
        if self.kind != 'inventory':
            return super()._rows()
        return [{'key': 'inventory:%s' % line.id, 'line_id': line.id, 'product_id': line.product_id.id,
            'product': line.product_id.display_name, 'barcode': line.product_id.barcode or '',
            'tracking': line.product_id.tracking, 'lot_id': line.prod_lot_id.id, 'lot': line.prod_lot_id.name or '',
            'owner_id': line.partner_id.id, 'location_id': line.location_id.id, 'source': line.location_id.display_name,
            'destination_id': False, 'destination': '', 'package_id': line.package_id.id, 'package': line.package_id.name or '',
            'destination_package_id': False, 'destination_package': '', 'picking_id': False, 'picking': self.inventory_id.name,
            'uom': line.product_uom_id.display_name, 'uom_id': line.product_uom_id.id, 'expected': line.theoretical_qty,
            'quantity': line.product_qty if line.counted else 0, 'prefilled': line.product_qty,
            'counted': line.counted, 'applied': line.applied, 'snapshot': str(line.snapshot_at),
            'group': 'inventory:%s:%s' % (self.inventory_id.id, line.location_id.id),
            'stamp': str(line.write_date)} for line in self.inventory_id.line_ids]

    def _fingerprint(self):
        if self.kind != 'inventory':
            return super()._fingerprint()
        return digest({'rows': self._rows(), 'state': self.inventory_id.state,
                       'stamp': str(self.inventory_id.write_date), 'configuration': self._configuration()})

    def _actions(self):
        return [] if self.kind == 'inventory' else super()._actions()

    def _record_id(self):
        return self.inventory_id.id if self.kind == 'inventory' else super()._record_id()

    def _read_target(self):
        if self.kind == 'inventory':
            self.inventory_id.check_access('read')
            return
        return super()._read_target()

    def _is_ended(self):
        return self.inventory_id.state in ('done', 'cancel') if self.kind == 'inventory' else super()._is_ended()

    def _apply_count(self, row, parsed, total=False):
        if self.kind != 'inventory':
            return super()._apply_count(row, parsed, total)
        inventory = self.inventory_id
        inventory._lock()
        inventory._counter()
        line = inventory.line_ids.filtered(lambda l: l.id == row['line_id'])
        if len(line) != 1 or line.applied or inventory.state != 'in_progress':
            raise UserError(self.env._('只能录入本单未记账的实盘明细.'))
        if line.product_uom_id != line.product_id.uom_id:
            raise UserError(self.env._('库存单位已变化,请重新核对盘库明细.'))
        if parsed.get('lot') and parsed['lot'] != line.prod_lot_id.name:
            raise ValidationError(self.env._('二维码批次与盘库明细不同.'))
        amount = self._quantity_in_product_uom(line.product_id, parsed, total)
        old = line.product_qty if line.counted else 0
        stored_old = line.product_qty
        new_quantity = amount if total else old + amount
        quantity(new_quantity, zero=True)
        if line.product_uom_id.compare(line.product_uom_id.round(new_quantity), new_quantity):
            raise ValidationError(self.env._('实盘数量不符合库存单位精度.'))
        line.write({'product_qty': new_quantity})
        return {'key': row['key'], 'group': row['group'], 'old': old, 'stored_old': stored_old, 'quantity': new_quantity}
