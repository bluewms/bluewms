# Adapted from stock_no_negative and stock_location_lockdown.
# Copyright 2015-2019 Akretion, Alexis de Lattre
# Copyright 2018 ForgeFlow, Jordi Ballester
# Copyright 2026 宁波宝蓝物流科技有限公司
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo import api, models
from odoo.exceptions import ValidationError


# This identity never comes from an RPC/JSON context.
_SAME_LOCATION_MOVE_TOKEN = object()


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def _blue_check_location_change(self, location, quantity, reserved_quantity=0):
        # A reservation release must remain possible when cancelling a frozen job.
        if not quantity and reserved_quantity <= 0:
            return
        frozen = location._blue_stock_blocking_location()
        if frozen:
            raise ValidationError(self.env._('库位 %(location)s 已冻结, 本次库存变更已阻止.', location=frozen.display_name))
        blocked = location._blue_stock_blocking_location(receiving=True) if quantity > 0 else self.env['stock.location']
        if blocked:
            trusted = self.env.context.get('blue_stock_same_location_token') is _SAME_LOCATION_MOVE_TOKEN
            line = self.env['stock.move.line'].browse(self.env.context.get('blue_stock_move_line_id')).exists() if trusted else self.env['stock.move.line']
            if not (line and line.location_id == location and line.location_dest_id == location):
                raise ValidationError(self.env._('库位 %(location)s 禁止入库, 本次库存增加已阻止.', location=blocked.display_name))

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            location = self.env['stock.location'].browse(values.get('location_id'))
            if location:
                self._blue_check_location_change(location, values.get('quantity', 0), values.get('reserved_quantity', 0))
        return super().create(values_list)

    def write(self, values):
        physical_fields = {'quantity', 'location_id', 'product_id', 'lot_id', 'package_id', 'owner_id'}
        if physical_fields & values.keys() or 'reserved_quantity' in values:
            for quant in self:
                new_location = self.env['stock.location'].browse(values.get('location_id')) if 'location_id' in values else quant.location_id
                new_quantity = values.get('quantity', quant.quantity)
                dimensions_changed = any(name in values and (values[name] or False) != (quant[name].id or False) for name in physical_fields - {'quantity'})
                if dimensions_changed and new_location != quant.location_id:
                    self._blue_check_location_change(quant.location_id, -quant.quantity)
                    self._blue_check_location_change(new_location, new_quantity)
                elif dimensions_changed:
                    # Repacking in the same location is not an incoming movement.
                    # A full freeze still protects its existing stock/reservations.
                    self._blue_check_location_change(quant.location_id, -abs(quant.quantity), quant.reserved_quantity)
                    self._blue_check_location_change(new_location, new_quantity - quant.quantity,
                        values.get('reserved_quantity', quant.reserved_quantity) - quant.reserved_quantity)
                else:
                    self._blue_check_location_change(new_location, new_quantity - quant.quantity,
                        values.get('reserved_quantity', quant.reserved_quantity) - quant.reserved_quantity)
        return super().write(values)

    @api.ondelete(at_uninstall=False)
    def _unlink_if_frozen_stock(self):
        for quant in self:
            if (quant.quantity or quant.reserved_quantity) and quant.location_id._blue_stock_blocking_location():
                raise ValidationError(self.env._('冻结库位中的库存不能删除.'))

    @api.constrains('quantity', 'product_id', 'location_id', 'lot_id', 'package_id', 'owner_id')
    def _check_blue_negative_stock(self):
        # Do not trust a caller-provided context flag to disable stock protection.
        for quant in self:
            product = quant.product_id
            if (product.is_storable and quant.location_id.usage in ('internal', 'transit')
                    and quant.uom_id.compare(quant.quantity, 0) < 0
                    and not product.allow_negative_stock
                    and not product.categ_id.allow_negative_stock
                    and not quant.location_id.allow_negative_stock):
                raise ValidationError(self.env._(
                    '产品 %(product)s 在库位 %(location)s 的库存将变为 %(quantity)s, 批次 %(lot)s. 此产品和位置未配置负库存例外, 本次操作已阻止.',
                    product=product.display_name, quantity=quant.quantity,
                    location=quant.location_id.display_name, lot=quant.lot_id.display_name or '-'))
