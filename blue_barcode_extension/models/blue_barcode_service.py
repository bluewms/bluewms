from odoo import api, models
from odoo.exceptions import UserError

from odoo.addons.blue_barcode_base.models.guard import scan_text


class BlueBarcodeService(models.AbstractModel):
    _inherit = 'blue.barcode.service'

    @api.model
    def _policy_snapshot(self, target, kind):
        profiles = (target.picking_type_id.blue_barcode_profile_id if kind in ('picking', 'batch')
                    else self.env.company.blue_barcode_profile_id)
        profile = profiles or self.env.company.blue_barcode_profile_id
        if not profile:
            return super()._policy_snapshot(target, kind)
        profile.ensure_one()
        release = profile.active_release_id
        if not profile.active or not release:
            raise UserError(self.env._('已绑定的条码策略尚未发布或已停用.'))
        if profile.company_id != self.env.company or release.version_id.contract != 'barcode_policy/1':
            raise UserError(self.env._('条码正式版本公司或合同不符.'))
        return {'release_id': release.id, 'contract': release.version_id.contract,
                'code': release.version_id.code_text, 'hash': release.content_hash}

    @api.model
    def lookup(self, raw, kind=False):
        self._authorize()
        scan_text(raw)
        profile = self.env.company.blue_barcode_profile_id
        matches = super().lookup(raw, kind)
        if not profile:
            return matches
        # Document routing is a fixed service, outside the product parse contract.
        if not kind and any(item['kind'] in ('picking', 'batch') for item in matches):
            return matches
        snapshot = self._policy_snapshot(self.env.company, 'home')
        parsed = self.env['blue.extension.contract']._run(snapshot['code'], {
            'request': {'phase': 'parse', 'raw': raw, 'context': {'kind': 'home'}, 'parsed': {}},
            'candidates': []}, 'barcode_policy/1')
        return [item for item in super().lookup(parsed['code'], kind) if item['kind'] == parsed['kind']]
