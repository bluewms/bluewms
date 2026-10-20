import json

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.blue_config_asset.models.blue_config_profile import digest

from ..tools.contract import CONTRACT, bounded, run_mapping
from .guard import ERP_TOKEN, manager


class BlueErpInterface(models.Model):
    _name = 'blue.erp.interface'
    _description = 'ERP 业务接口'
    _check_company_auto = True

    name = fields.Char('接口名称', required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    connection_id = fields.Many2one('blue.erp.connection', 'ERP 连接', required=True, check_company=True, ondelete='restrict')
    kind = fields.Selection([('incoming', '入库'), ('outgoing', '出库'), ('internal', '内部调拨'), ('inventory', '盘点差异')],
                            string='接口类别', required=True, default='incoming')
    picking_type_id = fields.Many2one('stock.picking.type', 'WMS 作业类型', check_company=True, ondelete='restrict')
    location_src_id = fields.Many2one('stock.location', '允许来源位置', check_company=True, ondelete='restrict')
    location_dest_id = fields.Many2one('stock.location', '允许目的位置', check_company=True, ondelete='restrict')
    inventory_location_ids = fields.Many2many('stock.location', string='盘点同步库位', check_company=True,
        help='仅同步所选内部库位,不自动包含子库位. 同公司同库位只配置一个启用接口.')
    inbound_lines_key = fields.Char('ERP 明细数组字段', default='lines', required=True,
        help='ERP JSON 对象中用于提供 candidates 的顶层数组字段. 其他单头字段由代码解析.')
    inbound_token = fields.Char('接收凭据', groups='base.group_system', copy=False)
    profile_id = fields.Many2one('blue.config.profile', '代码资产', readonly=True, copy=False, check_company=True, ondelete='restrict')
    operation_ids = fields.One2many('blue.erp.operation', 'interface_id', '允许的 ERP 操作')
    document_ids = fields.One2many('blue.erp.document', 'interface_id', '关联单据')
    event_ids = fields.One2many('blue.erp.event', 'interface_id', '同步记录')
    requirements = fields.Text(related='profile_id.requirements', readonly=False, related_sudo=False)
    code = fields.Text(related='profile_id.draft_code', readonly=False, related_sudo=False)
    tests = fields.Text(related='profile_id.draft_tests', readonly=False, related_sudo=False)
    policy_state = fields.Selection(related='profile_id.state', related_sudo=False)
    test_result = fields.Text(related='profile_id.simulation_result', related_sudo=False)
    version_ids = fields.One2many(related='profile_id.version_ids', related_sudo=False)
    release_ids = fields.One2many(related='profile_id.release_ids', related_sudo=False)
    audit_ids = fields.One2many(related='profile_id.event_ids', related_sudo=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any('profile_id' in vals for vals in vals_list):
            raise AccessError(self.env._('代码资产由接口自动创建.'))
        records = super().create(vals_list)
        for interface in records:
            profile = self.env['blue.config.profile'].with_context(blue_erp_token=ERP_TOKEN).create({
                'name': interface.name, 'company_id': interface.company_id.id,
                'template_id': self.env.ref('blue_erp_interface.template_erp').id, 'erp_interface_id': interface.id})
            interface.with_context(blue_erp_token=ERP_TOKEN).write({'profile_id': profile.id})
        return records

    def write(self, vals):
        self.check_access('write')
        if 'profile_id' in vals and self.env.context.get('blue_erp_token') is not ERP_TOKEN:
            raise AccessError(self.env._('接口代码资产不能直接更换.'))
        settings = {'company_id', 'connection_id', 'kind', 'picking_type_id', 'location_src_id', 'location_dest_id',
                    'inventory_location_ids', 'inbound_lines_key', 'active', 'inbound_token'}
        if settings.intersection(vals):
            self._lock_configuration()
            if {'company_id', 'kind'}.intersection(vals) and self.mapped('profile_id.release_ids'):
                raise UserError(self.env._('已有发布历史,请新建接口以更改公司或类别.'))
        return super().write(vals)

    def unlink(self):
        if self.mapped('profile_id.version_ids') or self.mapped('document_ids') or self.mapped('event_ids'):
            raise UserError(self.env._('已有历史的接口请归档保留.'))
        profiles = self.profile_id
        self.with_context(blue_erp_token=ERP_TOKEN).write({'profile_id': False})
        profiles.unlink()
        return super().unlink()

    @api.constrains('company_id', 'kind', 'picking_type_id', 'location_src_id', 'location_dest_id', 'inventory_location_ids', 'active', 'inbound_lines_key')
    def _check_settings(self):
        for interface in self:
            if not interface.inbound_lines_key or len(interface.inbound_lines_key) > 128:
                raise ValidationError(self.env._('请提供有效的明细数组字段.'))
            if interface.kind != 'inventory':
                if (not interface.picking_type_id or interface.picking_type_id.code != interface.kind
                        or not interface.location_src_id or not interface.location_dest_id):
                    raise ValidationError(self.env._('作业类型须与接口类别相符,并配置来源与目的位置.'))
                for location in interface.location_src_id | interface.location_dest_id:
                    if not location.active or location.company_id not in (interface.company_id, self.env['res.company']):
                        raise ValidationError(self.env._('接口位置必须有效且属于接口公司或共享位置.'))
                warehouse = interface.picking_type_id.warehouse_id
                for location in (interface.location_src_id | interface.location_dest_id).filtered(lambda l: l.usage == 'internal'):
                    if warehouse and not self.env['stock.location'].search_count([('id', '=', location.id), ('id', 'child_of', warehouse.view_location_id.id)]):
                        raise ValidationError(self.env._('内部位置须属于作业仓库.'))
            elif interface.active:
                self.env.cr.execute('SELECT id FROM res_company WHERE id=%s FOR UPDATE', [interface.company_id.id])
                if not interface.inventory_location_ids or any(l.usage != 'internal' or l.company_id != interface.company_id for l in interface.inventory_location_ids):
                    raise ValidationError(self.env._('盘点接口请选择当前公司的内部库位.'))
                # Explicit overlap check across only this company's count interfaces.
                if self.sudo().search_count([('id', '!=', interface.id), ('active', '=', True), ('kind', '=', 'inventory'),
                        ('company_id', '=', interface.company_id.id), ('inventory_location_ids', 'in', interface.inventory_location_ids.ids)]):
                    raise ValidationError(self.env._('同一库位只能启用一个盘点同步接口.'))

    def _lock_configuration(self):
        self.check_access('write')
        for interface in self:
            interface.flush_recordset()
            self.env.cr.execute('SELECT id FROM blue_erp_interface WHERE id = %s FOR UPDATE', [interface.id])
            if self.env['stock.picking'].search_count([('blue_erp_document_id.interface_id', '=', interface.id), ('state', 'not in', ['done', 'cancel'])]):
                raise UserError(self.env._('ERP 仍有关联单据未结束,请先处理后修改配置.'))
            if self.env['blue.erp.event'].search_count([('interface_id', '=', interface.id), ('state', 'not in', ['done', 'failed'])]):
                raise UserError(self.env._('存在未结束同步记录,请先处理后修改接口配置.'))

    def _scope(self):
        self.ensure_one()
        return {'interface_id': self.id, 'company_id': self.company_id.id, 'kind': self.kind,
                'connection_id': self.connection_id.id, 'connection_fingerprint': self.connection_id._fingerprint(),
                'picking_type_id': self.picking_type_id.id, 'source_id': self.location_src_id.id, 'destination_id': self.location_dest_id.id,
                'inventory_location_ids': sorted(self.inventory_location_ids.ids), 'inbound_lines_key': self.inbound_lines_key,
                'operations': {row.code: row.path for row in self.operation_ids}}

    def _published(self):
        self.ensure_one()
        release = self.profile_id.active_release_id
        if not self.active or not self.connection_id.active or not release:
            raise UserError(self.env._('请先启用连接及接口,并验证发布接口代码.'))
        if json.loads(release.snapshot)['scope']['erp_scope'] != self._scope():
            raise UserError(self.env._('连接或接口配置已变化,请重新验证并发布代码.'))
        return release

    def _payload(self, phase, message=None, candidates=None, **request):
        self.ensure_one()
        return {'request': {'phase': phase, 'kind': self.kind, 'event_key': '', 'external_id': '', 'number': '',
                            'message': message or {}, 'http_status': 0, 'operation': '', **request}, 'candidates': candidates or []}

    def _receive(self, message):
        self.ensure_one()
        if self.kind == 'inventory':
            raise UserError(self.env._('盘点接口只发送 WMS 已确认的差异.'))
        bounded(message)
        if type(message) is not dict or type(message.get(self.inbound_lines_key)) is not list:
            raise ValidationError(self.env._('ERP 报文必须包含配置的明细数组.'))
        # Touch the gate row without changing metadata. Under repeatable-read a
        # concurrent receiver gets a serialization retry and a fresh document snapshot.
        self.env.cr.execute('UPDATE blue_erp_interface SET write_date=write_date WHERE id=%s RETURNING id', [self.id])
        self.env.cr.fetchone()
        release = self._published()
        result = run_mapping(release.version_id.code_text,
                             self._payload('receive', message, message[self.inbound_lines_key]))
        documents = self.env['blue.erp.document']
        for data in result['documents']:
            data = {**data, 'lines': sorted(data['lines'], key=lambda row: row['external_line_id'])}
            existing = documents.search([('interface_id', '=', self.id), ('external_id', '=', data['external_id'])], limit=1)
            if existing:
                if existing.content_hash != digest(data):
                    raise ValidationError(self.env._('ERP 单据内容已变化,请人工核对后处理.'))
                documents |= existing
            else:
                document = documents.with_context(blue_erp_token=ERP_TOKEN).create({
                    'interface_id': self.id, 'company_id': self.company_id.id, 'external_id': data['external_id'],
                    'number': data['number'], 'normalized': data, 'content_hash': digest(data), 'release_id': release.id})
                document._create_pickings()
                documents |= document
        return [{'external_id': d.external_id, 'number': d.number, 'wms_documents': d.picking_ids.mapped('name')} for d in documents]

    def action_ai(self):
        manager(self)
        return self.profile_id.action_blue_ai_chat()

    def action_validate(self):
        manager(self)
        return self.profile_id.action_validate()

    def action_publish(self):
        manager(self)
        return self.profile_id.action_publish()

    def action_new_draft(self):
        manager(self)
        return self.profile_id.action_new_draft()

    def action_rollback(self):
        manager(self)
        return self.profile_id.action_rollback()
