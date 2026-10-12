# blue_stock_putaway

Odoo 20 首期可编辑上架策略闭环。使用方法、AI草稿接口、执行合同、权限和范围见 [交付说明](../docs/migrations/putaway-policy-20.md)。

代码、模板和样例可编辑；保存草稿不会自动发布。正式版本在本地数据库保存，运行不需要云端 API key。

## 20.0.1.1.0

系统设置优先, 代码只补充。支持整托盘及跨产品同批次号。详见 [托盘增强交付](../docs/migrations/putaway-pallet-enhancement-20.md)。

## 20.0.1.2.0

在原生上架规则列表直接选择增强场景. 策略移除重复范围字段, 按规则固定版本. 见 [使用说明](../docs/migrations/putaway-rule-binding-20.md)。
