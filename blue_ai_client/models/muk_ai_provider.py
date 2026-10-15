from odoo import api, models
from odoo.exceptions import ValidationError

from ..providers.chat_completions import normalize_url


class AIProvider(models.Model):
    _inherit = 'muk_ai.provider'

    @api.constrains('api_url', 'api_region', 'name')
    def _check_blue_url(self):
        for provider in self.filtered(lambda p: p.name == 'blue_cloud'):
            try:
                normalize_url(provider.api_url if provider.api_region == 'custom'
                              else provider._get_client().default_url)
            except ValueError as error:
                raise ValidationError(self.env._('请使用有效的 HTTPS 服务地址，不包含密码、查询参数或片段。')) from error
