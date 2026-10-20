from odoo.exceptions import AccessError

ERP_TOKEN = object()


def internal(records):
    if records.env.context.get('blue_erp_token') is not ERP_TOKEN:
        raise AccessError(records.env._('请通过 ERP 接口业务流程操作记录.'))


def manager(records):
    if not records.env.user.has_group('stock.group_stock_manager'):
        raise AccessError(records.env._('仅库存管理员可以管理 ERP 接口.'))
    records.check_access('write')
