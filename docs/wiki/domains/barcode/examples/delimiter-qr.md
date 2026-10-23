# 分隔二维码同时提取商品与数量

知识 ID: `barcode.delimiter_qr`. hook: `barcode_policy`. 合同: `barcode_policy/1`. 状态: verified（本地）. 日期: 2026-10-21. 作者: 宁波宝蓝物流科技有限公司. 许可: AGPL-3.0-or-later.

## 业务需求和边界

输入 `HDR#VENDOR#QRPRODUCT#LOT88#12#END`,第 2/3 个 # 之间是产品条码,第 4/5 个 # 之间是本次增加的库存单位数量. 一次增加 12,不先增加 1. LOT88 未被声明为批次,不自动使用. 分隔符按出现次数从 1 计数,空字段保留.

这个案例只接收上述分隔格式. 普通码、位置、批次或包裹另加明确分支;不能在格式错误时悄悄退回加 1. 多候选时提示选择,不取第一个. 配置授权、库存约束、幂等及实际写入由固定服务复核.

## 完整代码

```python
if request['phase'] == 'parse':
    raw = request['raw']
    result = {'kind': 'product', 'code': between(raw, '#', 2, 3), 'quantity': float(between(raw, '#', 4, 5)), 'lot': '', 'location': '', 'package': '', 'uom': '', 'reason': ''}
else:
    result = {'action': 'prompt', 'keys': [], 'reason': 'Select a row'}
    if len(candidates) == 1:
        result = {'action': 'count', 'keys': [candidates[0]['key']], 'reason': ''}
```

## 准确试算

```json
[
  {
    "name": "商品与数量一次提取",
    "input": {
      "request": {
        "phase": "parse",
        "raw": "HDR#VENDOR#QRPRODUCT#LOT88#12#END",
        "context": {},
        "parsed": {}
      },
      "candidates": []
    },
    "expected_result": {
      "kind": "product",
      "code": "QRPRODUCT",
      "quantity": 12.0,
      "lot": "",
      "location": "",
      "package": "",
      "uom": "",
      "reason": ""
    }
  },
  {
    "name": "选择唯一允许明细",
    "input": {
      "request": {
        "phase": "decide",
        "raw": "HDR#VENDOR#QRPRODUCT#LOT88#12#END",
        "context": {},
        "parsed": {
          "kind": "product",
          "code": "QRPRODUCT",
          "quantity": 12.0,
          "lot": "",
          "location": "",
          "package": "",
          "uom": "",
          "reason": ""
        }
      },
      "candidates": [
        {
          "key": "line:1",
          "product_id": 1,
          "quantity": 0,
          "expected": 20
        }
      ]
    },
    "expected_result": {
      "action": "count",
      "keys": [
        "line:1"
      ],
      "reason": ""
    }
  }
]
```

## 验证及来源

与 `blue_barcode_extension/tests/data/delimiter_qr.json` 保持逐字一致,通过 `scripts/validate_ai_wiki.py` 在隔离库验证. 合同试算、发布与固定版本,以及 QR 一次计数由模块回归另行覆盖. 本地 verified 不表示云端索引 ready、平台批准或客户策略已发布.
