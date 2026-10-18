from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    provider = env.ref('blue_ai_client.provider_blue_cloud', raise_if_not_found=False)
    if provider and provider.max_tokens == 8192:
        provider.max_tokens = 16384
    agent = env.ref('blue_ai_client.agent_blue_code', raise_if_not_found=False)
    if agent:
        extra = ['blue_search_code_knowledge', 'blue_read_code_knowledge']
        values = {'essential_tool_names': list(dict.fromkeys((agent.essential_tool_names or []) + extra))}
        if agent.tool_filter:
            values['tool_filter'] = list(dict.fromkeys(agent.tool_filter + extra))
        agent.write(values)
