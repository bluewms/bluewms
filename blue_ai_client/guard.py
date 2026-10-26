# An in-process token keeps workflow metadata out of public RPC writes.
BINDING_TOKEN = object()
TEAM_NAME = 'odooAI'
TASK_NAME = '日常任务'
REQUIRED_GUIDANCE = ('basics/ai-generation-workflow.md', 'basics/requirements-clarification.md')
REVIEW_QUESTION_PREFIX = '请确认本次需求理解:\n'
REVIEW_APPROVE = '确认并生成草稿'
HOOK_MODULES = {
    'putaway_policy': ('blue_stock_putaway', 'blue_stock_rules'),
    'wcs_creation': ('blue_wcs_base', 'blue_wcs_extension'),
    'erp_mapping': ('blue_erp_interface', 'blue_erp_inventory'),
    'device_protocol': ('blue_wcs_base', 'blue_wcs_protocol'),
    'barcode_policy': ('blue_barcode_base', 'blue_barcode_extension', 'blue_barcode_inventory', 'blue_barcode_wcs'),
}
HOOK_TASKS = {
    'putaway_policy': '上架策略',
    'erp_mapping': 'ERP接口',
    'wcs_creation': 'WCS生成策略',
    'device_protocol': '设备连接接口',
    'barcode_policy': '条码扫描策略',
}

CODE_TOOLS = {'blue_read_code_asset', 'blue_submit_code_draft', 'blue_validate_code_draft'}
KNOWLEDGE_TOOLS = {'blue_search_code_knowledge', 'blue_read_code_knowledge', 'ask_user'}
