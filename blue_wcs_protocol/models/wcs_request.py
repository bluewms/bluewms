import hashlib
import json

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.blue_wcs_base.models.guard import WCS_TOKEN

from ..tools.protocol import CONTRACT
from .guard import PROTOCOL_TOKEN


class WcsRequest(models.Model):
    _inherit = 'wcs.request'

    protocol_release_id = fields.Many2one('blue.config.release', '固定设备协议版本', readonly=True,
                                          copy=False, check_company=True, ondelete='restrict')
    protocol_category_id = fields.Many2one('wcs.equipment.category', '固定协议类别', readonly=True,
                                           copy=False, check_company=True, ondelete='restrict')
    protocol_task_snapshot = fields.Json('固定设备报文输入', readonly=True, copy=False)
    protocol_planned_location_id = fields.Many2one('stock.location', '原计划目的位置', readonly=True, check_company=True)
    protocol_actual_location_id = fields.Many2one('stock.location', '实际完成库位', readonly=True, check_company=True)
    protocol_reported_point = fields.Char('设备回报点位', readonly=True)
    protocol_subposition = fields.Char('回写包裹子位置', readonly=True)
    protocol_last_callback = fields.Json('完成回调原文', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('blue_wcs_token') is not WCS_TOKEN:
            return super().create(vals_list)
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            device = self.env['wcs.equipment'].browse(vals['equipment_id'])
            if device.adapter_code == 'protocol':
                category = device.category_id
                release = category._protocol_release()
                vals.update(protocol_release_id=release.id, protocol_category_id=category.id,
                            protocol_planned_location_id=vals.get('location_dest_id'))
            prepared.append(vals)
        tasks = super().create(prepared)
        for task in tasks.filtered('protocol_release_id'):
            task.with_context(blue_protocol_token=PROTOCOL_TOKEN).write({
                'protocol_task_snapshot': task._protocol_input(frozen=False)})
        return tasks

    def _wcs_workflow_fields(self):
        allowed = super()._wcs_workflow_fields()
        if self.env.context.get('blue_protocol_token') is PROTOCOL_TOKEN:
            allowed |= {'protocol_task_snapshot', 'protocol_actual_location_id', 'protocol_reported_point',
                        'protocol_subposition', 'protocol_last_callback', 'location_dest_id'}
        return allowed

    def _requires_callback_auth(self):
        if self.protocol_release_id:
            return self.protocol_category_id.sudo().protocol_callback_mode != 'legacy'
        return super()._requires_callback_auth()

    def _protocol_scope(self):
        self.ensure_one()
        return json.loads(self.protocol_release_id.snapshot)['scope']['device_scope']

    def _protocol_input(self, phase='request', message=None, http_status=0, frozen=True):
        self.ensure_one()
        if frozen and self.protocol_task_snapshot:
            data = json.loads(json.dumps(self.protocol_task_snapshot))
            data['request'].update(phase=phase, message=message or {}, http_status=http_status)
            return data
        items = [{'product_code': row.product_id.default_code or str(row.product_id.id),
                  'quantity': row.quantity, 'uom': row.uom_id.name, 'lot': row.lot_id.name or ''}
                 for row in self.plan_id.line_ids] if self.role == 'goods' else []
        return {'request': {'phase': phase, 'task': {'task_id': self.name, 'source': self.source_point,
            'destination': self.destination_point, 'template': self.task_type, 'carrier': self.carrier_code or '',
            'device_code': self.equipment_id.protocol_device_code or '', 'role': self.role,
            'operation': self.picking_type_id.code},
            'parameters': self._protocol_scope()['parameters'],
            'message': message or {}, 'http_status': http_status}, 'candidates': items}

    def _protocol_run(self, phase, message=None, http_status=0):
        self.ensure_one()
        return self.env['blue.extension.contract']._run(self.protocol_release_id.version_id.code_text,
            self._protocol_input(phase, message, http_status), CONTRACT)

    def _payload(self):
        return self._protocol_run('request')['body'] if self.protocol_release_id else super()._payload()

    def _preflight(self):
        if self.protocol_release_id:
            if self.protocol_category_id != self.equipment_id.category_id or self.equipment_id.adapter_code != 'protocol':
                raise UserError(self.env._('设备类别或协议已改变,请先核对固定任务.'))
            self.protocol_category_id._protocol_check_configuration()
            if self.protocol_category_id._protocol_scope() != self._protocol_scope():
                raise UserError(self.env._('人工接口配置已改变,请先核对固定任务.'))
        return super()._preflight()

    def _dispatch_connection(self):
        data = super()._dispatch_connection()
        if self.protocol_release_id:
            data.update(protocol_code=self.protocol_release_id.version_id.code_text,
                        protocol_input=self._protocol_input())
        return data

    def _receive_event(self, event_id, event, point='', actual_destination=''):
        if self.protocol_release_id and self.env.context.get('blue_protocol_token') is not PROTOCOL_TOKEN:
            raise UserError(self.env._('此任务必须通过固定版本的设备协议回调完成,不能使用普通设备回执.'))
        return super()._receive_event(event_id, event, point, actual_destination)

    def _protocol_location(self, code):
        scope = self._protocol_scope()
        root_id = scope['destination_root_id']
        if not scope['allow_destination'] or not root_id:
            raise ValidationError(self.env._('当前类别未人工允许库存目的库位回写.'))
        base = fields.Domain('company_id', '=', self.company_id.id) & fields.Domain('usage', '=', 'internal')
        base &= fields.Domain('id', 'child_of', root_id)
        base &= fields.Domain('barcode', '=', code) | fields.Domain('agv_map_point', '=', code)
        locations = self.env['stock.location'].search(base, limit=2)
        if len(locations) != 1:
            raise ValidationError(self.env._('完成库位编码必须在批准库区内唯一匹配既有库位.'))
        location = locations
        if location._blue_stock_blocking_location(receiving=True):
            raise ValidationError(self.env._('实际目的库位已冻结或禁止入库.'))
        return location

    def _protocol_check_final_goods(self):
        if self.role != 'goods' or not self.plan_id.line_ids:
            raise ValidationError(self.env._('位置回写必须关联明确的货物明细.'))
        if self.search_count([('plan_id', '=', self.plan_id.id), ('role', '=', 'goods'),
                              ('step', '>', self.step), ('state', '!=', 'cancelled')], limit=1):
            raise ValidationError(self.env._('中间搬运步骤不能回写最终库存位置或包裹子位置.'))
        if self.picking_id.state in ('done', 'cancel'):
            raise ValidationError(self.env._('已完成或取消的库存单据不能回写历史位置.'))

    def _protocol_apply_location(self, location):
        self._protocol_check_final_goods()
        rows = self.plan_id.line_ids
        lines = rows.move_line_id
        if len(lines) != len(rows) or any(line.state in ('done', 'cancel') for line in lines):
            raise ValidationError(self.env._('库存明细已变化,请核对实际完成库位.'))
        if self.env['wcs.plan.line'].search_count([
                ('move_line_id', 'in', lines.ids), ('plan_id', '!=', self.plan_id.id),
                ('plan_id.request_ids.state', '!=', 'cancelled')], limit=1):
            raise ValidationError(self.env._('同一库存明细有多个搬运计划,请人工核对实际库位.'))
        for row in rows:
            line = row.move_line_id
            if (line.product_id != row.product_id or line.lot_id != row.lot_id or line.uom_id != row.uom_id
                    or line.uom_id.compare(line.quantity, row.quantity) != 0):
                raise ValidationError(self.env._('部分数量或货物已变化,不能将整条库存明细改到回报库位.'))
            if line.location_id == location:
                raise ValidationError(self.env._('实际目的库位不能等于原库存起点.'))
        # Serialize capacity and package-slot decisions for this exact approved location.
        self.env.cr.execute('SELECT id FROM stock_location WHERE id = %s FOR UPDATE', [location.id])
        location.invalidate_recordset()
        products = rows.product_id
        check = location.with_context(exclude_sml_ids=set(lines.ids), products=products)
        carrier = self.plan_id.carrier_id
        if carrier and carrier.package_type_id:
            packages = self.env['stock.quant'].search([
                ('location_id', '=', location.id), ('quantity', '>', 0)]).package_id.outermost_package_id
            pending = self.env['stock.move.line'].search([
                ('location_dest_id', '=', location.id), ('state', 'not in', ['done', 'cancel']),
                ('id', 'not in', lines.ids)]).result_package_id.outermost_package_id
            count = len((packages | pending).filtered(lambda item: item != carrier and item.package_type_id == carrier.package_type_id))
            if not check._check_can_be_used(products, package=carrier, location_qty=count):
                raise ValidationError(self.env._('实际目的库位不满足原生包裹容量、重量或混放条件.'))
        else:
            for product in products:
                quantity = sum(row.uom_id._compute_quantity(row.quantity, product.uom_id, round=False)
                               for row in rows if row.product_id == product)
                existing = self.env['stock.quant'].search([
                    ('location_id', '=', location.id), ('product_id', '=', product.id)]).mapped('quantity')
                incoming = self.env['stock.move.line'].search([
                    ('location_dest_id', '=', location.id), ('product_id', '=', product.id),
                    ('state', 'not in', ['done', 'cancel']), ('id', 'not in', lines.ids)])
                forecast = sum(existing) + sum(incoming.mapped('quantity_product_uom'))
                if not check._check_can_be_used(product, quantity=quantity, location_qty=forecast):
                    raise ValidationError(self.env._('实际目的库位不满足原生容量、重量或混放条件.'))
        lines.with_context(blue_wcs_token=WCS_TOKEN).write({'location_dest_id': location.id})
        self.with_context(blue_wcs_token=WCS_TOKEN, blue_protocol_token=PROTOCOL_TOKEN).write({
            'location_dest_id': location.id, 'protocol_actual_location_id': location.id})

    def _protocol_packages(self):
        self.ensure_one()
        return self.plan_id.carrier_id or self.plan_id.line_ids.package_id

    def _protocol_write_subposition(self, value):
        locations = self.plan_id.line_ids.move_line_id.location_dest_id
        if len(locations) != 1:
            raise ValidationError(self.env._('子位置必须归属唯一的实际库存库位.'))
        location = locations
        # Coordinate occupancy also includes completed device events awaiting stock posting.
        self.env.cr.execute('SELECT id FROM stock_location WHERE id = %s FOR UPDATE', [location.id])
        location.invalidate_recordset()
        if location.coordinate_ids:
            coordinates = location.coordinate_ids.filtered(lambda item: value in (item.name, item.location_code))
            if len(coordinates) != 1:
                raise ValidationError(self.env._('回报子位置未唯一匹配该库位已配置的容量位置.'))
            aliases = list({item for item in (coordinates.name, coordinates.location_code) if item})
            own = self._protocol_packages().outermost_package_id
            quants = self.env['stock.quant'].search(fields.Domain('location_id', '=', location.id)
                & (fields.Domain('quantity', '!=', 0) | fields.Domain('reserved_quantity', '!=', 0)))
            occupied = (quants.package_id.outermost_package_id - own).filtered(lambda item: item.package_removal_priority in aliases)
            pending = self.search_count([('id', '!=', self.id), ('company_id', '=', self.company_id.id),
                ('protocol_subposition', 'in', aliases), ('state', '=', 'completed'),
                ('picking_id.state', 'not in', ['done', 'cancel']),
                ('plan_id.line_ids.move_line_id.location_dest_id', '=', location.id)], limit=1)
            if occupied or pending:
                raise ValidationError(self.env._('回报子位置已被其他包裹或待入账任务占用.'))
        self._protocol_packages().write({'package_removal_priority': value})

    def _protocol_receive(self, message):
        self.ensure_one()
        self._lock()
        result = self._protocol_run('callback', message)
        if self.equipment_id.protocol_device_code and message.get('deviceId') != self.equipment_id.protocol_device_code:
            raise ValidationError(self.env._('回调设备编码与任务设备不一致.'))
        intent = {key: value for key, value in result.items() if key != 'response'}
        event_id = hashlib.sha256(json.dumps(intent, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        event = self.env['wcs.event'].search([('request_id', '=', self.id), ('external_id', '=', event_id)], limit=1)
        if event:
            return result['response']
        if self.state not in ('sending', 'accepted', 'running', 'unknown') or self.picking_id.state in ('done', 'cancel'):
            raise ValidationError(self.env._('此任务当前不接受新的完成回报.'))
        if self.equipment_id.category_id != self.protocol_category_id or not self.equipment_id.active:
            raise ValidationError(self.env._('回调任务设备或类别已变化.'))
        scope = self._protocol_scope()
        if result['destination_code']:
            self._protocol_apply_location(self._protocol_location(result['destination_code']))
        elif result['point'] and not result['subposition'] and result['point'] != self.destination_point:
            raise ValidationError(self.env._('回报点与计划终点不同,请在协议中明确子位置或库存库位映射.'))
        if result['subposition']:
            self._protocol_check_final_goods()
            if not scope['allow_subposition'] or not self._protocol_packages():
                raise ValidationError(self.env._('此任务或类别未允许包裹子位置回写.'))
            self._protocol_write_subposition(result['subposition'])
        controlled = self.with_context(blue_wcs_token=WCS_TOKEN, blue_protocol_token=PROTOCOL_TOKEN,
                                      blue_protocol_report=message)
        controlled.write({'protocol_reported_point': result['point'], 'protocol_subposition': result['subposition'],
                          'protocol_last_callback': message})
        controlled._receive_event(event_id, 'end', point=result['point'])
        return result['response']
