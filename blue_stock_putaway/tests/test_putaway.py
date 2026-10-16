import json

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user
from odoo.tools import file_open

from odoo.addons.blue_extension_contract.tools.policy import PolicyError, run_policy
from odoo.addons.blue_stock_putaway.models.policy_guard import POLICY_TOKEN


class TestPutaway(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Regression fixtures are test-only data, not installed generation examples.
        with file_open('blue_stock_putaway/tests/data/putaway_regression_cases.json') as source:
            examples = json.load(source)
        for xml_id, values in examples.items():
            cls.env.ref('blue_stock_putaway.' + xml_id).write(dict(values, cloud_managed=False))
        cls.warehouse = cls.env['stock.warehouse'].create({'name': 'Blue policy test warehouse', 'code': 'BPOL', 'company_id': cls.env.company.id})
        cls.root = cls.env['stock.location'].create({'name': 'Blue policy area', 'usage': 'view', 'location_rank': 'area',
                                                    'location_id': cls.warehouse.lot_stock_id.id, 'company_id': cls.env.company.id})
        cls.locations = cls.env['stock.location'].create([
            {'name': name, 'usage': 'internal', 'location_id': cls.root.id, 'company_id': cls.env.company.id}
            for name in ('Blue policy A', 'Blue policy B', 'Blue policy C')])
        cls.storage = cls.env['stock.storage.category'].create({'name': 'Blue native allowed storage', 'max_weight': 10000, 'company_id': cls.env.company.id})
        cls.locations.storage_category_id = cls.storage
        cls.native_rule = cls.env['stock.putaway.rule'].create({'location_in_id': cls.root.id, 'location_out_id': cls.root.id,
            'sublocation': 'closest_location', 'storage_category_id': cls.storage.id, 'company_id': cls.env.company.id})
        cls.product = cls.env['product.product'].create({'name': 'Blue policy goods', 'is_storable': True, 'tracking': 'lot'})
        cls.lots = cls.env['stock.lot'].create([{'name': name, 'product_id': cls.product.id, 'company_id': cls.env.company.id} for name in ('Blue policy lot 1', 'Blue policy lot 2')])
        cls.template = cls.env.ref('blue_stock_putaway.blue_scene_template_same_lot')
        cls.profile = cls.env['blue.config.profile'].create({'name': 'Blue policy test', 'company_id': cls.env.company.id,
            'template_id': cls.template.id})
        cls.native_rule.blue_profile_id = cls.profile
        cls.profile.action_load_example()
        cls.manager = new_test_user(cls.env, login='blue_policy_manager', groups='stock.group_stock_manager')
        cls.worker = new_test_user(cls.env, login='blue_policy_worker', groups='stock.group_stock_user')

    def _publish(self):
        self.profile.action_validate()
        self.profile.action_publish()
        return self.profile.active_release_id

    def test_machine_contract_matches_actual_putaway_payload_fields(self):
        payload = self.profile._prepare_putaway_payload(self._line(), self.native_rule)
        schema = self.env['blue.extension.contract']._describe(self.profile.contract)
        self.assertEqual(set(payload['request']), set(schema['input']['runtime_request_fields']))
        self.assertTrue(payload['candidates'])
        self.assertEqual(set(payload['candidates'][0]), set(schema['input']['runtime_candidate_fields']))

    def _stock(self, location, qty, lot=None, product=None):
        return self.env['stock.quant']._update_available_quantity(product or self.product, location, qty, lot_id=lot or self.lots[0])

    def _line(self, qty=2, lot=None, picking=None, product=None, uom=None):
        product = product or self.product
        uom = uom or product.uom_id
        if picking is None:
            picking = self.env['stock.picking'].create({'picking_type_id': self.warehouse.in_type_id.id,
                'location_id': self.env.ref('stock.stock_location_suppliers').id, 'location_dest_id': self.root.id})
        move = self.env['stock.move'].create({'product_id': product.id, 'uom_id': uom.id, 'product_uom_qty': qty,
            'picking_id': picking.id, 'location_id': picking.location_id.id, 'location_dest_id': self.root.id})
        move._action_confirm(merge=False)
        values = {'move_id': move.id, 'picking_id': picking.id, 'product_id': product.id,
            'uom_id': uom.id, 'quantity': qty, 'lot_id': (lot or self.lots[0]).id,
            'location_id': picking.location_id.id, 'location_dest_id': self.root.id}
        if move.move_line_ids:
            line = move.move_line_ids[0]
            values['location_dest_id'] = line.location_dest_id.id
            line.write(values)
            return line
        return self.env['stock.move.line'].create(values)

    def _capacity(self, maximum):
        category = self.env['stock.storage.category'].create({'name': 'Blue policy capacity', 'company_id': self.env.company.id,
            'max_weight': 10000, 'allow_new_product': 'mixed',
            'capacity_ids': [Command.create({'product_id': self.product.id, 'quantity': maximum})]})
        self.locations.storage_category_id = category
        self.native_rule.storage_category_id = category
        return category

    def test_examples_edit_validate_publish_and_rollback(self):
        first = self._publish()
        self.assertEqual(self.profile.state, 'published')
        self.profile.action_new_draft()
        code = self.profile.draft_code.replace('score = 0', 'score = -5')
        self.profile.draft_code = code
        self.assertEqual(self.profile.state, 'draft')
        self.assertEqual(self.profile.active_release_id, first)
        second = self._publish()
        self.assertNotEqual(first, second)
        self.assertEqual(second.version_id.code_text, code)
        self.profile.action_rollback()
        self.assertEqual(self.profile.active_release_id, first)
        self.assertEqual(self.profile.event_ids[:1].event_type, 'rollback')

    def test_draft_change_requires_fresh_validation(self):
        self.profile.action_validate()
        self.profile.draft_code = self.profile.draft_code.replace('score = 0', 'score = -1')
        with self.assertRaises(UserError):
            self.profile.action_publish()

    def test_failed_trial_cannot_publish(self):
        self.profile.draft_code = 'result = []'
        with self.assertRaises(ValidationError):
            self.profile.action_validate()
        self.assertFalse(self.profile.active_release_id)
        self.assertFalse(self.profile.version_ids)

    def test_ai_draft_uses_same_workflow_and_never_auto_publishes(self):
        first = self._publish()
        result = self.profile.action_submit_draft(self.profile.draft_code, self.profile.draft_tests, 'AI changed explanation', first.id, 'cloud-session-1')
        self.assertEqual(result['state'], 'draft')
        self.assertEqual(self.profile.active_release_id, first)
        self.assertFalse(self.profile.validated_version_id)
        second = self._publish()
        self.assertEqual(second.version_id.source, 'ai')
        self.assertEqual(second.version_id.conversation_ref, 'cloud-session-1')

    def test_ai_stale_base_is_rejected(self):
        self._publish()
        with self.assertRaises(UserError):
            self.profile.action_submit_draft(self.profile.draft_code, self.profile.draft_tests, 'Stale AI request')

    def test_worker_cannot_submit_validate_publish_or_rollback(self):
        for method in ('action_load_example', 'action_validate', 'action_publish', 'action_rollback', 'action_new_draft'):
            with self.assertRaises(AccessError):
                getattr(self.profile.with_user(self.worker), method)()
        with self.assertRaises(AccessError):
            self.profile.with_user(self.worker).action_submit_draft(self.profile.draft_code, self.profile.draft_tests, 'No access')

    def test_workflow_fields_cannot_be_forged(self):
        release = self._publish()
        with self.assertRaises(AccessError):
            self.profile.write({'active_release_id': False})
        with self.assertRaises(AccessError):
            self.profile.with_context(blue_asset_token='rpc').write({'validated_version_id': release.version_id.id})
        with self.assertRaises(AccessError):
            self.env['blue.config.release'].create({'name': 'Forged'})
        with self.assertRaises(AccessError):
            release.write({'snapshot': '{}'})
        with self.assertRaises(AccessError):
            release.version_id.write({'code_text': 'result = []'})
        with self.assertRaises(AccessError), self.cr.savepoint():
            release.unlink()

    def test_same_lot_prefers_stock_over_empty_location(self):
        self._stock(self.locations[1], 3)
        release = self._publish()
        line = self._line()
        self.assertEqual(line.location_dest_id, self.locations[1])
        self.assertEqual(line.picking_id.blue_putaway_release_id, release)
        self.assertEqual(line.blue_putaway_release_id, release)
        self.assertIn('同批次', line.blue_putaway_reason)
        self.assertTrue(line.picking_id.blue_putaway_application_ids)

    def test_same_lot_matches_product_and_lot(self):
        self._stock(self.locations[0], 3, lot=self.lots[1])
        self._stock(self.locations[2], 3)
        self._publish()
        line = self._line()
        self.assertEqual(line.location_dest_id, self.locations[2])

    def test_empty_location_fallback(self):
        self._stock(self.locations[0], 3, lot=self.lots[1])
        self._publish()
        self.assertEqual(self._line().location_dest_id, self.locations[1])

    def test_pending_same_lot_is_visible_to_next_picking(self):
        self._stock(self.locations[2], 2)
        self._publish()
        first = self._line()
        self._stock(self.locations[2], -2)
        second = self._line()
        self.assertEqual(second.location_dest_id, first.location_dest_id)

    def test_same_picking_prefers_its_previous_pending_location(self):
        self.profile.template_id = self.env.ref('blue_stock_putaway.blue_scene_template_same_picking')
        self.profile.action_load_example()
        self._stock(self.locations[0], 1, lot=self.lots[1])
        self._publish()
        first = self._line(lot=self.lots[1])
        self.assertEqual(first.location_dest_id, self.locations[1])
        self._stock(self.locations[0], -1, lot=self.lots[1])
        second = self._line(lot=self.lots[0], picking=first.picking_id)
        self.assertEqual(second.location_dest_id, self.locations[1])
        self.assertIn('同入库单', second.blue_putaway_reason)

    def test_cancelled_picking_releases_pending_preference_and_capacity(self):
        self._capacity(2)
        self._publish()
        first = self._line()
        first.picking_id.action_cancel()
        second = self._line()
        self.assertEqual(second.location_dest_id, self.locations[0])

    def test_capacity_counts_other_pending_receipts(self):
        self._capacity(2)
        self._publish()
        first = self._line()
        second = self._line()
        self.assertEqual(first.location_dest_id, self.locations[0])
        self.assertEqual(second.location_dest_id, self.locations[1])

    def test_partial_capacity_splits_without_changing_total_quantity(self):
        self._capacity(3)
        self._stock(self.locations[1], 2)
        self._publish()
        line = self._line(qty=4)
        lines = line.picking_id.move_line_ids
        self.assertEqual(sum(lines.mapped('quantity_product_uom')), 4)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines.filtered(lambda item: item.location_dest_id == self.locations[1]).quantity, 1)
        self.assertEqual(lines.filtered(lambda item: item.location_dest_id == self.locations[0]).quantity, 3)

    def test_frozen_and_no_entry_locations_cannot_be_chosen(self):
        self._stock(self.locations[0], 2)
        self._stock(self.locations[1], 2)
        self.locations[0].is_locking = True
        self.locations[1].block_stock_entrance = True
        self._publish()
        self.assertEqual(self._line().location_dest_id, self.locations[2])

    def test_no_candidate_fails_atomically(self):
        self.root.is_locking = True
        self._publish()
        count = self.env['stock.move.line'].search_count([('product_id', '=', self.product.id)])
        with self.assertRaises(UserError), self.cr.savepoint():
            self._line()
        self.assertEqual(self.env['stock.move.line'].search_count([('product_id', '=', self.product.id)]), count)
        self.assertFalse(self.env['blue.putaway.application'].search([('release_id', '=', self.profile.active_release_id.id)]))

    def test_picking_keeps_version_after_new_release_and_rollback(self):
        first = self._publish()
        line = self._line()
        self.profile.action_new_draft()
        self.profile.draft_code = self.profile.draft_code.replace('score = 0', 'score = -1')
        second = self._publish()
        line.picking_id.action_blue_apply_putaway()
        self.assertEqual(line.blue_putaway_release_id, first)
        fresh = self._line()
        self.assertEqual(fresh.blue_putaway_release_id, second)
        self.profile.action_rollback()
        fresh.picking_id.action_blue_apply_putaway()
        self.assertEqual(fresh.blue_putaway_release_id, second)
        self.assertEqual(self._line().blue_putaway_release_id, first)

    def test_real_preview_has_no_inventory_or_destination_effect(self):
        line = self._line()
        before = (line.location_dest_id, line.picking_id.blue_putaway_release_id)
        wizard = self.env['blue.putaway.preview'].create({'profile_id': self.profile.id, 'rule_id': self.native_rule.id, 'move_line_id': line.id})
        wizard.action_preview()
        self.assertTrue(json.loads(wizard.detail)['result'])
        self.assertEqual((line.location_dest_id, line.picking_id.blue_putaway_release_id), before)
        self.assertFalse(self.env['stock.quant'].search([('product_id', '=', self.product.id)]))

    def test_actual_receipt_runs_policy_and_preserves_stock_guards(self):
        self._capacity(3)
        self._stock(self.locations[1], 2)
        self._publish()
        line = self._line(qty=4)
        picking = line.picking_id
        picking.move_line_ids.picked = True
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        quants = self.env['stock.quant'].search([('product_id', '=', self.product.id), ('location_id', 'in', self.locations.ids)])
        self.assertEqual(sum(quants.mapped('quantity')), 6)
        self.assertEqual(len(picking.move_line_ids), 2)

    def test_full_location_at_validation_is_reallocated(self):
        self._capacity(2)
        self._publish()
        line = self._line()
        self._stock(self.locations[0], 2, lot=self.lots[1])
        line.picked = True
        line.picking_id.button_validate()
        self.assertEqual(line.location_dest_id, self.locations[1])
        self.assertEqual(line.picking_id.state, 'done')

    def test_strategy_scope_comes_only_from_native_rules(self):
        self._publish()
        self.assertNotIn('warehouse_id', self.profile._fields)
        self.assertNotIn('picking_type_id', self.profile._fields)
        self.assertNotIn('root_location_id', self.profile._fields)
        self.assertEqual(self.native_rule.blue_profile_id, self.profile)

    def test_same_picking_done_history_only_when_stock_remains(self):
        self.profile.template_id = self.env.ref('blue_stock_putaway.blue_scene_template_same_picking')
        self.profile.action_load_example()
        first = self._line()
        first.location_dest_id = self.locations[2]
        first.picked = True
        first.picking_id.button_validate()
        other = self._line()
        trial_line = self.env['stock.move.line'].new({'move_id': other.move_id.id, 'picking_id': first.picking_id.id,
            'product_id': self.product.id, 'uom_id': self.product.uom_id.id, 'quantity': 2,
            'company_id': self.env.company.id, 'location_id': other.location_id.id,
            'location_dest_id': self.root.id, 'lot_id': self.lots[0].id})
        payload = self.profile._prepare_putaway_payload(trial_line)
        selected = next(item for item in payload['candidates'] if item['location_id'] == self.locations[2].id)
        self.assertTrue(selected['same_picking'])
        self._stock(self.locations[2], -2)
        payload = self.profile._prepare_putaway_payload(trial_line)
        selected = next(item for item in payload['candidates'] if item['location_id'] == self.locations[2].id)
        self.assertFalse(selected['same_picking'])

    def test_execution_fields_cannot_be_forged(self):
        release = self._publish()
        line = self._line()
        with self.assertRaises(AccessError):
            line.write({'blue_putaway_reason': 'Forged'})
        with self.assertRaises(AccessError):
            line.picking_id.write({'blue_putaway_release_id': False})
        with self.assertRaises(AccessError):
            self.env['blue.putaway.application'].with_context(blue_putaway_token='rpc').create({'company_id': self.env.company.id})
        with self.assertRaises(AccessError):
            self.env['stock.picking'].create({'picking_type_id': self.warehouse.in_type_id.id, 'blue_putaway_release_id': release.id})

    def test_cross_company_profile_access_is_denied(self):
        company = self.env['res.company'].create({'name': 'Blue private policy company'})
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
        profile = self.env['blue.config.profile'].with_company(company).create({'name': 'Other company policy', 'company_id': company.id,
            'template_id': self.template.id})
        with self.assertRaises(AccessError):
            profile.with_user(self.manager).action_load_example()

    def test_interpreter_rejects_unsafe_or_unbounded_syntax(self):
        payload = json.loads(self.template.test_cases)[0]['input']
        unsafe = ['import os', 'result = env["stock.quant"]', 'while True:\n    result = []',
                  'result = [candidate for candidate in candidates]', 'result = request.__class__',
                  'result = []\nresult.append(__import__("os"))', 'result = []\nfor candidate in candidates:\n    for candidate in candidates:\n        result = []',
                  'result = []\nx = "a" * 1000000000', 'result = []\nx = 2 ** 9999999']
        for code in unsafe:
            with self.subTest(code=code), self.assertRaises(PolicyError):
                run_policy(code, payload)

    def test_interpreter_result_cannot_escape_candidate_set(self):
        payload = json.loads(self.template.test_cases)[0]['input']
        for code in ['result = [{"location_id": 99, "score": 0, "reason": "outside"}]',
                     'result = [{"location_id": 1, "score": 0, "reason": "one"}, {"location_id": 1, "score": 1, "reason": "duplicate"}]',
                     'result = [{"location_id": True, "score": 0, "reason": "bool"}]']:
            with self.subTest(code=code), self.assertRaises(PolicyError):
                run_policy(code, payload)

    def test_ai_can_change_actual_selection_and_rollback_restores_behavior(self):
        self._stock(self.locations[1], 2)
        first = self._publish()
        old_line = self._line()
        code = '''result = []
for candidate in candidates:
    score = 10
    reason = "AI: other permitted location"
    if candidate["empty"]:
        score = 0
        reason = "AI: empty location first"
    result.append({"location_id": candidate["location_id"], "score": score, "reason": reason})
'''
        cases = json.loads(self.profile.draft_tests)
        cases[0]['expected_order'] = [1, 2, 3]
        self.profile.action_submit_draft(code, json.dumps(cases), 'Empty location before consolidation', first.id, 'ai-trial')
        second = self._publish()
        fresh = self._line(lot=self.lots[1])
        self.assertEqual(fresh.location_dest_id, self.locations[0])
        self.assertEqual(fresh.blue_putaway_release_id, second)
        old_line.picking_id.action_blue_apply_putaway()
        self.assertEqual(old_line.location_dest_id, self.locations[1])
        self.profile.action_rollback()
        restored = self._line()
        self.assertEqual(restored.location_dest_id, self.locations[1])
        self.assertEqual(restored.blue_putaway_release_id, first)

    def test_inventory_worker_can_execute_an_approved_policy(self):
        self._publish()
        line = self._line()
        line.picking_id.with_user(self.worker).action_blue_apply_putaway()
        self.assertEqual(line.blue_putaway_release_id, self.profile.active_release_id)

    def test_manager_can_edit_validate_and_publish(self):
        profile = self.profile.with_user(self.manager)
        profile.action_load_example()
        profile.action_validate()
        profile.action_publish()
        self.assertTrue(profile.active_release_id)

    def test_quantity_edit_rechecks_capacity_without_double_counting(self):
        self._capacity(3)
        self._publish()
        line = self._line(qty=2)
        line.quantity = 4
        self.assertEqual(sum(line.picking_id.move_line_ids.mapped('quantity_product_uom')), 4)
        self.assertEqual(len(line.picking_id.move_line_ids), 2)

    def test_package_requires_a_declared_type_before_execution(self):
        self._publish()
        line = self._line()
        package = self.env['stock.package'].create({})
        line.result_package_id = package
        line.picked = True
        with self.assertRaises(UserError), self.cr.savepoint():
            line.picking_id.button_validate()
        self.assertNotEqual(line.picking_id.state, 'done')

    def test_no_active_profile_keeps_native_behavior(self):
        line = self._line()
        self.assertEqual(line.location_dest_id, self.locations[0])
        self.assertFalse(line.picking_id.blue_putaway_release_id)

    def test_split_preserves_quantity_in_a_larger_move_unit(self):
        self._capacity(4)
        unit = self.env['uom.uom'].create({'name': 'Blue six units', 'relative_uom_id': self.product.uom_id.id, 'relative_factor': 6})
        self._publish()
        line = self._line(qty=1, uom=unit)
        lines = line.picking_id.move_line_ids
        self.assertAlmostEqual(sum(lines.mapped('quantity')), 1)
        self.assertAlmostEqual(sum(lines.mapped('quantity_product_uom')), 6)
        self.assertEqual(len(lines), 2)
        self.assertAlmostEqual(lines.filtered(lambda item: item.location_dest_id == self.locations[0]).quantity, 0.66)

    def test_unrepresentable_remaining_space_is_skipped(self):
        self._capacity(4)
        self._stock(self.locations[0], 3.96)
        unit = self.env['uom.uom'].create({'name': 'Blue precision six units', 'relative_uom_id': self.product.uom_id.id, 'relative_factor': 6})
        self._publish()
        line = self._line(qty=0.01, uom=unit)
        self.assertEqual(line.location_dest_id, self.locations[1])
        self.assertAlmostEqual(line.quantity_product_uom, 0.06)

    def test_same_picking_example_full_edit_publish_execute_rollback(self):
        self.profile.template_id = self.env.ref('blue_stock_putaway.blue_scene_template_same_picking')
        self.profile.action_load_example()
        self._stock(self.locations[0], 1)
        first_release = self._publish()
        first_line = self._line()
        second_line = self._line(lot=self.lots[1], picking=first_line.picking_id)
        self.assertEqual(first_line.location_dest_id, self.locations[1])
        self.assertEqual(second_line.location_dest_id, first_line.location_dest_id)
        first_line.picking_id.move_line_ids.picked = True
        first_line.picking_id.button_validate()
        self.assertEqual(first_line.picking_id.state, 'done')
        self.profile.action_new_draft()
        self.profile.draft_code = self.profile.draft_code.replace('score = 0', 'score = -5')
        second_release = self._publish()
        self.assertNotEqual(second_release, first_release)
        new_line = self._line()
        self.assertEqual(new_line.blue_putaway_release_id, second_release)
        self.profile.action_rollback()
        self.assertEqual(self.profile.active_release_id, first_release)
        self.assertEqual(self._line().blue_putaway_release_id, first_release)
        self.assertEqual(first_line.picking_id.blue_putaway_release_id, first_release)

    def _pallet_category(self, count=10, mixing='mixed'):
        self.pallet_type = self.env['stock.package.type'].create({'name': 'Blue pallet', 'package_use': 'reusable'})
        category = self.env['stock.storage.category'].create({'name': 'Blue native pallet category', 'company_id': self.env.company.id,
            'max_weight': 10000, 'allow_new_product': mixing,
            'capacity_ids': [Command.create({'package_type_id': self.pallet_type.id, 'quantity': count})]})
        self.locations.storage_category_id = category
        self.native_rule.storage_category_id = category
        return category

    def _pallet(self, location=None, entries=None):
        package = self.env['stock.package'].create({'package_type_id': self.pallet_type.id})
        if location:
            for product, lot, qty in entries or [(self.product, self.lots[0], 1)]:
                self.env['stock.quant']._update_available_quantity(product, location, qty, lot_id=lot, package_id=package)
        return package

    def _packed_lines(self, entries=None, package=None, picking=None):
        package = package or self._pallet()
        # Build a complete draft unit without prematurely allocating its first
        # product. This capability is test-only server setup, not an RPC context.
        internal = self.env(context=dict(self.env.context, blue_putaway_token=POLICY_TOKEN))
        picking = picking or internal['stock.picking'].create({'picking_type_id': self.warehouse.in_type_id.id,
            'location_id': self.env.ref('stock.stock_location_suppliers').id, 'location_dest_id': self.root.id})
        line_ids = []
        for product, lot, qty in entries or [(self.product, self.lots[0], 1)]:
            move = internal['stock.move'].create({'product_id': product.id, 'uom_id': product.uom_id.id, 'product_uom_qty': qty,
                'picking_id': picking.id, 'location_id': picking.location_id.id, 'location_dest_id': self.root.id})
            move._action_confirm(merge=False)
            line = move.move_line_ids[:1]
            values = {'move_id': move.id, 'picking_id': picking.id, 'product_id': product.id, 'uom_id': product.uom_id.id,
                'quantity': qty, 'lot_id': lot.id if lot else False, 'result_package_id': package.id,
                'location_id': picking.location_id.id, 'location_dest_id': self.root.id}
            if line:
                line.write(values)
            else:
                line = internal['stock.move.line'].create(values)
            line_ids.extend(line.ids)
        return self.env['stock.move.line'].browse(line_ids), package

    def _strict_batch(self):
        self.profile.template_id = self.env.ref('blue_stock_putaway.blue_scene_template_same_batch_name')
        self.profile.action_load_example()
        return self._publish()

    def _other_product_same_batch(self):
        product = self.env['product.product'].create({'name': 'Blue pallet second SKU', 'is_storable': True, 'tracking': 'lot'})
        lot = self.env['stock.lot'].create({'name': self.lots[0].name, 'product_id': product.id, 'company_id': self.env.company.id})
        return product, lot

    def test_native_fixed_destination_cannot_be_overridden_by_code(self):
        self.native_rule.write({'sublocation': 'no', 'location_out_id': self.locations[0].id, 'storage_category_id': False})
        self._stock(self.locations[1], 2)
        self._publish()
        self.assertEqual(self._line().location_dest_id, self.locations[0])

    def test_native_storage_category_excludes_an_attractive_other_bin(self):
        other_category = self.env['stock.storage.category'].create({'name': 'Not allowed by native rule', 'max_weight': 10000})
        self.locations[1].storage_category_id = other_category
        self._stock(self.locations[1], 2)
        self._publish()
        self.assertEqual(self._line().location_dest_id, self.locations[0])

    def test_native_rule_priority_precedes_supplementary_score(self):
        self.env['stock.putaway.rule'].create({'location_in_id': self.root.id, 'location_out_id': self.locations[0].id,
            'product_id': self.product.id, 'company_id': self.env.company.id, 'blue_profile_id': self.profile.id})
        self._stock(self.locations[1], 2)
        self._publish()
        self.assertEqual(self._line().location_dest_id, self.locations[0])

    def test_supplementary_rejection_allows_native_fallback_rule(self):
        self.env['stock.putaway.rule'].create({'location_in_id': self.root.id, 'location_out_id': self.locations[0].id,
            'product_id': self.product.id, 'company_id': self.env.company.id, 'blue_profile_id': self.profile.id})
        self._stock(self.locations[0], 1, lot=self.lots[1])
        self._stock(self.locations[1], 1)
        self._strict_batch()
        self.assertEqual(self._line().location_dest_id, self.locations[1])

    def test_no_native_rule_keeps_default_destination_scope(self):
        self.native_rule.unlink()
        self._stock(self.locations[1], 2)
        self._publish()
        line = self._line()
        self.assertEqual(line.location_dest_id, self.locations[0])
        self.assertFalse(line.blue_putaway_release_id)

    def test_pallet_tenth_slot_is_available_and_eleventh_is_rejected(self):
        self._pallet_category()
        for __ in range(9):
            self._pallet(self.locations[0])
        self.locations[1:].is_locking = True
        self._strict_batch()
        lines, __ = self._packed_lines()
        lines.picking_id.action_blue_apply_putaway()
        self.assertEqual(lines.location_dest_id, self.locations[0])
        others, __ = self._packed_lines()
        with self.assertRaises(UserError), self.cr.savepoint():
            others.picking_id.action_blue_apply_putaway()
        self.assertFalse(others.picking_id.blue_putaway_release_id)

    def test_pallet_capacity_counts_distinct_packages_not_product_rows(self):
        self._pallet_category()
        second, second_lot = self._other_product_same_batch()
        for __ in range(9):
            self._pallet(self.locations[0], [(self.product, self.lots[0], 1), (second, second_lot, 1)])
        self._strict_batch()
        lines, package = self._packed_lines([(self.product, self.lots[0], 1), (second, second_lot, 1)])
        lines.picking_id.action_blue_apply_putaway()
        self.assertEqual(lines.location_dest_id, self.locations[0])
        payload = self.profile._prepare_putaway_payload(lines[0])
        first = next(item for item in payload['candidates'] if item['location_id'] == self.locations[0].id)
        self.assertEqual(first['occupied_packages'], 9)
        self.assertEqual(first['package_capacity'], 10)
        self.assertEqual(payload['request']['package_count'], 1)
        self.assertEqual(payload['request']['product_ids'], lines.product_id.ids)
        self.assertEqual(lines.picking_id.blue_putaway_application_ids.package_id, package)
        self.assertEqual(lines.picking_id.blue_putaway_application_ids.quantity, 1)

    def test_cross_product_same_batch_name_is_allowed_and_actual_receipt_completes(self):
        self._pallet_category()
        second, second_lot = self._other_product_same_batch()
        self.assertNotEqual(second_lot, self.lots[0])
        self._pallet(self.locations[1], [(self.product, self.lots[0], 1)])
        self._strict_batch()
        lines, package = self._packed_lines([(self.product, self.lots[0], 2), (second, second_lot, 3)])
        lines.picking_id.action_blue_apply_putaway()
        self.assertEqual(lines.location_dest_id, self.locations[1])
        lines.picked = True
        lines.picking_id.button_validate()
        self.assertEqual(lines.picking_id.state, 'done')
        self.assertEqual(package.location_id, self.locations[1])
        self.assertEqual(len(package.quant_ids), 2)
        self.assertAlmostEqual(sum(package.quant_ids.mapped('quantity')), 5)

    def test_other_batch_and_unknown_batch_are_filtered(self):
        self._pallet_category()
        self._pallet(self.locations[0], [(self.product, self.lots[1], 1)])
        untracked = self.env['product.product'].create({'name': 'Unknown batch contents', 'is_storable': True})
        package = self._pallet()
        self.env['stock.quant']._update_available_quantity(untracked, self.locations[1], 1, package_id=package)
        self._strict_batch()
        lines, __ = self._packed_lines()
        lines.picking_id.action_blue_apply_putaway()
        self.assertEqual(lines.location_dest_id, self.locations[2])

    def test_mixed_batch_names_in_one_pallet_are_rejected(self):
        self._pallet_category()
        self._strict_batch()
        lines, __ = self._packed_lines([(self.product, self.lots[0], 1), (self.product, self.lots[1], 1)])
        with self.assertRaises(UserError), self.cr.savepoint():
            lines.picking_id.action_blue_apply_putaway()
        self.assertFalse(lines.picking_id.blue_putaway_release_id)
        self.assertEqual(sum(lines.mapped('quantity')), 2)

    def test_mixed_products_cannot_bypass_native_same_product_setting(self):
        self._pallet_category(mixing='same')
        second, second_lot = self._other_product_same_batch()
        self._strict_batch()
        lines, __ = self._packed_lines([(self.product, self.lots[0], 1), (second, second_lot, 1)])
        with self.assertRaises(UserError), self.cr.savepoint():
            lines.picking_id.action_blue_apply_putaway()

    def test_whole_pallet_respects_product_capacity_too(self):
        category = self._pallet_category()
        category.capacity_ids = [Command.create({'product_id': self.product.id, 'quantity': 1})]
        self._strict_batch()
        lines, __ = self._packed_lines([(self.product, self.lots[0], 2)])
        with self.assertRaises(UserError), self.cr.savepoint():
            lines.picking_id.action_blue_apply_putaway()
        self.assertEqual(len(lines.picking_id.move_line_ids), 1)
        self.assertEqual(lines.quantity, 2)

    def test_whole_pallet_weight_uses_all_products(self):
        category = self._pallet_category()
        category.max_weight = 3
        self.product.weight = 2
        second, second_lot = self._other_product_same_batch()
        second.weight = 2
        self._strict_batch()
        lines, __ = self._packed_lines([(self.product, self.lots[0], 1), (second, second_lot, 1)])
        with self.assertRaises(UserError), self.cr.savepoint():
            lines.picking_id.action_blue_apply_putaway()

    def test_pallet_final_validation_rechecks_changed_capacity(self):
        self._pallet_category(count=1)
        self._strict_batch()
        lines, __ = self._packed_lines()
        lines.picking_id.action_blue_apply_putaway()
        self.assertEqual(lines.location_dest_id, self.locations[0])
        self._pallet(self.locations[0])
        lines.picked = True
        lines.picking_id.button_validate()
        self.assertEqual(lines.picking_id.state, 'done')
        self.assertEqual(lines.location_dest_id, self.locations[1])

    def test_same_pallet_other_pending_picking_does_not_consume_two_slots(self):
        self._pallet_category(count=1)
        self._strict_batch()
        first, package = self._packed_lines()
        first.picking_id.action_blue_apply_putaway()
        second, __ = self._packed_lines(package=package)
        second.picking_id.action_blue_apply_putaway()
        self.assertEqual(second.location_dest_id, first.location_dest_id)

    def test_native_package_type_rule_selects_its_configured_location(self):
        self._pallet_category()
        other_type = self.env['stock.package.type'].create({'name': 'Other native type'})
        self.native_rule.write({'sublocation': 'no', 'location_out_id': self.locations[0].id, 'storage_category_id': False,
                                'package_type_ids': [Command.set(other_type.ids)]})
        self.env['stock.putaway.rule'].create({'location_in_id': self.root.id, 'location_out_id': self.locations[1].id,
            'package_type_ids': [Command.set(self.pallet_type.ids)], 'company_id': self.env.company.id, 'blue_profile_id': self.profile.id})
        self._pallet(self.locations[0])
        self._strict_batch()
        lines, __ = self._packed_lines()
        lines.picking_id.action_blue_apply_putaway()
        self.assertEqual(lines.location_dest_id, self.locations[1])

    def test_different_native_fixed_scopes_reject_one_mixed_pallet(self):
        self._pallet_category()
        self.native_rule.unlink()
        second, second_lot = self._other_product_same_batch()
        self.env['stock.putaway.rule'].create([
            {'location_in_id': self.root.id, 'location_out_id': location.id, 'product_id': product.id, 'company_id': self.env.company.id, 'blue_profile_id': self.profile.id}
            for product, location in [(self.product, self.locations[0]), (second, self.locations[1])]])
        self._strict_batch()
        lines, __ = self._packed_lines([(self.product, self.lots[0], 1), (second, second_lot, 1)])
        with self.assertRaises(UserError), self.cr.savepoint():
            lines.picking_id.action_blue_apply_putaway()

    def test_cancellation_releases_pallet_pending_capacity(self):
        self._pallet_category(count=1)
        self._strict_batch()
        first, __ = self._packed_lines()
        first.picking_id.action_blue_apply_putaway()
        first.picking_id.action_cancel()
        second, __ = self._packed_lines()
        second.picking_id.action_blue_apply_putaway()
        self.assertEqual(second.location_dest_id, self.locations[0])

    def test_inner_boxes_share_one_outer_pallet_slot(self):
        self._pallet_category(count=1)
        self._strict_batch()
        pallet = self._pallet()
        boxes = self.env['stock.package'].create([{'package_dest_id': pallet.id}, {'package_dest_id': pallet.id}])
        first, __ = self._packed_lines(package=boxes[0])
        second, __ = self._packed_lines(package=boxes[1], picking=first.picking_id)
        first.picking_id.action_blue_apply_putaway()
        self.assertEqual((first | second).location_dest_id, self.locations[0])
        other, __ = self._packed_lines()
        other.picking_id.action_blue_apply_putaway()
        self.assertEqual(other.location_dest_id, self.locations[1])

    def test_physical_inner_box_inventory_counts_outer_pallet(self):
        self._pallet_category(count=1)
        pallet = self._pallet()
        box = self.env['stock.package'].create({'parent_package_id': pallet.id})
        self.env['stock.quant']._update_available_quantity(self.product, self.locations[0], 1, lot_id=self.lots[0], package_id=box)
        self._strict_batch()
        lines, __ = self._packed_lines()
        lines.picking_id.action_blue_apply_putaway()
        self.assertEqual(lines.location_dest_id, self.locations[1])

    def test_capacity_guard_rejects_a_script_returning_a_full_bin(self):
        self._pallet_category(count=1)
        self._pallet(self.locations[0])
        self._strict_batch()
        lines, __ = self._packed_lines()
        payload = self.profile._prepare_putaway_payload(lines[0])
        self.assertNotIn(self.locations[0].id, [item['location_id'] for item in payload['candidates']])
        malicious = 'result = [{"location_id": %s, "score": 0, "reason": "force full bin"}]' % self.locations[0].id
        with self.assertRaises(ValidationError):
            self.env['blue.extension.contract']._run(malicious, payload)

    def test_native_last_used_rule_remains_a_fixed_scope(self):
        previous = self._line()
        previous.location_dest_id = self.locations[1]
        previous.picked = True
        previous.picking_id.button_validate()
        self.native_rule.write({'sublocation': 'last_used', 'location_out_id': self.root.id})
        self._stock(self.locations[2], 2)
        self._publish()
        self.assertEqual(self._line().location_dest_id, self.locations[1])

    def test_revision_counter_is_not_user_writable(self):
        with self.assertRaises(AccessError):
            self.warehouse.with_user(self.worker).write({'blue_putaway_revision': 999})
        before = self.warehouse.blue_putaway_revision
        self._publish()
        self._line()
        self.assertGreater(self.warehouse.blue_putaway_revision, before)

    def test_batch_name_entry_preserves_native_lot_creation_for_mixed_products(self):
        self._pallet_category()
        second, __ = self._other_product_same_batch()
        self.warehouse.in_type_id.use_create_lots = True
        self._strict_batch()
        lines, package = self._packed_lines([(self.product, False, 2), (second, False, 3)])
        lines.lot_name = 'NEW-CROSS-PRODUCT-BATCH'
        self.assertFalse(lines.lot_id)
        self.assertEqual(lines.location_dest_id, self.locations[0])
        lines.picked = True
        lines.picking_id.button_validate()
        self.assertEqual(lines.picking_id.state, 'done')
        self.assertEqual(len(lines.lot_id), 2)
        self.assertEqual(set(lines.lot_id.mapped('name')), {'NEW-CROSS-PRODUCT-BATCH'})
        self.assertEqual(package.location_id, self.locations[0])

    def test_strict_batch_cannot_enable_native_lot_creation_when_disabled(self):
        self._pallet_category()
        self.warehouse.in_type_id.use_create_lots = False
        self._strict_batch()
        lines, __ = self._packed_lines([(self.product, False, 1)])
        lines.lot_name = 'NOT-ALLOWED-TO-CREATE'
        self.assertFalse(lines.picking_id.blue_putaway_release_id)
        lines.picked = True
        with self.assertRaises(UserError), self.cr.savepoint():
            lines.picking_id.button_validate()

    def test_preview_reports_one_pallet_and_the_ten_pallet_limit(self):
        self._pallet_category()
        for __ in range(9):
            self._pallet(self.locations[0])
        self._strict_batch()
        lines, __ = self._packed_lines()
        wizard = self.env['blue.putaway.preview'].create({'profile_id': self.profile.id, 'rule_id': self.native_rule.id, 'move_line_id': lines[0].id})
        wizard.action_preview()
        self.assertIn('10 / 10', wizard.result)
        self.assertTrue(json.loads(wizard.detail)['result'])
        self.assertFalse(lines.picking_id.blue_putaway_release_id)

    def test_internal_pallet_transfer_keeps_source_package_and_quantities(self):
        self._pallet_category()
        self._strict_batch()
        package = self._pallet(self.warehouse.lot_stock_id)
        picking = self.env['stock.picking'].create({'picking_type_id': self.warehouse.int_type_id.id,
            'location_id': self.warehouse.lot_stock_id.id, 'location_dest_id': self.root.id})
        move = self.env['stock.move'].create({'product_id': self.product.id, 'uom_id': self.product.uom_id.id, 'product_uom_qty': 1,
            'picking_id': picking.id, 'location_id': self.warehouse.lot_stock_id.id, 'location_dest_id': self.root.id})
        move._action_confirm(merge=False)
        if not move.move_line_ids:
            picking.action_assign()
        line = move.move_line_ids[:1]
        line.write({'lot_id': self.lots[0].id, 'package_id': package.id, 'result_package_id': package.id, 'quantity': 1})
        line.picked = True
        picking.button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertEqual(package.location_id, self.locations[0])
        self.assertEqual(sum(package.quant_ids.mapped('quantity')), 1)

    def test_category_empty_also_excludes_other_pending_pallets(self):
        self._pallet_category(mixing='empty')
        self._strict_batch()
        first, __ = self._packed_lines()
        first.picking_id.action_blue_apply_putaway()
        second, __ = self._packed_lines()
        second.picking_id.action_blue_apply_putaway()
        self.assertEqual(first.location_dest_id, self.locations[0])
        self.assertEqual(second.location_dest_id, self.locations[1])

    def test_batch_name_comparison_is_exact_and_case_sensitive(self):
        self._pallet_category()
        second, __ = self._other_product_same_batch()
        lower = self.env['stock.lot'].create({'name': self.lots[0].name.lower(), 'product_id': second.id, 'company_id': self.env.company.id})
        self._pallet(self.locations[0], [(second, lower, 1)])
        self._strict_batch()
        lines, __ = self._packed_lines()
        lines.picking_id.action_blue_apply_putaway()
        self.assertEqual(lines.location_dest_id, self.locations[1])

    def test_frozen_pallet_bins_stay_outside_supplementary_code(self):
        self._pallet_category()
        self._pallet(self.locations[0])
        self.locations[0].is_locking = True
        self.locations[1].block_stock_entrance = True
        self._strict_batch()
        lines, __ = self._packed_lines()
        lines.picking_id.action_blue_apply_putaway()
        self.assertEqual(lines.location_dest_id, self.locations[2])

    def test_private_revision_counter_wraps_without_integer_overflow(self):
        self.env.cr.execute('UPDATE stock_warehouse SET blue_putaway_revision = %s WHERE id = %s', [2000000000, self.warehouse.id])
        self.warehouse.invalidate_recordset(['blue_putaway_revision'])
        self.warehouse._blue_lock_putaway()
        self.assertEqual(self.warehouse.blue_putaway_revision, 0)

    def test_untracked_inventory_products_cannot_evade_pallet_accounting(self):
        self._pallet_category()
        self.profile.template_id = self.env.ref('blue_stock_putaway.blue_scene_template_same_picking')
        self.profile.action_load_example()
        self._publish()
        untracked = self.env['product.product'].create({'name': 'No inventory ledger', 'is_storable': False})
        lines, __ = self._packed_lines([(untracked, False, 1)])
        lines.picked = True
        with self.assertRaises(UserError), self.cr.savepoint():
            lines.picking_id.button_validate()
        self.assertNotEqual(lines.picking_id.state, 'done')

    def test_non_inventory_content_is_not_silently_ignored_inside_a_pallet(self):
        self._pallet_category()
        self.profile.template_id = self.env.ref('blue_stock_putaway.blue_scene_template_same_picking')
        self.profile.action_load_example()
        self._publish()
        untracked = self.env['product.product'].create({'name': 'Unrecorded pallet content', 'is_storable': False})
        lines, __ = self._packed_lines([(self.product, self.lots[0], 1), (untracked, False, 1)])
        self.assertEqual(len(lines[0]._blue_allocation_unit()[0]), 2)
        lines.picked = True
        with self.assertRaises(UserError), self.cr.savepoint():
            lines.picking_id.button_validate()
        self.assertNotEqual(lines.picking_id.state, 'done')

    def test_one_scene_is_reusable_by_rules_in_two_warehouses(self):
        self._publish()
        other = self.env['stock.warehouse'].create({'name': 'Rule binding second warehouse', 'code': 'BRUL', 'company_id': self.env.company.id})
        destination = self.env['stock.location'].create({'name': 'Other native fixed bin', 'usage': 'internal', 'company_id': self.env.company.id,
            'location_id': other.lot_stock_id.id})
        rule = self.env['stock.putaway.rule'].create({'location_in_id': other.lot_stock_id.id, 'location_out_id': destination.id,
            'company_id': self.env.company.id, 'blue_profile_id': self.profile.id})
        picking = self.env['stock.picking'].create({'picking_type_id': other.in_type_id.id,
            'location_id': self.env.ref('stock.stock_location_suppliers').id, 'location_dest_id': other.lot_stock_id.id})
        move = self.env['stock.move'].create({'product_id': self.product.id, 'uom_id': self.product.uom_id.id, 'product_uom_qty': 1,
            'picking_id': picking.id, 'location_id': picking.location_id.id, 'location_dest_id': picking.location_dest_id.id})
        move._action_confirm(merge=False)
        move.move_line_ids.write({'lot_id': self.lots[0].id})
        self.assertEqual(move.move_line_ids.location_dest_id, destination)
        self.assertEqual(picking.blue_putaway_binding_ids.rule_id, rule)
        self.assertEqual(picking.blue_putaway_binding_ids.profile_id, self.profile)
        self.assertIn(self.native_rule, self.profile.putaway_rule_ids)
        self.assertIn(rule, self.profile.putaway_rule_ids)

    def test_two_scenes_in_one_picking_keep_separate_rule_versions(self):
        first_release = self._publish()
        second_product, second_lot = self._other_product_same_batch()
        second_profile = self.env['blue.config.profile'].create({'name': 'Second rule scene', 'company_id': self.env.company.id,
            'template_id': self.env.ref('blue_stock_putaway.blue_scene_template_same_picking').id})
        second_profile.action_load_example()
        second_profile.action_validate()
        second_profile.action_publish()
        second_rule = self.env['stock.putaway.rule'].create({'location_in_id': self.root.id, 'location_out_id': self.locations[1].id,
            'product_id': second_product.id, 'company_id': self.env.company.id, 'blue_profile_id': second_profile.id})
        first = self._line()
        second = self._line(product=second_product, lot=second_lot, picking=first.picking_id)
        self.assertEqual(first.location_dest_id, self.locations[0])
        self.assertEqual(second.location_dest_id, self.locations[1])
        self.assertEqual(first.blue_putaway_release_id, first_release)
        self.assertEqual(second.blue_putaway_release_id, second_profile.active_release_id)
        binding = first.picking_id.blue_putaway_binding_ids.filtered(lambda item: item.rule_id == second_rule)
        self.assertEqual(binding.release_id, second_profile.active_release_id)

    def test_changing_rule_scene_does_not_replace_a_started_jobs_version(self):
        first_release = self._publish()
        line = self._line()
        replacement = self.env['blue.config.profile'].create({'name': 'Replacement scene', 'company_id': self.env.company.id, 'template_id': self.template.id})
        replacement.action_load_example()
        replacement.action_validate()
        replacement.action_publish()
        self.native_rule.blue_profile_id = replacement
        line.picking_id.action_blue_apply_putaway()
        self.assertEqual(line.blue_putaway_release_id, first_release)
        self.assertEqual(self._line().blue_putaway_release_id, replacement.active_release_id)

    def test_unbound_specific_rule_uses_native_logic_without_generic_scene_override(self):
        self._stock(self.locations[1], 2)
        self._publish()
        rule = self.env['stock.putaway.rule'].create({'location_in_id': self.root.id, 'location_out_id': self.locations[0].id,
            'product_id': self.product.id, 'company_id': self.env.company.id})
        line = self._line()
        self.assertEqual(line.location_dest_id, self.locations[0])
        binding = line.picking_id.blue_putaway_binding_ids.filtered(lambda item: item.rule_id == rule)
        self.assertFalse(binding.release_id)

    def test_binding_a_scene_later_does_not_enable_it_on_an_already_started_job(self):
        self.native_rule.blue_profile_id = False
        self._stock(self.locations[1], 2)
        old = self._line()
        self._publish()
        self.native_rule.blue_profile_id = self.profile
        old.picking_id.action_blue_apply_putaway()
        self.assertFalse(old.blue_putaway_release_id)
        self.assertFalse(old.picking_id.blue_putaway_binding_ids.release_id)
        fresh = self._line()
        self.assertEqual(fresh.location_dest_id, self.locations[1])
        self.assertEqual(fresh.blue_putaway_release_id, self.profile.active_release_id)

    def test_rule_binding_rejects_another_companys_scene(self):
        company = self.env['res.company'].create({'name': 'Rule binding private company'})
        private = self.env['blue.config.profile'].with_company(company).create({'name': 'Private scene', 'company_id': company.id, 'template_id': self.template.id})
        with self.assertRaises(UserError), self.cr.savepoint():
            self.native_rule.blue_profile_id = private

    def test_rule_version_selection_cannot_be_forged(self):
        self._publish()
        line = self._line()
        binding = line.picking_id.blue_putaway_binding_ids
        with self.assertRaises(AccessError):
            binding.write({'release_id': False})
        with self.assertRaises(AccessError):
            line.picking_id.write({'blue_putaway_binding_ids': [Command.clear()]})
        with self.assertRaises(AccessError):
            self.env['blue.putaway.binding'].with_context(blue_putaway_token='rpc').create({'rule_key': self.native_rule.id})

    def test_preview_requires_a_rule_bound_to_the_selected_scene(self):
        other = self.env['blue.config.profile'].create({'name': 'Unrelated preview scene', 'company_id': self.env.company.id, 'template_id': self.template.id})
        other.action_load_example()
        line = self._line()
        wizard = self.env['blue.putaway.preview'].create({'profile_id': other.id, 'rule_id': self.native_rule.id, 'move_line_id': line.id})
        with self.assertRaises(UserError):
            wizard.action_preview()
