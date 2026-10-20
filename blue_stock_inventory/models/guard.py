from odoo.exceptions import AccessError

INVENTORY_TOKEN = object()


def trusted(records):
    return records.env.context.get('blue_stock_inventory_token') is INVENTORY_TOKEN


def manager(records):
    records.check_access('write')
    if not records.env.user.has_group('stock.group_stock_manager'):
        raise AccessError(records.env._('仅库存管理员可以开始或应用盘点.'))
