# Copyright 2024 ForgeFlow S.L. (http://www.forgeflow.com)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    stock_inventory_auto_complete = fields.Boolean('盘点全部记账后自动完成', default=False)
