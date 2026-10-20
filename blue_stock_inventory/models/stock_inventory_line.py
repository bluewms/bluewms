import math

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .guard import INVENTORY_TOKEN, trusted


class StockInventoryLine(models.Model):
    _name = 'stock.inventory.line'
    _description = '盘点实盘明细'
    _order = 'inventory_id, location_id, product_id, id'
    _check_company_auto = True

    inventory_id = fields.Many2one('stock.inventory', '盘点单', required=True, ondelete='cascade', check_company=True)
    company_id = fields.Many2one(related='inventory_id.company_id', store=True, index=True)
    state = fields.Selection(related='inventory_id.state')
    product_id = fields.Many2one('product.product', '商品', required=True, check_company=True, ondelete='restrict')
    product_uom_id = fields.Many2one('uom.uom', '单位', required=True, readonly=True)
    location_id = fields.Many2one('stock.location', '库位', required=True, check_company=True, ondelete='restrict')
    prod_lot_id = fields.Many2one('stock.lot', '批次或序列号', check_company=True, ondelete='restrict')
    package_id = fields.Many2one('stock.package', '包裹', check_company=True, ondelete='restrict')
    partner_id = fields.Many2one('res.partner', '货主', check_company=True, ondelete='restrict')
    theoretical_qty = fields.Float('账面数量快照', digits='Product Unit', readonly=True)
    product_qty = fields.Float('实盘数量', digits='Product Unit')
    difference_qty = fields.Float('盘点差异', compute='_compute_difference', store=True, digits='Product Unit')
    counted = fields.Boolean('已确认实盘', default=False)
    applied = fields.Boolean('已记账', default=False, readonly=True)
    applied_at = fields.Datetime('记账时间', readonly=True)
    snapshot_at = fields.Datetime('账存快照时间', default=fields.Datetime.now, readonly=True)
    _unique_dimensions = models.Constraint('UNIQUE NULLS NOT DISTINCT (inventory_id,product_id,location_id,prod_lot_id,package_id,partner_id)',
                                           '同一盘点单的商品、库位、批次、包裹及货主组合不能重复.')

    @api.depends('product_qty', 'theoretical_qty')
    def _compute_difference(self):
        for line in self:
            line.difference_qty = line.product_qty - line.theoretical_qty

    @api.model_create_multi
    def create(self, vals_list):
        inventories = self.env['stock.inventory'].browse(sorted({v.get('inventory_id') for v in vals_list if v.get('inventory_id')}))
        inventories._counter()
        for inventory in inventories:
            inventory._lock()
            if inventory.state not in ('draft', 'in_progress'):
                raise UserError(self.env._('已结束的盘点单不能添加明细.'))
        if not trusted(self) and any({'theoretical_qty', 'applied', 'applied_at', 'snapshot_at'}.intersection(v) for v in vals_list):
            raise AccessError(self.env._('账存快照及记账状态由系统生成.'))
        seen = set()
        dimensions = ('inventory_id', 'product_id', 'location_id', 'prod_lot_id', 'package_id', 'partner_id')
        for values in vals_list:
            if not trusted(self):
                values.update(applied=False, applied_at=False)
            product = self.env['product.product'].browse(values.get('product_id'))
            if values.get('product_uom_id') and values['product_uom_id'] != product.uom_id.id:
                raise ValidationError(self.env._('盘点使用商品的库存单位.'))
            values['product_uom_id'] = product.uom_id.id
            key = tuple(values.get(field) or False for field in dimensions)
            if key in seen or self.search_count(list(zip(dimensions, ['='] * len(dimensions), key))):
                raise ValidationError(self.env._('同一盘点单的库存维度不能重复,请修改已有明细.'))
            seen.add(key)
        records = super().create(vals_list)
        for line, values in zip(records, vals_list):
            if not trusted(self):
                line.with_context(blue_stock_inventory_token=INVENTORY_TOKEN).write({
                    'theoretical_qty': line._book_quantity(), 'counted': 'product_qty' in values,
                    'snapshot_at': fields.Datetime.now()})
        return records

    @api.onchange('product_id')
    def _onchange_product_unit(self):
        self.product_uom_id = self.product_id.uom_id

    def write(self, vals):
        self.check_access('write')
        if not trusted(self):
            if set(vals) - {'product_qty', 'counted'}:
                raise AccessError(self.env._('库存维度及快照不能直接更改,请重新添加未记账明细.'))
            self.inventory_id._counter()
            for inventory in self.inventory_id:
                inventory._lock()
            if any(l.applied or l.state not in ('draft', 'in_progress') for l in self):
                raise UserError(self.env._('已记账或已结束的明细不可修改.'))
            if 'product_qty' in vals:
                vals = {**vals, 'counted': True}
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_applied(self):
        if any(l.applied or l.state not in ('draft', 'in_progress', 'cancel') for l in self):
            raise UserError(self.env._('已记账或已完成盘点明细必须保留.'))
        self.inventory_id._counter()

    @api.constrains('inventory_id', 'product_id', 'location_id', 'prod_lot_id', 'package_id', 'partner_id', 'product_qty')
    def _check_dimensions(self):
        for line in self:
            inventory = line.inventory_id
            if not math.isfinite(line.product_qty) or not 0 <= line.product_qty <= 1e12:
                raise ValidationError(self.env._('实盘数量必须是有限的非负数.'))
            if (line.location_id not in inventory._locations()
                    or not self.env['product.product'].with_context(active_test=False).search_count(inventory._product_domain() & fields.Domain('id', '=', line.product_id.id))):
                raise ValidationError(self.env._('明细的库位或商品超出盘点范围.'))
            if inventory.owner_id and line.partner_id != inventory.owner_id:
                raise ValidationError(self.env._('明细货主与盘点范围不符.'))
            if inventory.package_id and line.package_id != inventory.package_id:
                raise ValidationError(self.env._('明细包裹与盘点范围不符.'))
            if inventory.product_selection == 'lot' and line.prod_lot_id not in inventory.lot_ids:
                raise ValidationError(self.env._('明细批次不在指定范围内.'))
            if line.prod_lot_id and (line.prod_lot_id.product_id != line.product_id or line.prod_lot_id.company_id != line.company_id):
                raise ValidationError(self.env._('批次必须与商品和公司一致.'))
            if line.product_id.tracking not in (False, 'none') and not line.prod_lot_id:
                raise ValidationError(self.env._('批次或序列号跟踪商品必须填写已有批次.'))
            if line.product_id.tracking == 'serial' and line.product_qty not in (0, 1):
                raise ValidationError(self.env._('序列号商品的实盘数量只能为 0 或 1.'))
            if line.package_id and line.package_id.location_id and line.package_id.location_id != line.location_id:
                raise ValidationError(self.env._('包裹所在库位与盘点明细不符.'))

    def _quants(self):
        self.ensure_one()
        return self.env['stock.quant'].search([('company_id', '=', self.company_id.id), ('location_id', '=', self.location_id.id),
            ('product_id', '=', self.product_id.id), ('lot_id', '=', self.prod_lot_id.id),
            ('package_id', '=', self.package_id.id), ('owner_id', '=', self.partner_id.id)])

    def _book_quantity(self):
        self.ensure_one()
        return sum(self._quants().mapped('quantity'))

    def action_refresh_book(self):
        self.check_access('write')
        self.inventory_id._counter()
        for inventory in self.inventory_id:
            inventory._lock()
        for line in self:
            if line.applied or line.state != 'in_progress':
                raise UserError(self.env._('只能刷新进行中且未记账的明细.'))
            line.with_context(blue_stock_inventory_token=INVENTORY_TOKEN).write({
                'theoretical_qty': line._book_quantity(), 'snapshot_at': fields.Datetime.now(), 'counted': False})
        return True

    def action_apply(self):
        self.check_access('write')
        for inventory in self.inventory_id:
            inventory._apply_lines(self.filtered(lambda l: l.inventory_id == inventory))
        return True
