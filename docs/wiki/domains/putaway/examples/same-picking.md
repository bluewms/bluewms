# 同一作业单优先集中

- 知识 ID：`putaway.same_picking`
- 知识状态：`verified`（代码与声明用例已验证；云端批准／发布另行记录）
- hook：`putaway_policy`
- 适用合同：`putaway_policy/1（v2 同字段可用）`
- 来源：开发提交 `ad35793` 的 `blue_stock_putaway/tests/data/putaway_regression_cases.json` 中 `blue_scene_template_same_picking`
- 本页复核日期：2026-10-18
- 代码 SHA-256：`ec0ec15aeb7b7e58f60223ad7fa435c2ebd23482dce02e937759ecd2bf5c2131`
云端发布：以对应 Wiki 的发布清单和平台批准状态为准，文稿标签本身不能授予执行权限。

## 需求与适用范围

优先本入库单已使用或待上架的位置，其次空库位，再考虑其他合规位置。容量不足允许拆分；不独占库位。

系统已经过滤不合规位置，代码只补充限制或排序。原生规则优先级、容量、重量、混放、冻结及公司权限继续生效；整托盘不拆分。same_picking 的含义以本地候选构造为准；不保证全单全局最优，也不独占库位。

## 准确代码

```python
result = []
for candidate in candidates:
    score = 20
    reason = "其他合规库位"
    if candidate["same_picking"]:
        score = 0
        reason = "同入库单已有或待上架位置"
    elif candidate["empty"]:
        score = 10
        reason = "优先空库位"
    result.append({"location_id": candidate["location_id"], "score": score, "reason": reason})
```

## 试算预期

| 用例 | 解释器返回的位置顺序 |
|---|---|
| 集中优先 | `[2, 1, 3]` |
| 无集中位置时空位优先 | `[1, 2, 3]` |
| 无合规候选 | `[]` |

最小试算仅保留本段代码读取的字段；真实作业输入还有本地合同提供的其他字段。解释器按补充分数排序；实际业务仍先按原生优先级处理。

## 完整试算 JSON

```json
[
  {
    "name": "集中优先",
    "input": {
      "request": {
        "product_id": 1,
        "lot_id": 1,
        "picking_id": 1,
        "quantity": 2
      },
      "candidates": [
        {
          "location_id": 1,
          "same_lot": false,
          "same_picking": false,
          "empty": true,
          "max_quantity": 10,
          "fits_all": true
        },
        {
          "location_id": 2,
          "same_lot": true,
          "same_picking": true,
          "empty": false,
          "max_quantity": 10,
          "fits_all": true
        },
        {
          "location_id": 3,
          "same_lot": false,
          "same_picking": false,
          "empty": false,
          "max_quantity": 10,
          "fits_all": true
        }
      ]
    },
    "expected_order": [
      2,
      1,
      3
    ]
  },
  {
    "name": "无集中位置时空位优先",
    "input": {
      "request": {
        "product_id": 1,
        "lot_id": 1,
        "picking_id": 1,
        "quantity": 2
      },
      "candidates": [
        {
          "location_id": 1,
          "same_lot": false,
          "same_picking": false,
          "empty": true,
          "max_quantity": 10,
          "fits_all": true
        },
        {
          "location_id": 2,
          "same_lot": false,
          "same_picking": false,
          "empty": false,
          "max_quantity": 10,
          "fits_all": true
        },
        {
          "location_id": 3,
          "same_lot": false,
          "same_picking": false,
          "empty": false,
          "max_quantity": 10,
          "fits_all": true
        }
      ]
    },
    "expected_order": [
      1,
      2,
      3
    ]
  },
  {
    "name": "无合规候选",
    "input": {
      "request": {
        "product_id": 1,
        "lot_id": 1,
        "picking_id": 1,
        "quantity": 2
      },
      "candidates": []
    },
    "expected_order": []
  }
]
```

## 验证证据与限制

本页声明的 3 条用例已用本地同版本解释器逐一复核，核对输出位置顺序。三个标准案例合计九条用例。解释器试算、模块业务回归和真实模型联调是不同证据，不能互相代替。

通过这些最小用例不代表已经测试所有业务组合；容量、托盘和真实单据行为需结合本地预览及业务回归。AI 生成新草稿后仍要执行它自己的测试并由用户发布，不能把参考代码的验证直接沿用为新代码验证。

关联：[上架规范](../specification.md) · [示例目录](README.md)。示例代码源自 `blue_stock_putaway`，代码许可 AGPL-3.0-or-later；后续修改保留来源和验证记录。
