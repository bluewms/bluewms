# 上架标准示例

更新：2026-10-17。三个案例沿用已验证的准确代码和试算，各自独立维护。代码源自 `blue_stock_putaway`，遵循其 AGPL-3.0-or-later 许可证；来源和测试基线见各页。

| 知识 ID | 案例 | 合同 | 状态 |
|---|---|---|---|
| `putaway.same_lot` | [同产品同批次优先集中](same-lot.md) | v1／v2 通用字段 | verified |
| `putaway.same_picking` | [同一作业单优先集中](same-picking.md) | v1／v2 通用字段 | verified |
| `putaway.same_batch_name` | [跨产品同批次号限制](same-batch-name.md) | v2 | verified |

新增案例从 [模板](../../../templates/example-template.md) 复制，代码和测试写在新文件，并在本目录添加链接。三个案例共九条最小解释器试算，不替代容量／托盘／原生规则等业务回归。

当前整理尚未重新发布云端，Odoo 仍读取原批准 Skill 的 `04-approved-putaway-examples.md`。人工维护分文件，发布时按 [映射](../../../publication-map.json) 汇编；不直接改运行时资源路径。共同规范见 [上架规范](../specification.md)。
