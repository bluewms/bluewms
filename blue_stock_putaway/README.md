# blue_stock_putaway

Odoo 20 首期可编辑上架策略闭环。使用方法、AI草稿接口、执行合同、权限和范围见 [交付说明](../docs/migrations/putaway-policy-20.md)。

策略代码与本次试算用例可编辑，保存草稿不会自动发布。通用上架示例由云端维护，正式版本仍在本地执行，不需要云端 API Key 在线。

## 20.0.1.4.0

新场景使用“上架增强接口 v2”；保留旧接口 ID、批次能力、正式代码与单据固定版本，退出本地通用示例入口。见 [云端知识接入与升级](../docs/migrations/putaway-cloud-knowledge-20.md)。

## 20.0.1.1.0

系统设置优先, 代码只补充。支持整托盘及跨产品同批次号。详见 [托盘增强交付](../docs/migrations/putaway-pallet-enhancement-20.md)。

## 20.0.1.2.0

在原生上架规则列表直接选择增强场景. 策略移除重复范围字段, 按规则固定版本. 见 [使用说明](../docs/migrations/putaway-rule-binding-20.md)。
