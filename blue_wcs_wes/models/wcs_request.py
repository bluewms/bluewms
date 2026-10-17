from odoo import models
from odoo.exceptions import UserError


class WcsRequest(models.Model):
    _inherit = 'wcs.request'

    def _payload(self):
        self.ensure_one()
        device = self.equipment_id
        if device.adapter_code != 'wes':
            return super()._payload()
        if self.role != 'goods':
            raise UserError(self.env._('WES VZF supports goods tasks; route empty carriers through an appropriate device.'))
        if not device.wes_warehouse_code or not device.wes_room_code or not device.wes_owner_code:
            raise UserError(self.env._('Configure WES warehouse, room and owner codes.'))
        direction = self.picking_type_id.wcs_type if 'wcs_type' in self.picking_type_id._fields and self.picking_type_id.wcs_type else device.wes_direction
        payload = {'whCode': device.wes_warehouse_code, 'whRoomCode': device.wes_room_code,
                   'ownerCode': device.wes_owner_code, 'carBillCode': self.name}
        items = []
        for row in self.plan_id.line_ids:
            if not row.product_id.default_code or not row.package_id:
                raise UserError(self.env._('WES goods need product and package codes.'))
            item = {'carBillCode': self.name, 'SAPOrderNo': self.name, 'SAPOrderItemNo': str(row.id),
                    'batchAttr04': row.lot_id.name or ''}
            quantity = row.uom_id._compute_quantity(row.quantity, row.product_id.uom_id, round=False)
            if direction == 'in':
                item.update(materialCode=row.product_id.default_code, materialQuantity=str(quantity),
                            intoOrderInParamsVzf=[{'traceCode': row.package_id.name, 'matQty': quantity, 'wholePallet': True}])
            else:
                if not device.wes_storage_type:
                    raise UserError(self.env._('Configure a WES storage type.'))
                item.update(matCode=row.product_id.default_code, outQty=quantity, stgTypCode=device.wes_storage_type,
                            outPalletAllocationList=[{'traceCode': row.package_id.name, 'outQty': quantity}])
            items.append(item)
        if direction == 'in':
            payload.update(planOrderType=device.wes_order_type, planItemVOList=items)
        else:
            payload.update(outOrderType=device.wes_order_type, outOrderItemList=items)
        return payload

    def _receive_wes_item_completion(self, event_id, item_ref, actual_destination=''):
        import hashlib
        import json
        from odoo.exceptions import ValidationError
        from odoo.addons.blue_wcs_base.models.guard import WCS_TOKEN

        self.ensure_one()
        self._lock()
        if self.equipment_id.adapter_code != 'wes' or self.state not in ('sending', 'unknown', 'accepted', 'running', 'completed'):
            raise UserError(self.env._('This WES task is not awaiting item completion.'))
        row = self.plan_id.line_ids.filtered(lambda item: str(item.id) == str(item_ref))
        if len(row) != 1:
            raise ValidationError(self.env._('Unknown WES item reference.'))
        if actual_destination and actual_destination != self.destination_point:
            raise ValidationError(self.env._('Unexpected WES destination; reconcile the actual bin.'))
        content = json.dumps(['item_end', str(row.id), actual_destination], separators=(',', ':'))
        digest = hashlib.sha256(content.encode()).hexdigest()
        existing = self.env['wcs.event'].search([('request_id', '=', self.id), ('external_id', '=', event_id)], limit=1)
        if existing and existing.content_hash != digest:
            raise ValidationError(self.env._('WES event ID was reused with different content.'))
        if not existing:
            self.env['wcs.event'].with_context(blue_wcs_token=WCS_TOKEN).create({
                'request_id': self.id, 'company_id': self.company_id.id, 'external_id': event_id,
                'event': 'item_end', 'point': str(row.id), 'content_hash': digest})
        completed_items = set(self.event_ids.filtered(lambda entry: entry.event == 'item_end').mapped('point'))
        if {str(item.id) for item in self.plan_id.line_ids} <= completed_items:
            self._receive_event('all-items-' + self.name, 'end', actual_destination=self.destination_point)
        return True
