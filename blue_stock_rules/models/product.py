# Adapted from stock_no_negative and stock_location_lockdown.
# Copyright 2015-2019 Akretion, Alexis de Lattre
# Copyright 2018 ForgeFlow, Jordi Ballester
# Copyright 2026 宁波宝蓝物流科技有限公司
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo import api, fields, models
from odoo.exceptions import AccessError


def _check_policy_permission(env, values):
    if 'allow_negative_stock' in values and not env.user.has_group('stock.group_stock_manager'):
        raise AccessError(env._('仅库存管理员可以修改负库存例外配置.'))


class ProductCategory(models.Model):
    _inherit = 'product.category'

    allow_negative_stock = fields.Boolean('允许负库存', help='允许此类别直接关联的库存产品出现负库存，不自动继承到子类别。')

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if values.get('allow_negative_stock'):
                _check_policy_permission(self.env, values)
        return super().create(values_list)

    def write(self, values):
        _check_policy_permission(self.env, values)
        return super().write(values)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    allow_negative_stock = fields.Boolean('允许负库存', help='默认禁止库存产品在内部／中转位置出现负库存。只有明确允许的产品、类别或位置可以例外。')

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if values.get('allow_negative_stock'):
                _check_policy_permission(self.env, values)
        return super().create(values_list)

    def write(self, values):
        _check_policy_permission(self.env, values)
        return super().write(values)
