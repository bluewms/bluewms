from odoo.addons.muk_ai.providers import REGISTRY

from .chat_completions import BlueCloudProvider

REGISTRY[BlueCloudProvider.name] = BlueCloudProvider
