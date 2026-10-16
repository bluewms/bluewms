# blue_extension_contract

Odoo 20 首期可编辑上架策略闭环。使用方法、AI草稿接口、执行合同、权限和范围见 [交付说明](../docs/migrations/putaway-policy-20.md)。

策略使用受限 AST 解释器执行纯 JSON 数据，不提供 ORM、网络、文件或任意 Python 调用。`_describe(contract)` 为上架 v1/v2 返回机器可读字段、语法、输出和资源限制；由 `blue_ai_client` 返回给模型。正式版本在本地执行，无需云端 API Key 在线。

## 20.0.1.1.0

系统设置优先, 代码只补充。支持整托盘及跨产品同批次号。详见 [托盘增强交付](../docs/migrations/putaway-pallet-enhancement-20.md)。
