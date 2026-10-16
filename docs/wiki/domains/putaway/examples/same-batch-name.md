# 跨产品同批次号限制

知识 ID：`putaway.same_batch_name`  
知识状态：`verified`（代码与声明用例已验证；云端批准／发布另行记录）  
hook：`putaway_policy`  
适用合同：`putaway_policy/2`  
来源：开发提交 `ad35793` 的 `blue_stock_putaway/tests/data/putaway_regression_cases.json` 中 `blue_scene_template_same_batch_name`  
本页复核日期：2026-10-17  
代码 SHA-256：`9972e3339b33b2e6d6f413d9b93c8267df90ee25ea261df073abbd53ea538a93`  
云端发布：原准确案例已在既有批准资源使用；本次分文件整理尚未重新发布。

## 需求与适用范围

Odoo原生上架规则和存储类别先筛选。补充代码只允许空库位或已有批次号完全相同的库位，允许不同产品。比较批次号文本，不比较产品专属的批次ID。整托盘不拆分。

系统已经过滤不合规位置，代码只补充限制或排序。原生规则优先级、容量、重量、混放、冻结及公司权限继续生效；整托盘不拆分。本次必须有唯一已知批次号；位置存在未知或其他批次号时不得混入。lot ID 不是跨产品批次号。

## 准确代码

```python
result = []
for candidate in candidates:
    if request["has_single_batch_name"] and (candidate["empty"] or candidate["batch_name_matches"]):
        score = 0 if candidate["batch_name_matches"] else 10
        reason = "同批次号，允许不同产品" if candidate["batch_name_matches"] else "空库位，建立本批次"
        result.append({"location_id": candidate["location_id"], "score": score, "reason": reason})
```

## 试算预期

| 用例 | 解释器返回的位置顺序 |
|---|---|
| 保留同批次号或空位，排除其他批次 | `[2, 1]` |
| 托盘包含多个批次号，拒绝分配 | `[]` |
| 无系统准入候选，拒绝分配 | `[]` |

最小试算仅保留本段代码读取的字段；真实作业输入还有本地合同提供的其他字段。解释器按补充分数排序；实际业务仍先按原生优先级处理。

## 完整试算 JSON

```json
[
  {
    "name": "保留同批次号或空位，排除其他批次",
    "input": {
      "request": {
        "has_single_batch_name": true,
        "batch_name": "BATCH-001"
      },
      "candidates": [
        {
          "location_id": 1,
          "empty": true,
          "batch_name_matches": false
        },
        {
          "location_id": 2,
          "empty": false,
          "batch_name_matches": true
        },
        {
          "location_id": 3,
          "empty": false,
          "batch_name_matches": false
        }
      ]
    },
    "expected_order": [
      2,
      1
    ]
  },
  {
    "name": "托盘包含多个批次号，拒绝分配",
    "input": {
      "request": {
        "has_single_batch_name": false,
        "batch_name": false
      },
      "candidates": [
        {
          "location_id": 1,
          "empty": true,
          "batch_name_matches": false
        },
        {
          "location_id": 2,
          "empty": false,
          "batch_name_matches": true
        },
        {
          "location_id": 3,
          "empty": false,
          "batch_name_matches": false
        }
      ]
    },
    "expected_order": []
  },
  {
    "name": "无系统准入候选，拒绝分配",
    "input": {
      "request": {
        "has_single_batch_name": true,
        "batch_name": "BATCH-001"
      },
      "candidates": []
    },
    "expected_order": []
  }
]
```

## 验证证据与限制

本限制只作用于绑定该增强场景的原生规则。其他未绑定的回退规则不自动继承它；若要求全流程同批次号，须一起检查原生规则配置和回退路径。

本页整理时用仓库当前纯 AST 解释器重新执行以上 3 条用例，核对输出位置顺序。三份标准案例合计九条用例；它们不是新执行的 150 项业务联合回归。此前模块的 150 项联合测试及真实模型场景证据见 [上架云端交付](../../../../migrations/putaway-cloud-knowledge-20.md)。

通过这些最小用例不代表已经测试所有业务组合；容量、托盘和真实单据行为需结合本地预览及业务回归。AI 生成新草稿后仍要执行它自己的测试并由用户发布，不能把参考代码的验证直接沿用为新代码验证。

关联：[上架规范](../specification.md) · [示例目录](README.md) · [维护约定](../../../maintenance.md)。示例代码源自 `blue_stock_putaway`，代码许可 AGPL-3.0-or-later；后续修改保留来源和验证记录。
