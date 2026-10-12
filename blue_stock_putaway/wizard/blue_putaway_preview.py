import json

from odoo import fields, models
from odoo.exceptions import AccessError, UserError


class BluePutawayPreview(models.TransientModel):
    _name = 'blue.putaway.preview'
    _description = 'Read-only putaway trial on a real move line'
    _check_company_auto = True

    profile_id = fields.Many2one('blue.config.profile', '场景', required=True, check_company=True)
    rule_id = fields.Many2one('stock.putaway.rule', '原生上架规则', required=True, check_company=True, domain="[('blue_profile_id', '=', profile_id), ('company_id', '=', company_id)]")
    company_id = fields.Many2one(related='profile_id.company_id')
    move_line_id = fields.Many2one('stock.move.line', '待上架明细', required=True, check_company=True,
                                   domain="[('company_id', '=', company_id), ('state', 'not in', ['done', 'cancel'])]")
    use_draft = fields.Boolean('试算草稿代码', default=True)
    result = fields.Text('试算结果', readonly=True)
    detail = fields.Text('输入与输出快照', readonly=True)

    def action_preview(self):
        self.ensure_one()
        self.check_access('write')
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise AccessError(self.env._('Only inventory managers can trial unpublished drafts.'))
        if self.rule_id.blue_profile_id != self.profile_id:
            raise UserError(self.env._('请选择绑定当前场景的原生上架规则.'))
        payload = self.profile_id._prepare_putaway_payload(self.move_line_id, self.rule_id)
        binding = self.move_line_id.picking_id.blue_putaway_binding_ids.filtered(lambda item: item.rule_key == self.rule_id.id)
        release = binding.release_id if binding else self.profile_id.active_release_id
        if self.use_draft:
            code, contract = self.profile_id.draft_code, self.profile_id.contract
        elif release:
            code, contract = release.version_id.code_text, release.version_id.contract
        else:
            raise UserError(self.env._('Publish a version before trialing the active policy.'))
        result = self.env['blue.extension.contract']._run(code, payload, contract)
        result = self.profile_id._rank_supplementary_result(result, payload)
        candidates = {item['location_id']: item for item in payload['candidates']}
        summary = [self.env._('系统设置允许 %(native)s 个库位, 补充条件保留 %(retained)s 个.', native=len(candidates), retained=len(result))]
        if not result:
            summary.append(self.env._('没有满足全部条件的库位. 实际分配会停止并提示处理.'))
        for rank, item in enumerate(result, 1):
            candidate = candidates[item['location_id']]
            if payload['request']['unit'] == 'package':
                capacity = str(candidate['package_capacity']) if candidate['package_capacity'] else self.env._('未设置此包装类型上限')
                summary.append(self.env._('%(rank)s. %(name)s | 分配后托盘数: %(after)s / %(capacity)s | %(reason)s',
                    rank=rank, name=candidate['name'], after=candidate['packages_after'], capacity=capacity, reason=item['reason']))
            else:
                summary.append(self.env._('%(rank)s. %(name)s | 可放数量: %(quantity)s | %(reason)s',
                    rank=rank, name=candidate['name'], quantity=candidate['max_quantity'], reason=item['reason']))
        summary.append(self.env._('仅试算, 不修改库存、目的库位或单据版本.'))
        self.result = '\n'.join(summary)
        self.detail = json.dumps({'input': payload, 'result': result}, ensure_ascii=False, indent=2)
        return {'type': 'ir.actions.act_window', 'name': self.env._('真实单据试算'), 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'new'}
