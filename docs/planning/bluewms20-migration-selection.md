# 库存迁移候选与状态

更新：2026-10-18。这里只记录已选和待选范围，不作为安装全部候选的授权。

| 原功能／旧来源 | 归属 | 当前状态 |
|---|---|---|
| `blue_stock` 库存基础 | `blue_stock_base`，品牌界面拆至 `blue_web_theme` | 已迁移，见[基础说明](../migrations/blue-stock-20.md) |
| `stock_no_negative`、`stock_location_lockdown` | 独立 `blue_stock_rules` | 已迁移，保留原 AGPL 和来源，见[规则说明](../migrations/stock-rules-20.md) |
| `stock_same_lot`、`stock_putaway_same_picking` | `blue_stock_putaway` | 已重做为受限增强能力；同单、同批次与跨产品批次号案例在云端，见[上架说明](../migrations/putaway-policy-20.md) |
| `stock_empty_package_storage` | 候选 `blue_stock_empty_package` | 待选择；先解决包裹位置、依赖和单位语义 |
| `blue_auto_unpack` | 候选包裹扩展或 `blue_stock_auto_unpack` | 待选择；按独立安装价值确定，不新增通用脚本入口 |
| `stock_inventory_ajustement` | 候选 `blue_stock_inventory` | 待迁移；人工盘点和差异流程不依赖机器人或条码 |
| `stock_inventory_barcode_bridge` | 候选 `blue_barcode_inventory` | 等条码基础与盘点能力就绪，保持与库存基础分开 |
| 机器人盘点、客户 WCS／ERP 桥接 | `blue_wcs_*` 或 `blue_project_*` | 按具体协议和项目独立评审，不因 WCS 基础可用就视为全部迁入 |

库存基础、硬约束、上架策略、包裹、盘点及条码各有职责。分类不是要求每个规则都新建模块；也不能把一个客户的同批次要求固化成所有实例的默认行为。

迁移前核对原作者／许可、模型和 XML ID、依赖、已有数据库、单位／数量／批次／位置语义与所有消费者。新库采用目标名；旧客户库必须有独立迁移和恢复方案，不全局替换名称。

当前已交付范围以[开发计划](bluewms20-development-plan.md)为准，旧 19 源文件只作调查证据，不直接当作 Odoo 20 成品安装。
