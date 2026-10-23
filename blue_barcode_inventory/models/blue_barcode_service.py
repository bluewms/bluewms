from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class BlueBarcodeService(models.AbstractModel):
    _inherit = 'blue.barcode.service'

    @api.model
    def _target(self, kind, record_id):
        if kind != 'inventory':
            return super()._target(kind, record_id)
        self._authorize()
        if type(record_id) is not int or record_id <= 0:
            raise ValidationError('Invalid inventory identity.')
        inventory = self.env['stock.inventory'].browse(record_id).exists()
        inventory.ensure_one()
        inventory._counter()
        if inventory.company_id != self.env.company:
            raise AccessError(self.env._('请切换至盘库单所属公司.'))
        if inventory.state != 'in_progress':
            raise UserError(self.env._('请先开始盘库单. 已完成或取消的单据不能扫码.'))
        return inventory, self.env['stock.picking']

    @api.model
    def _open_values(self, kind, target, pickings):
        if kind == 'inventory':
            return {'kind': 'inventory', 'inventory_id': target.id}
        return super()._open_values(kind, target, pickings)

    @api.model
    def _occupancy_domain(self, kind, target, pickings):
        return [('inventory_id', '=', target.id)] if kind == 'inventory' else super()._occupancy_domain(kind, target, pickings)

    @api.model
    def _lock_target(self, kind, target, pickings):
        if kind == 'inventory':
            target._lock()
            return
        return super()._lock_target(kind, target, pickings)

    @api.model
    def list_records(self, kind, term='', offset=0, operation_type_id=False):
        if kind != 'inventory':
            return super().list_records(kind, term, offset, operation_type_id)
        self._authorize()
        if type(term) is not str or len(term) > 256 or type(offset) is not int or not 0 <= offset <= 100000:
            raise ValidationError('Invalid search arguments.')
        domain = fields.Domain('company_id', '=', self.env.company.id) & fields.Domain('state', '=', 'in_progress')
        if not self.env.user.has_group('stock.group_stock_manager'):
            domain &= fields.Domain('responsible_id', '=', self.env.uid)
        if term:
            domain &= fields.Domain('name', 'ilike', term)
        inventories = self.env['stock.inventory'].search(domain, offset=offset, limit=51)
        return {'items': [{'id': i.id, 'kind': 'inventory', 'name': i.name} for i in inventories[:50]],
                'more': len(inventories) > 50, 'message': self.env._('先建立并开始盘库单,再选择单据扫描.')}
