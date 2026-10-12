from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError


class StockLocation(models.Model):
    _inherit = 'stock.location'

    child_count = fields.Integer('下级库位数', compute='_compute_child_count', store=True, recursive=True)
    child_none_count = fields.Integer('可用库位数', compute='_compute_child_count', store=True, recursive=True)
    state = fields.Selection(
        [('none', '空位'), ('full', '有货')], string='状态', compute='_compute_state', store=True, recursive=True,
    )
    is_locking = fields.Boolean('是否锁定', default=False)
    location_rank = fields.Selection(
        [('location', '库位'), ('list', '列'), ('passageway', '通道'), ('area', '库区')],
        string='位置等级', default='location',
    )
    storey = fields.Char('楼层/库区')
    passageway = fields.Char('通道')
    list = fields.Char('列')
    layer = fields.Char('层')
    position = fields.Char('库位')
    location_destination_value = fields.Char('地图ID')
    color = fields.Integer('颜色', compute='_compute_package_name', store=True)
    package_name = fields.Char('包裹', compute='_compute_package_name', store=True)
    single_product_id = fields.Many2one('product.product', string='单一产品', compute='_compute_package_name', store=True)
    single_uom_id = fields.Many2one('uom.uom', string='单位', compute='_compute_package_name', store=True)
    single_product_qty = fields.Float('数量', compute='_compute_package_name', store=True)
    is_mixed_product = fields.Boolean('混放产品', compute='_compute_package_name', store=True)
    coordinate_ids = fields.One2many('stock.location.coordinate', 'location_id', string='库位容量')

    @api.depends(
        'quant_ids', 'quant_ids.quantity', 'quant_ids.product_id',
        'quant_ids.uom_id', 'quant_ids.package_id', 'quant_ids.package_id.name', 'location_rank',
    )
    def _compute_package_name(self):
        for location in self:
            quants = location.quant_ids.filtered(
                lambda quant: quant.uom_id.compare(quant.quantity, 0) != 0
            ) if location.location_rank == 'location' else self.env['stock.quant']
            products = quants.product_id
            location.package_name = ', '.join(quants.package_id.mapped('name')) or False
            location.is_mixed_product = len(products) > 1
            location.single_product_id = products if len(products) == 1 else False
            location.single_uom_id = products.uom_id if len(products) == 1 else False
            location.single_product_qty = sum(quants.mapped('quantity')) if len(products) == 1 else 0
            location.color = int(any(quant.uom_id.compare(quant.quantity, 0) > 0 for quant in quants))

    @api.depends('quant_ids', 'quant_ids.quantity', 'quant_ids.uom_id', 'child_ids.state', 'location_rank')
    def _compute_state(self):
        for location in self:
            if location.location_rank == 'location':
                occupied = any(quant.uom_id.compare(quant.quantity, 0) > 0 for quant in location.quant_ids)
            else:
                occupied = any(child.state == 'full' for child in location.child_ids)
            location.state = 'full' if occupied else 'none'

    @api.depends(
        'child_ids.child_count', 'child_ids.child_none_count', 'state',
        'location_rank', 'is_locking', 'active', 'usage',
    )
    def _compute_child_count(self):
        for location in self:
            if location.location_rank == 'location':
                location.child_count = int(location.active)
                location.child_none_count = int(
                    location.active and location.usage == 'internal'
                    and location.state == 'none' and not location.is_locking
                )
            else:
                location.child_count = sum(location.child_ids.mapped('child_count'))
                location.child_none_count = 0 if location.is_locking or not location.active else sum(
                    location.child_ids.mapped('child_none_count')
                )

    def action_sync_coordinates(self):
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise AccessError(self.env._('Only inventory managers can synchronize capacity positions.'))
        for location in self:
            capacities = location.storage_category_id.capacity_ids.filtered('package_type_id')
            if len(capacities) > 1:
                raise UserError(self.env._('Select a storage category with one package capacity.'))
            quantity = capacities.quantity if capacities else 0
            if quantity < 0 or quantity > 2000 or quantity != int(quantity):
                raise UserError(self.env._('Capacity must be an integer between 0 and 2000.'))
            wanted = {str(number) for number in range(1, int(quantity) + 1)}
            obsolete = location.coordinate_ids.filtered(lambda coordinate: coordinate.name not in wanted)
            obsolete.unlink()
            existing = set(location.coordinate_ids.mapped('name'))
            self.env['stock.location.coordinate'].create([
                {'name': str(number), 'sequence': number, 'location_id': location.id,
                 'location_name': f'{location.name}-{number}', 'location_code': f'{location.name}-{number}'}
                for number in range(1, int(quantity) + 1) if str(number) not in existing
            ])
        return True

    @api.private
    def compute_storage_category_qty(self):
        """Keep the old internal entry point for later WCS migration."""
        return self.action_sync_coordinates()
