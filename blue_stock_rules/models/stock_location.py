# Adapted from stock_no_negative and stock_location_lockdown.
# Copyright 2015-2019 Akretion, Alexis de Lattre
# Copyright 2018 ForgeFlow, Jordi Ballester
# Copyright 2026 宁波宝蓝物流科技有限公司
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo import api, fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    block_stock_entrance = fields.Boolean('禁止入库', help='阻止向此位置及下级位置增加库存；允许将现有库存移出。')
    allow_negative_stock = fields.Boolean('允许负库存', help='允许此位置的库存产品出现负库存。')
    is_locking = fields.Boolean(help='冻结此位置及下级位置的库存进出和新增预留；可以释放已有预留或取消作业。')

    blue_policy_blocked = fields.Boolean(
        '受库位规则限制', compute='_compute_blue_policy_blocked', store=True, recursive=True,
    )

    @api.depends('is_locking', 'block_stock_entrance', 'location_id.blue_policy_blocked')
    def _compute_blue_policy_blocked(self):
        for location in self:
            location.blue_policy_blocked = bool(location.is_locking or location.block_stock_entrance or location.location_id.blue_policy_blocked)

    def _blue_stock_blocking_location(self, receiving=False):
        self.ensure_one()
        location = self
        while location:
            if location.is_locking or (receiving and location.block_stock_entrance):
                return location
            location = location.location_id
        return self.env['stock.location']

    def _check_can_be_used(self, product, quantity=0, package=None, location_qty=0):
        if self._blue_stock_blocking_location(receiving=True):
            return False
        return super()._check_can_be_used(product, quantity=quantity, package=package, location_qty=location_qty)

    @api.depends('blue_policy_blocked', 'child_ids.child_count', 'child_ids.child_none_count', 'state', 'location_rank', 'is_locking', 'active', 'usage')
    def _compute_child_count(self):
        super()._compute_child_count()
        for location in self:
            if location.blue_policy_blocked:
                location.child_none_count = 0
