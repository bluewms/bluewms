import json

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Domain

from odoo.addons.blue_config_asset.models.blue_config_profile import digest

from .policy_guard import POLICY_TOKEN


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    blue_putaway_release_id = fields.Many2one('blue.config.release', '分配使用版本', readonly=True, copy=False, check_company=True, ondelete='restrict')
    blue_putaway_reason = fields.Char('上架选择原因', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('blue_putaway_token') is not POLICY_TOKEN and any({'blue_putaway_release_id', 'blue_putaway_reason'}.intersection(vals) for vals in vals_list):
            raise AccessError(self.env._('Putaway execution fields cannot be supplied directly.'))
        lines = super().create(vals_list)
        if self.env.context.get('blue_putaway_token') is not POLICY_TOKEN:
            lines._blue_apply_policy()
        return lines

    def write(self, vals):
        internal = self.env.context.get('blue_putaway_token') is POLICY_TOKEN
        if {'blue_putaway_release_id', 'blue_putaway_reason'}.intersection(vals) and not internal:
            raise AccessError(self.env._('Putaway execution fields cannot be supplied directly.'))
        result = super().write(vals)
        if not internal and {'lot_id', 'lot_name', 'quantity', 'uom_id', 'product_id', 'move_id', 'picking_id', 'result_package_id', 'package_id'}.intersection(vals):
            self._blue_apply_policy()
        return result

    def _apply_putaway_strategy(self):
        internal = self.with_context(blue_putaway_token=POLICY_TOKEN)
        result = super(StockMoveLine, internal)._apply_putaway_strategy()
        self._blue_apply_policy()
        return result

    def _action_done(self):
        extra = self._blue_apply_policy(final=True)
        # Native lot creation and quant synchronization must not re-enter an
        # allocation after some contents have already been synchronized.
        internal = (self | extra).with_context(blue_putaway_token=POLICY_TOKEN)
        return super(StockMoveLine, internal)._action_done()

    def _blue_eligible(self):
        self.ensure_one()
        return bool(self.picking_id and self.state not in ('draft', 'done', 'cancel') and self.move_id
                    and (self.product_id.is_storable or self.result_package_id)
                    and not (self.move_id.location_id == self.move_id.location_dest_id and self.location_id == self.location_dest_id))

    def _blue_native_paths(self):
        lines, package = self._blue_allocation_unit()
        paths = None
        all_rules = self.env['stock.putaway.rule']
        requirement = 0
        for base, grouped_lines in lines.grouped(lambda other: other.move_id.location_dest_id).items():
            for product in grouped_lines.product_id:
                categories = product.categ_id
                parent = product.categ_id.parent_id
                while parent:
                    categories |= parent
                    parent = parent.parent_id
                package_type = package.package_type_id if package else grouped_lines.filtered(lambda other: other.product_id == product)[:1].move_id.packaging_uom_id.package_type_id
                rules = base.putaway_rule_ids.filtered(lambda rule:
                    rule.active and rule.company_id == self.company_id
                    and (not rule.product_id or rule.product_id == product)
                    and (not rule.category_id or rule.category_id in categories)
                    and (not rule.package_type_ids or package_type in rule.package_type_ids))
                rules = rules.sorted(lambda rule: (bool(rule.package_type_ids), bool(rule.product_id),
                                                   bool(rule.category_id == product.categ_id), bool(rule.category_id)), reverse=True)
                all_rules |= rules
                choices = {}
                if not rules:
                    fallback = base.child_internal_location_ids[:1] if base.usage == 'view' else base
                    if fallback and fallback.usage == 'internal':
                        choices[fallback.id] = [(0, 0)]
                for rank, rule in enumerate(rules):
                    for location in rule._blue_locations(product):
                        choices.setdefault(location.id, []).append((rank, rule.id))
                if paths is None:
                    paths = {location_id: {requirement: variants} for location_id, variants in choices.items()}
                else:
                    paths = {location_id: dict(previous) for location_id, previous in paths.items() if location_id in choices}
                    for location_id in paths:
                        paths[location_id][requirement] = choices[location_id]
                requirement += 1
        return paths or {}, all_rules

    def _blue_lot_name(self):
        self.ensure_one()
        if self.lot_id:
            return self.lot_id.name
        if self.product_id.tracking in ('lot', 'serial') and self.picking_type_id.use_create_lots:
            return self.lot_name or False
        return False

    def _blue_allocation_unit(self):
        self.ensure_one()
        package = self.result_package_id.outermost_package_id
        if not package:
            return self, self.env['stock.package']
        lines = self.picking_id.move_line_ids.filtered(lambda other:
            other.state not in ('draft', 'done', 'cancel')
            and other.product_id.uom_id.compare(other.quantity_product_uom, 0) > 0
            and other.result_package_id.outermost_package_id == package)
        return lines or self, package

    def _blue_supplementary_results(self, payload, paths, bindings):
        evaluated = {}
        active = [binding for binding in bindings.values() if binding.release_id]
        for binding in active:
            release = binding.release_id
            profile = binding.profile_id
            snapshot = json.loads(release.snapshot)
            if digest(snapshot) != release.content_hash or snapshot['scope'] != profile._scope_snapshot():
                raise UserError(self.env._('请重新验证并发布按原生规则绑定的增强版本.'))
            contract = snapshot['contracts']['putaway_policy']
            if contract['version_id'] != release.version_id.id or contract['content_hash'] != release.version_id.content_hash or contract['code'] != release.version_id.code_text:
                raise UserError(self.env._('The policy release code is inconsistent.'))
            candidates = [item for item in payload['candidates'] if any(
                any(rule_id == binding.rule_key for __, rule_id in variants)
                for variants in paths[item['location_id']].values())]
            if snapshot['scope']['requires_batch_names'] and payload['request']['has_unknown_batch']:
                evaluated[binding.rule_key] = {}
                continue
            scoped = {'request': dict(payload['request'], rule_id=binding.rule_key), 'candidates': candidates}
            result = self.env['blue.extension.contract']._run(contract['code'], scoped, contract['contract'])
            evaluated[binding.rule_key] = {item['location_id']: item for item in result}
        results = []
        for candidate in payload['candidates']:
            location_id = candidate['location_id']
            selected = []
            for variants in paths[location_id].values():
                accepted = [(rank, rule_id) for rank, rule_id in variants
                            if rule_id not in evaluated or location_id in evaluated[rule_id]]
                if not accepted:
                    break
                selected.append(min(accepted))
            else:
                chosen_rules = {rule_id for __, rule_id in selected if rule_id}
                reasons = []
                score = 0
                chosen_bindings = []
                for rule_id in sorted(chosen_rules):
                    binding = bindings[rule_id]
                    chosen_bindings.append(binding.id)
                    if rule_id in evaluated:
                        item = evaluated[rule_id][location_id]
                        score += item['score']
                        reasons.append(item['reason'])
                results.append({'location_id': location_id, 'score': score, 'system_priority': max(rank for rank, __ in selected),
                                'reason': ' / '.join(dict.fromkeys(reasons))[:512] or self.env._('原生上架规则'),
                                'binding_ids': chosen_bindings})
        return sorted(results, key=lambda item: (item['system_priority'], item['score'], item['location_id']))

    def _blue_apply_policy(self, final=False):
        if self.env.context.get('blue_putaway_token') is POLICY_TOKEN:
            return self.env['stock.move.line']
        extra = self.env['stock.move.line']
        processed, locked_warehouses = set(), set()
        service = self.env['blue.config.profile']
        for line in self.sorted('id'):
            if not line._blue_eligible() or line.product_id.uom_id.compare(line.quantity_product_uom, 0) <= 0:
                continue
            lines, package = line._blue_allocation_unit()
            key = (line.picking_id.id, package.id if package else False, line.id if not package else False)
            if key in processed:
                continue
            processed.add(key)
            paths, rules = line._blue_native_paths()
            if not rules:
                continue
            lines.check_access('write')
            warehouses = lines.move_id.location_dest_id.warehouse_id | line.picking_id.picking_type_id.warehouse_id
            warehouses |= self.env['stock.location'].browse(list(paths)).warehouse_id
            if not warehouses:
                raise UserError(self.env._('增强分配需要原生作业或目的库位关联仓库.'))
            for warehouse in warehouses.sorted('id'):
                if warehouse.id not in locked_warehouses:
                    warehouse._blue_lock_putaway()
                    locked_warehouses.add(warehouse.id)
            bindings = line.picking_id._blue_rule_bindings(rules)
            active = [binding for binding in bindings.values() if binding.release_id]
            if not active:
                continue
            if package and any(not other.product_id.is_storable for other in lines):
                if final:
                    raise UserError(self.env._('整托盘上架需要所有商品启用库存追踪, 才能准确计算托盘占用.'))
                continue
            if package and not package.package_type_id:
                if final:
                    raise UserError(self.env._('请先为托盘选择包装类型, 再执行上架.'))
                continue
            if not final and any(other.product_id.tracking != 'none' and not other._blue_lot_name() for other in lines):
                continue
            pending = [line]
            iterations = 0
            while pending:
                current = pending.pop()
                iterations += 1
                if iterations > 200:
                    raise UserError(self.env._('A move line would need more than 200 putaway allocations.'))
                paths, __ = current._blue_native_paths()
                payload = service._prepare_putaway_payload(current)
                result = current._blue_supplementary_results(payload, paths, bindings)
                if not result:
                    raise UserError(self.env._('找不到同时满足系统设置和补充条件的库位: %s.', current.product_id.display_name))
                selected = result[0]
                selected_bindings = self.env['blue.putaway.binding'].browse(selected['binding_ids'])
                release = selected_bindings.release_id[:1] or active[0].release_id
                if not line.picking_id.blue_putaway_release_id:
                    line.picking_id.with_context(blue_putaway_token=POLICY_TOKEN).write({'blue_putaway_release_id': release.id})
                candidate = next(item for item in payload['candidates'] if item['location_id'] == selected['location_id'])
                if package:
                    unchanged = all(other.location_dest_id.id == selected['location_id'] and other.blue_putaway_release_id == release
                                    and other.blue_putaway_reason == selected['reason'] for other in lines)
                    lines.with_context(blue_putaway_token=POLICY_TOKEN).write({
                        'location_dest_id': selected['location_id'], 'blue_putaway_release_id': release.id, 'blue_putaway_reason': selected['reason']})
                    quantity = 1
                else:
                    quantity = min(current.quantity_product_uom, candidate['max_quantity'])
                    line_quantity = current.product_id.uom_id._compute_quantity(quantity, current.uom_id, round=False)
                    line_quantity = current.uom_id.round(line_quantity, rounding_method='DOWN')
                    quantity = current.uom_id._compute_quantity(line_quantity, current.product_id.uom_id)
                    if current.uom_id.compare(line_quantity, 0) <= 0:
                        raise UserError(self.env._('The available capacity is smaller than the move unit precision.'))
                    internal = current.with_context(blue_putaway_token=POLICY_TOKEN)
                    remaining = self.env['stock.move.line']
                    if current.uom_id.compare(line_quantity, current.quantity) < 0:
                        remaining = internal.copy({'quantity': current.quantity - line_quantity,
                                                   'blue_putaway_release_id': False, 'blue_putaway_reason': False})
                        extra |= remaining
                        pending.append(remaining)
                    unchanged = (current.location_dest_id.id == selected['location_id'] and current.blue_putaway_release_id == release
                                 and current.blue_putaway_reason == selected['reason'] and not remaining)
                    internal.write({'quantity': line_quantity, 'location_dest_id': selected['location_id'],
                                    'blue_putaway_release_id': release.id, 'blue_putaway_reason': selected['reason']})
                if not unchanged:
                    self.env['blue.putaway.application'].with_context(blue_putaway_token=POLICY_TOKEN).create({
                        'company_id': current.company_id.id, 'picking_id': current.picking_id.id, 'move_line_id': current.id,
                        'release_id': release.id, 'location_id': selected['location_id'], 'quantity': quantity,
                        'unit': 'package' if package else 'loose', 'package_id': package.id or False, 'reason': selected['reason'],
                        'binding_ids': [(6, 0, selected['binding_ids'])],
                        'input_json': json.dumps(payload, ensure_ascii=False), 'output_json': json.dumps(result, ensure_ascii=False),
                    })
        return extra
