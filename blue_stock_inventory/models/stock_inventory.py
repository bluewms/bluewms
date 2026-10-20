"""Odoo 20 inventory documents adapted from stock_inventory_ajustement."""
from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .guard import INVENTORY_TOKEN, manager, trusted


class StockInventory(models.Model):
    _name = 'stock.inventory'
    _description = '库存盘点单'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char('盘点单号', required=True, default='New', copy=False, readonly=True)
    date = fields.Datetime('盘点日期', default=fields.Datetime.now, required=True)
    completed_at = fields.Datetime('完成时间', readonly=True, copy=False)
    company_id = fields.Many2one('res.company', '公司', default=lambda self: self.env.company, required=True, index=True)
    state = fields.Selection([('draft', '草稿'), ('in_progress', '进行中'), ('done', '已完成'), ('cancel', '已取消')],
                             string='状态', default='draft', required=True, tracking=True, copy=False)
    responsible_id = fields.Many2one('res.users', '盘点负责人', default=lambda self: self.env.user, ondelete='restrict')
    location_ids = fields.Many2many('stock.location', string='盘点库位', check_company=True)
    exclude_sublocation = fields.Boolean('仅选定库位', help='启用时不包含子库位.')
    product_selection = fields.Selection([('all', '全部商品'), ('manual', '指定商品'), ('one', '单一商品'),
        ('category', '商品分类'), ('lot', '批次或序列号')], string='商品范围', default='all', required=True)
    product_ids = fields.Many2many('product.product', string='指定商品', check_company=True)
    category_id = fields.Many2one('product.category', '商品分类')
    lot_ids = fields.Many2many('stock.lot', string='批次或序列号', check_company=True)
    owner_id = fields.Many2one('res.partner', '限定货主', check_company=True)
    package_id = fields.Many2one('stock.package', '限定包裹', check_company=True)
    start_empty = fields.Boolean('空白盘点', help='开始时不生成已有库存明细,由盘点人员手工添加.')
    prefill_counted_quantity = fields.Selection([('counted', '预填账面数量'), ('zero', '预填零')],
                                               string='实盘预填方式', default='counted', required=True)
    line_ids = fields.One2many('stock.inventory.line', 'inventory_id', '实盘明细', copy=False)
    stock_quant_ids = fields.Many2many('stock.quant', 'blue_inventory_quant_rel', 'inventory_id', 'quant_id',
                                       string='关联库存记录', copy=False, readonly=True)
    stock_move_ids = fields.One2many('stock.move.line', 'inventory_adjustment_id', '调整流水')
    line_count = fields.Integer('明细数', compute='_compute_counts')
    counted_count = fields.Integer('已确认实盘', compute='_compute_counts')
    applied_count = fields.Integer('已记账', compute='_compute_counts')
    note = fields.Text('备注')

    @api.depends('line_ids', 'line_ids.counted', 'line_ids.applied')
    def _compute_counts(self):
        for inventory in self:
            inventory.line_count = len(inventory.line_ids)
            inventory.counted_count = len(inventory.line_ids.filtered('counted'))
            inventory.applied_count = len(inventory.line_ids.filtered('applied'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not trusted(self) and (vals.get('state', 'draft') != 'draft' or any(k in vals for k in ('completed_at', 'stock_quant_ids'))):
                raise AccessError(self.env._('请通过盘点业务按钮改变状态及历史.'))
            if not trusted(self):
                vals.update(state='draft', completed_at=False, stock_quant_ids=[])
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('blue.stock.inventory') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        self.check_access('write')
        if not trusted(self):
            if {'state', 'completed_at', 'stock_quant_ids', 'stock_move_ids', 'name'}.intersection(vals):
                raise AccessError(self.env._('盘点状态、编号和流水只能通过业务流程更新.'))
            settings = {'date', 'company_id', 'responsible_id', 'location_ids', 'exclude_sublocation', 'product_selection',
                'product_ids', 'category_id', 'lot_ids', 'owner_id', 'package_id', 'start_empty', 'prefill_counted_quantity'}
            if settings.intersection(vals) and any(i.state != 'draft' for i in self):
                raise UserError(self.env._('开始盘点后不能改变范围,请在无调整流水时退回草稿.'))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_history(self):
        if any(i.state not in ('draft', 'cancel') or i.line_ids.filtered('applied') for i in self):
            raise UserError(self.env._('只有没有记账历史的草稿或取消盘点单可以删除.'))

    @api.constrains('name', 'company_id', 'location_ids', 'product_selection', 'product_ids', 'category_id', 'lot_ids', 'responsible_id')
    def _check_configuration(self):
        for inventory in self:
            if not inventory.name or len(inventory.name) > 128:
                raise ValidationError(self.env._('盘点单号须为 1 至 128 个字符.'))
            if any(l.usage != 'internal' or l.company_id != inventory.company_id or not l.active for l in inventory.location_ids):
                raise ValidationError(self.env._('盘点库位必须是当前公司的有效内部库位.'))
            if any(not p.is_storable or p.company_id not in (inventory.company_id, self.env['res.company']) for p in inventory.product_ids):
                raise ValidationError(self.env._('请选择本公司或共享的库存商品.'))
            if inventory.product_selection in ('one', 'lot') and len(inventory.product_ids) > 1:
                raise ValidationError(self.env._('单一商品或批次模式只能选择一个商品.'))
            if any(l.company_id != inventory.company_id or l.product_id not in inventory.product_ids for l in inventory.lot_ids):
                raise ValidationError(self.env._('批次必须属于所选公司和商品.'))
            if inventory.responsible_id and (not inventory.responsible_id.active or inventory.company_id not in inventory.responsible_id.company_ids
                    or not inventory.responsible_id.has_group('stock.group_stock_user')):
                raise ValidationError(self.env._('负责人须为具有本公司库存权限的有效用户.'))

    def _counter(self):
        self.check_access('write')
        for inventory in self:
            if (inventory.responsible_id and inventory.responsible_id != self.env.user
                    and not self.env.user.has_group('stock.group_stock_manager')):
                raise AccessError(self.env._('仅盘点负责人或库存管理员可以录入实盘.'))

    def _lock(self):
        self.ensure_one()
        self.flush_recordset()
        # Touch the gate row so concurrent HTTP retries obtain a fresh snapshot.
        self.env.cr.execute('UPDATE stock_inventory SET write_date=write_date WHERE id=%s RETURNING id', [self.id])
        self.env.cr.fetchone()
        self.invalidate_recordset()

    def _locations(self):
        self.ensure_one()
        operator = 'in' if self.exclude_sublocation else 'child_of'
        return self.env['stock.location'].search([('id', operator, self.location_ids.ids),
            ('company_id', '=', self.company_id.id), ('usage', '=', 'internal'), ('active', '=', True)])

    def _product_domain(self):
        self.ensure_one()
        domain = fields.Domain('is_storable', '=', True) & fields.Domain('company_id', 'in', [False, self.company_id.id])
        if self.product_selection in ('manual', 'one', 'lot'):
            domain &= fields.Domain('id', 'in', self.product_ids.ids)
        elif self.product_selection == 'category':
            domain &= fields.Domain('categ_id', 'child_of', self.category_id.id)
        return domain

    def _quant_domain(self):
        self.ensure_one()
        domain = fields.Domain('company_id', '=', self.company_id.id) & fields.Domain('location_id', 'in', self._locations().ids)
        products = self.env['product.product'].with_context(active_test=False).search(self._product_domain())
        domain &= fields.Domain('product_id', 'in', products.ids)
        if self.product_selection == 'lot':
            domain &= fields.Domain('lot_id', 'in', self.lot_ids.ids)
        if self.owner_id:
            domain &= fields.Domain('owner_id', '=', self.owner_id.id)
        if self.package_id:
            domain &= fields.Domain('package_id', '=', self.package_id.id)
        return domain

    def _check_overlap(self):
        self.ensure_one()
        # Only this company's scope admission is serialized, including empty bins.
        self.env.cr.execute('UPDATE res_company SET write_date=write_date WHERE id=%s RETURNING id', [self.company_id.id])
        self.env.cr.fetchone()
        locations = self._locations()
        others = self.search([('id', '!=', self.id), ('company_id', '=', self.company_id.id), ('state', '=', 'in_progress')])
        for other in others:
            if not (locations & other._locations()):
                continue
            if self.owner_id and other.owner_id and self.owner_id != other.owner_id:
                continue
            if self.package_id and other.package_id and self.package_id != other.package_id:
                continue
            if self.product_selection == other.product_selection == 'lot' and not (self.lot_ids & other.lot_ids):
                continue
            if self.env['product.product'].with_context(active_test=False).search_count(self._product_domain() & other._product_domain(), limit=1):
                raise ValidationError(self.env._('盘点范围与进行中的 %(name)s 重叠,请先完成或调整范围.', name=other.name))

    def action_start(self):
        self.ensure_one()
        manager(self)
        with self.env.cr.savepoint():
            self._lock()
            if self.state != 'draft':
                raise UserError(self.env._('只有草稿可以开始盘点.'))
            if (not self.location_ids or not self._locations()
                    or self.product_selection in ('manual', 'one', 'lot') and not self.product_ids
                    or self.product_selection == 'category' and not self.category_id
                    or self.product_selection == 'lot' and not self.lot_ids):
                raise ValidationError(self.env._('请填写完整的库位及商品、分类或批次范围.'))
            self._check_overlap()
            self.line_ids._check_dimensions()
            quants = self.env['stock.quant'].search(self._quant_domain())
            if quants.filtered(lambda q: q.inventory_quantity_set or q.current_inventory_id):
                raise UserError(self.env._('范围内存在原生实盘录入或其他盘点,请先处理.'))
            if not self.line_ids and not self.start_empty:
                groups = quants._read_group(self._quant_domain(),
                    ['product_id', 'location_id', 'lot_id', 'package_id', 'owner_id'], ['quantity:sum'])
                values = []
                for product, location, lot, package, owner, quantity in groups:
                    if product.uom_id.compare(quantity, 0) == 0:
                        continue
                    values.append({'inventory_id': self.id, 'product_id': product.id, 'location_id': location.id,
                        'prod_lot_id': lot.id, 'package_id': package.id, 'partner_id': owner.id,
                        'product_qty': max(quantity, 0) if self.prefill_counted_quantity == 'counted' else 0,
                        'theoretical_qty': quantity, 'counted': False})
                if values:
                    self.env['stock.inventory.line'].with_context(blue_stock_inventory_token=INVENTORY_TOKEN).create(values)
            for line in self.line_ids:
                line.with_context(blue_stock_inventory_token=INVENTORY_TOKEN).write({'theoretical_qty': line._book_quantity(), 'counted': False})
            self.with_context(blue_stock_inventory_token=INVENTORY_TOKEN).write({'state': 'in_progress', 'date': fields.Datetime.now(),
                'stock_quant_ids': [Command.set(quants.ids)]})
            quants.with_context(blue_stock_inventory_token=INVENTORY_TOKEN, inventory_mode=False).write({'current_inventory_id': self.id, 'to_do': True})
        return True

    def action_mark_counted(self):
        self.ensure_one()
        self._counter()
        if self.state != 'in_progress':
            raise UserError(self.env._('请先开始盘点.'))
        self.line_ids.filtered(lambda l: not l.applied).write({'counted': True})
        return True

    def _apply_lines(self, lines):
        self.ensure_one()
        manager(self)
        with self.env.cr.savepoint():
            self._lock()
            if self.state != 'in_progress' or any(l.inventory_id != self or l.applied or not l.counted for l in lines):
                raise UserError(self.env._('只能应用本单尚未记账并已确认实盘的明细.'))
            prepared = []
            lines._check_dimensions()
            for line in lines.sorted('id'):
                if line.product_uom_id != line.product_id.uom_id:
                    raise UserError(self.env._('商品库存单位已变化,请重新建立盘点明细.'))
                quants = line._quants()
                quants.flush_recordset()
                if quants:
                    self.env.cr.execute('SELECT id FROM stock_quant WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(quants.ids)])
                    quants.invalidate_recordset()
                if len(quants) > 1:
                    raise UserError(self.env._('此库存维度存在重复库存记录,请先通过原生库存整理后刷新账存.'))
                current = sum(quants.mapped('quantity'))
                if line.product_uom_id.compare(current, line.theoretical_qty) != 0:
                    raise UserError(self.env._('商品 %(product)s 的账存已变化,请刷新账存并重新确认实盘.', product=line.product_id.display_name))
                if quants.filtered(lambda q: q.current_inventory_id and q.current_inventory_id != self or q.inventory_quantity_set):
                    raise UserError(self.env._('库存记录已有其他实盘录入,请先核对.'))
                if not quants and line.product_uom_id.compare(line.product_qty, 0) != 0:
                    quants = self.env['stock.quant'].with_context(blue_stock_inventory_token=INVENTORY_TOKEN, inventory_mode=False).create({
                        'product_id': line.product_id.id, 'location_id': line.location_id.id, 'lot_id': line.prod_lot_id.id,
                        'package_id': line.package_id.id, 'owner_id': line.partner_id.id, 'quantity': 0,
                        'current_inventory_id': self.id, 'to_do': True})
                prepared.append((line, quants))
            changed = self.env['stock.quant']
            mapping = {}
            for line, quants in prepared:
                if quants and line.product_uom_id.compare(line.product_qty, line.theoretical_qty) != 0:
                    quants.with_context(blue_stock_inventory_token=INVENTORY_TOKEN, inventory_mode=False).write({'inventory_quantity': line.product_qty})
                    changed |= quants
                    mapping[str(quants.id)] = line.id
            if changed:
                changed.with_context(blue_stock_inventory_token=INVENTORY_TOKEN, blue_stock_inventory_id=self.id,
                    blue_stock_inventory_line_ids=lines.ids, blue_stock_inventory_line_by_quant=mapping,
                    inventory_name=self.name)._apply_inventory()
            for line, quants in prepared:
                line.with_context(blue_stock_inventory_token=INVENTORY_TOKEN).write({'applied': True, 'applied_at': fields.Datetime.now()})
                quants.with_context(blue_stock_inventory_token=INVENTORY_TOKEN, inventory_mode=False).write({'current_inventory_id': False, 'to_do': False})
            if self.line_ids and all(self.line_ids.mapped('applied')) and self.company_id.stock_inventory_auto_complete:
                self._finish()
        return True

    def _finish(self):
        claimed = self.env['stock.quant'].search([('current_inventory_id', '=', self.id)])
        claimed.with_context(blue_stock_inventory_token=INVENTORY_TOKEN, inventory_mode=False).write({'current_inventory_id': False, 'to_do': False})
        self.with_context(blue_stock_inventory_token=INVENTORY_TOKEN).write({'state': 'done', 'completed_at': fields.Datetime.now()})

    def action_state_to_done(self):
        self.ensure_one()
        manager(self)
        with self.env.cr.savepoint():
            self._lock()
            if self.state != 'in_progress' or not self.line_ids or self.line_ids.filtered(lambda l: not l.counted):
                raise UserError(self.env._('请先开始盘点,添加明细并确认全部实盘数量.'))
            remaining = self.line_ids.filtered(lambda l: not l.applied)
            if remaining:
                self._apply_lines(remaining)
            self._finish()
        return True

    def _release(self, state):
        manager(self)
        self._lock()
        if self.state not in ('draft', 'in_progress') or self.line_ids.filtered('applied'):
            raise UserError(self.env._('已有记账历史或已结束的盘点不能取消、退回草稿.'))
        claimed = self.env['stock.quant'].search([('current_inventory_id', '=', self.id)])
        claimed.with_context(blue_stock_inventory_token=INVENTORY_TOKEN, inventory_mode=False).write({'current_inventory_id': False, 'to_do': False})
        self.with_context(blue_stock_inventory_token=INVENTORY_TOKEN).write({'state': state})
        return True

    def action_state_to_draft(self):
        self.ensure_one()
        return self._release('draft')

    def action_state_to_cancel(self):
        self.ensure_one()
        return self._release('cancel')

    def action_view_stock_moves(self):
        self.ensure_one()
        self.check_access('read')
        return {'type': 'ir.actions.act_window', 'name': self.env._('盘点调整流水'), 'res_model': 'stock.move.line',
                'view_mode': 'list,form', 'domain': [('inventory_adjustment_id', '=', self.id)]}
