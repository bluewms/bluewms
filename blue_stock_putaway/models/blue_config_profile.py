# Native rule matching and priority follow the Odoo stock implementation.
# Copyright Odoo S.A. and 宁波宝蓝物流科技有限公司.
# License AGPL-3.0-or-later; the upstream Odoo dependency remains LGPL-3.

from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain


class BlueConfigProfile(models.Model):
    _inherit = 'blue.config.profile'

    putaway_rule_ids = fields.One2many('stock.putaway.rule', 'blue_profile_id', '使用此增强策略的原生规则')

    def _requires_batch_names(self):
        self.ensure_one()
        return self.template_id.requires_batch_names or self.template_id == self.env.ref('blue_stock_putaway.blue_scene_template_same_lot')

    def _scope_snapshot(self):
        result = super()._scope_snapshot()
        result.update(behavior='native_rule_binding/3', requires_batch_names=self._requires_batch_names())
        return result

    def _draft_payload(self):
        result = super()._draft_payload()
        result['scope'] = self._scope_snapshot()
        return result

    def action_open_preview(self):
        self._check_manager()
        return {'type': 'ir.actions.act_window', 'name': self.env._('真实单据试算'), 'res_model': 'blue.putaway.preview',
                'view_mode': 'form', 'target': 'new', 'context': {'default_profile_id': self.id, 'default_rule_id': self.putaway_rule_ids.id if len(self.putaway_rule_ids) == 1 else False}}

    def _prepare_putaway_payload(self, line, rule=None):
        line.ensure_one()
        line.check_access('read')
        company = line.company_id
        if self:
            self.ensure_one()
            self.check_access('read')
            if self.company_id != company:
                raise UserError(self.env._('请选择同一公司下的作业明细.'))
        if rule:
            rule.check_access('read')
            if rule.company_id != company:
                raise UserError(self.env._('原生规则和明细必须属于同一公司.'))
        lines, package = line._blue_allocation_unit()
        lines.check_access('read')
        if any(other.company_id != company for other in lines):
            raise UserError(self.env._('A package cannot span companies.'))
        quantities = defaultdict(float)
        lot_pairs, incoming_names = set(), set()
        unknown_batch = False
        for other in lines:
            if other.product_id.uom_id.compare(other.quantity_product_uom, 0) <= 0:
                continue
            quantities[other.product_id.id] += other.quantity_product_uom
            label = other._blue_lot_name()
            lot_pairs.add((other.product_id.id, label))
            if label:
                incoming_names.add(label)
            else:
                unknown_batch = True
        if not quantities:
            raise UserError(self.env._('Choose a storable product move line with positive quantity.'))
        products = lines.product_id
        if package:
            # Existing contents also belong to the same physical pallet.
            for quant in package.contained_quant_ids:
                if quant.uom_id.compare(quant.quantity, 0) > 0:
                    if quant.company_id != company:
                        raise UserError(self.env._('A package cannot span companies.'))
                    if quant.lot_id:
                        incoming_names.add(quant.lot_id.name)
                    else:
                        unknown_batch = True
        batch_name = next(iter(incoming_names)) if len(incoming_names) == 1 and not unknown_batch else False
        paths, rules = line._blue_native_paths()
        if rule:
            paths = {location_id: requirements for location_id, requirements in paths.items()
                     if any(any(rule_id == rule.id for __, rule_id in choices) for choices in requirements.values())}
        ranks = {location_id: max(min(rank for rank, __ in choices) for choices in requirements.values()) for location_id, requirements in paths.items()}
        warehouse = line.picking_id.picking_type_id.warehouse_id or line.move_id.location_dest_id.warehouse_id
        locations = self.env['stock.location'].search(
            Domain('id', 'in', list(ranks))
            & Domain('company_id', 'in', [False, company.id]) & Domain('active', '=', True)
            & Domain('usage', '=', 'internal') & Domain('id', 'not in', lines.location_id.ids), order='id', limit=201)
        if len(locations) > 200:
            raise UserError(self.env._('Select a smaller storage area: at most 200 candidate locations per trial.'))
        excluded_ids = lines._origin.ids
        quants = self.env['stock.quant'].search(Domain('location_id', 'in', locations.ids) & Domain('company_id', '=', company.id))
        pending = self.env['stock.move.line'].search(
            Domain('location_dest_id', 'in', locations.ids) & Domain('company_id', '=', company.id)
            & Domain('state', 'not in', ['draft', 'cancel', 'done']) & Domain('id', 'not in', excluded_ids))
        history = self.env['stock.move.line'].search(
            Domain('picking_id', '=', line.picking_id.id) & Domain('location_dest_id', 'in', locations.ids)
            & Domain('company_id', '=', company.id) & Domain('state', '=', 'done') & Domain('id', 'not in', excluded_ids))
        quantities_at = defaultdict(float)
        batch_names_at, lots_at = defaultdict(set), defaultdict(set)
        package_ids_at = defaultdict(set)
        occupied, unknown_at, same_picking, positive_dimensions = set(), set(), set(), set()
        requested_type = package.package_type_id if package else self.env['stock.package.type']

        def physical_capacity_package(current):
            matched = self.env['stock.package']
            while current:
                if current.package_type_id == requested_type:
                    matched = current
                current = current.parent_package_id
            return matched

        for quant in quants:
            quantities_at[(quant.location_id.id, quant.product_id.id)] += quant.quantity
            if quant.uom_id.compare(quant.quantity, 0) <= 0:
                continue
            location_id = quant.location_id.id
            occupied.add(location_id)
            lots_at[location_id].add((quant.product_id.id, quant.lot_id.name or False))
            positive_dimensions.add((location_id, quant.product_id.id, quant.lot_id.id, quant.owner_id.id))
            if quant.lot_id:
                batch_names_at[location_id].add(quant.lot_id.name)
            else:
                unknown_at.add(location_id)
            if package and quant.package_id:
                existing = physical_capacity_package(quant.package_id)
                if existing:
                    package_ids_at[location_id].add(existing.id)
        foreign_package_destinations = set()
        for other in pending:
            quantities_at[(other.location_dest_id.id, other.product_id.id)] += other.quantity_product_uom
            if other.product_id.uom_id.compare(other.quantity_product_uom, 0) <= 0:
                continue
            location_id = other.location_dest_id.id
            occupied.add(location_id)
            label = other._blue_lot_name()
            lots_at[location_id].add((other.product_id.id, label))
            if label:
                batch_names_at[location_id].add(label)
            else:
                unknown_at.add(location_id)
            if other.picking_id == line.picking_id:
                same_picking.add(location_id)
            if package and other.result_package_id:
                outer = other.result_package_id.outermost_package_id
                if outer.package_type_id == requested_type:
                    package_ids_at[location_id].add(outer.id)
                if outer == package:
                    foreign_package_destinations.add(location_id)
        if len(foreign_package_destinations) > 1:
            raise UserError(self.env._('This pallet already has conflicting pending destinations.'))
        for other in history:
            if other.product_id.uom_id.compare(other.quantity_product_uom, 0) > 0 and (
                other.location_dest_id.id, other.product_id.id, other.lot_id.id, other.owner_id.id
            ) in positive_dimensions:
                same_picking.add(other.location_dest_id.id)
        weights = locations._get_weight(set(excluded_ids))
        incoming_weight = sum(product.weight * quantities[product.id] for product in products)
        candidates = []
        for location in locations:
            if foreign_package_destinations and location.id not in foreign_package_destinations:
                continue
            category = location.storage_category_id
            if category and category.allow_new_product == 'empty' and location.id in occupied:
                continue
            if category and category.allow_new_product == 'same':
                present_products = {product_id for product_id, __ in lots_at[location.id]}
                if len(products) != 1 or (present_products and present_products != set(products.ids)):
                    continue
            checked = location.with_context(exclude_sml_ids=set(excluded_ids), products=products)
            if package:
                if not requested_type:
                    continue
                occupied_ids = package_ids_at[location.id]
                additional_slot = int(package.id not in occupied_ids)
                capacities = category.package_capacity_ids.filtered(lambda entry: entry.package_type_id == requested_type) if category else self.env['stock.storage.category.capacity']
                if capacities and len(occupied_ids) + additional_slot > capacities.quantity:
                    continue
                if category and weights[location]['forecast_weight'] + incoming_weight > category.max_weight:
                    continue
                full = True
                for product in products:
                    capacity = category.product_capacity_ids.filtered(lambda entry: entry.product_id == product) if category else self.env['stock.storage.category.capacity']
                    if capacity and product.uom_id.compare(quantities_at[(location.id, product.id)] + quantities[product.id], capacity.quantity) > 0:
                        full = False
                        break
                    if not checked._check_can_be_used(product, quantity=quantities[product.id], package=package,
                                                      location_qty=len(occupied_ids - {package.id})):
                        full = False
                        break
                if not full:
                    continue
                maximum = line.quantity_product_uom
            else:
                product = line.product_id
                maximum = line.quantity_product_uom
                if category:
                    capacity = category.product_capacity_ids.filtered(lambda entry: entry.product_id == product)
                    if capacity:
                        maximum = min(maximum, capacity.quantity - quantities_at[(location.id, product.id)])
                    if product.weight > 0:
                        maximum = min(maximum, (category.max_weight - weights[location]['forecast_weight']) / product.weight)
                maximum = product.uom_id.round(maximum, rounding_method='DOWN')
                move_quantity = product.uom_id._compute_quantity(maximum, line.uom_id, round=False)
                move_quantity = line.uom_id.round(move_quantity, rounding_method='DOWN')
                maximum = line.uom_id._compute_quantity(move_quantity, product.uom_id, round=False)
                if product.uom_id.compare(maximum, 0) <= 0:
                    continue
                if not checked._check_can_be_used(product, quantity=maximum, location_qty=quantities_at[(location.id, product.id)]):
                    continue
            candidates.append({'location_id': location.id, 'name': location.complete_name,
                'system_priority': ranks[location.id], 'same_lot': bool(lot_pairs & lots_at[location.id]),
                'same_picking': location.id in same_picking, 'empty': location.id not in occupied,
                'batch_name_matches': bool(batch_name and location.id not in unknown_at and batch_names_at[location.id] == {batch_name}),
                'batch_names': sorted(batch_names_at[location.id]), 'has_unknown_batch': location.id in unknown_at,
                'current_product_qty': quantities_at[(location.id, line.product_id.id)],
                'occupied_packages': len(package_ids_at[location.id]) if package else 0,
                'package_capacity': capacities.quantity if package and capacities else False,
                'packages_after': len(package_ids_at[location.id]) + additional_slot if package else 0,
                'max_quantity': maximum, 'fits_all': bool(package) or line.product_id.uom_id.compare(maximum, line.quantity_product_uom) >= 0})
        return {'request': {'unit': 'package' if package else 'loose', 'package_id': package.id or False,
            'package_type_id': requested_type.id or False, 'package_count': int(bool(package)),
            'product_id': products.id if len(products) == 1 else False, 'product_ids': products.ids,
            'lot_id': line.lot_id.id or False, 'batch_name': batch_name, 'batch_names': sorted(incoming_names),
            'has_single_batch_name': bool(batch_name), 'has_unknown_batch': unknown_batch,
            'quantities': {str(product.id): quantities[product.id] for product in products},
            'picking_id': line.picking_id.id, 'quantity': line.quantity_product_uom if not package else False,
            'company_id': company.id, 'warehouse_id': warehouse.id or False, 'rule_id': rule.id if rule else False}, 'candidates': candidates}

    def _rank_supplementary_result(self, result, payload):
        priorities = {item['location_id']: item['system_priority'] for item in payload['candidates']}
        return sorted(result, key=lambda item: (priorities[item['location_id']], item['score'], item['location_id']))
