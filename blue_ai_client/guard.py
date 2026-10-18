# An in-process token keeps workflow metadata out of public RPC writes.
BINDING_TOKEN = object()
TEAM_NAME = 'odooAI'
TASK_NAME = '日常任务'
HOOK_TASKS = {
    'putaway_policy': '上架策略',
    'erp_mapping': 'ERP接口',
    'wcs_creation': 'WCS生成策略',
    'device_protocol': '设备连接接口',
    'barcode_policy': '条码扫描策略',
}
