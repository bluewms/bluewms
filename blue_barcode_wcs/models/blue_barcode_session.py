from odoo import models
from odoo.exceptions import UserError


class BlueBarcodeSession(models.Model):
    _inherit = 'blue.barcode.session'

    def _actions(self):
        actions = super()._actions()
        if self.kind in ('picking', 'batch') and all(p.picking_type_id.blue_wcs_enabled for p in self.picking_ids):
            actions.append('wcs')
        return actions

    def action_execute(self, client_key, revision, action, group_key=''):
        if action != 'wcs':
            return super().action_execute(client_key, revision, action, group_key)
        self._lock()
        self._check_client(client_key)
        self._check_target()
        if (type(revision) is not int or revision != self.revision
                or self.fingerprint != self._fingerprint() or action not in self._actions()):
            raise UserError(self.env._('请先核对并保存当前数量,确认作业已启用 WCS.'))
        for picking in self.picking_ids:
            picking.action_create_wcs_request_from_button()
        self._internal().write({'revision': self.revision + 1, 'fingerprint': self._fingerprint()})
        return {'action': False, 'view': self._view(), 'message': self.env._('已通过 WCS 正式入口处理请求,请核对任务状态.')}
