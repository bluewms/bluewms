# 上架标准示例

更新：2026-10-17。三个案例沿用已验证的准确代码和试算，各自独立维护。代码源自 `blue_stock_putaway`，遵循其 AGPL-3.0-or-later 许可证；来源和测试基线见各页。

| 知识 ID | 案例 | 合同 | 状态 |
|---|---|---|---|
| `putaway.same_lot` | [同产品同批次优先集中](same-lot.md) | v1／v2 通用字段 | verified |
| `putaway.same_picking` | [同一作业单优先集中](same-picking.md) | v1／v2 通用字段 | verified |
| `putaway.same_batch_name` | [跨产品同批次号限制](same-batch-name.md) | v2 | verified |

参考案例按 [案例格式](../../../templates/example-template.md) 记录完整代码、测试和适用合同。三个案例共九条最小解释器试算；生成新草稿时必须重新验证，不能替代容量／托盘／原生规则等真实业务校验。

当前生成以读取工具实际返回的批准案例和本地合同为准，不能声称已经读过未返回的资料。共同能力及限制见 [上架规范](../specification.md)。
