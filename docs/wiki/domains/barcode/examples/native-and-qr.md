# 作业原生解析与 QR 数量共存

知识 ID: barcode.native_qr; hook: barcode_policy; contract: barcode_policy/1. 状态: verified.

本例绑定作业类型,识别固定 QR# 前缀,其他编码保留作业 context.standard 的原生结果,避免把位置/批次/包裹或 GS1 都当作普通商品. 首页查询没有该标准上下文,不把此例直接绑定成公司通用解析;须按实际公司查询编码规则另写 parse 和试算. 空的标准结果应验证失败,不能静默改成加 1.

## 准确代码

```python
if request['phase'] == 'parse':
    raw = request['raw']
    if raw[:3] == 'QR#':
        result = {'kind': 'product', 'code': between(raw, '#', 2, 3), 'quantity': float(between(raw, '#', 4, 5)), 'lot': '', 'location': '', 'package': '', 'uom': '', 'reason': 'QR quantity'}
    else:
        result = request['context'].get('standard', {})
else:
    if request['parsed']['kind'] != 'product':
        result = {'action': 'select', 'keys': [], 'reason': 'Select scanned context'}
    else:
        result = {'action': 'prompt', 'keys': [], 'reason': 'Select a unique row'}
        if len(candidates) == 1:
            result = {'action': 'count', 'keys': [candidates[0]['key']], 'reason': ''}
```

## 准确输入与预期

```json
[
  {
    "name": "QR 整次数量",
    "input": {
      "request": {
        "phase": "parse",
        "raw": "QR#v1#SKU-A#qty#3#",
        "context": {
          "kind": "picking",
          "standard": {}
        },
        "parsed": {}
      },
      "candidates": []
    },
    "expected_result": {
      "kind": "product",
      "code": "SKU-A",
      "quantity": 3,
      "lot": "",
      "location": "",
      "package": "",
      "uom": "",
      "reason": "QR quantity"
    }
  },
  {
    "name": "位置保持原生类型",
    "input": {
      "request": {
        "phase": "parse",
        "raw": "LOC-A",
        "context": {
          "kind": "picking",
          "standard": {
            "kind": "location",
            "code": "LOC-A",
            "quantity": 1,
            "lot": "",
            "location": "",
            "package": "",
            "uom": "",
            "reason": "native"
          }
        },
        "parsed": {}
      },
      "candidates": []
    },
    "expected_result": {
      "kind": "location",
      "code": "LOC-A",
      "quantity": 1,
      "lot": "",
      "location": "",
      "package": "",
      "uom": "",
      "reason": "native"
    }
  },
  {
    "name": "批次保持原生类型",
    "input": {
      "request": {
        "phase": "parse",
        "raw": "LOT-007",
        "context": {
          "kind": "picking",
          "standard": {
            "kind": "lot",
            "code": "LOT-007",
            "quantity": 1,
            "lot": "",
            "location": "",
            "package": "",
            "uom": "",
            "reason": "native"
          }
        },
        "parsed": {}
      },
      "candidates": []
    },
    "expected_result": {
      "kind": "lot",
      "code": "LOT-007",
      "quantity": 1,
      "lot": "",
      "location": "",
      "package": "",
      "uom": "",
      "reason": "native"
    }
  },
  {
    "name": "包裹保持原生类型",
    "input": {
      "request": {
        "phase": "parse",
        "raw": "PACK-007",
        "context": {
          "kind": "picking",
          "standard": {
            "kind": "package",
            "code": "PACK-007",
            "quantity": 1,
            "lot": "",
            "location": "",
            "package": "",
            "uom": "",
            "reason": "native"
          }
        },
        "parsed": {}
      },
      "candidates": []
    },
    "expected_result": {
      "kind": "package",
      "code": "PACK-007",
      "quantity": 1,
      "lot": "",
      "location": "",
      "package": "",
      "uom": "",
      "reason": "native"
    }
  },
  {
    "name": "GS1 数量与批次不二次换算",
    "input": {
      "request": {
        "phase": "parse",
        "raw": "]C1-example",
        "context": {
          "kind": "picking",
          "standard": {
            "kind": "product",
            "code": "SKU-A",
            "quantity": 2,
            "lot": "LOT-007",
            "location": "",
            "package": "",
            "uom": "",
            "reason": "GS1"
          }
        },
        "parsed": {}
      },
      "candidates": []
    },
    "expected_result": {
      "kind": "product",
      "code": "SKU-A",
      "quantity": 2,
      "lot": "LOT-007",
      "location": "",
      "package": "",
      "uom": "",
      "reason": "GS1"
    }
  },
  {
    "name": "非商品选择",
    "input": {
      "request": {
        "phase": "decide",
        "raw": "LOC-A",
        "context": {
          "kind": "picking"
        },
        "parsed": {
          "kind": "location",
          "code": "LOC-A",
          "quantity": 1,
          "lot": "",
          "location": "",
          "package": "",
          "uom": "",
          "reason": "native"
        }
      },
      "candidates": []
    },
    "expected_result": {
      "action": "select",
      "keys": [],
      "reason": "Select scanned context"
    }
  },
  {
    "name": "商品唯一明细",
    "input": {
      "request": {
        "phase": "decide",
        "raw": "SKU-A",
        "context": {
          "kind": "picking"
        },
        "parsed": {
          "kind": "product",
          "code": "SKU-A",
          "quantity": 1,
          "lot": "",
          "location": "",
          "package": "",
          "uom": "",
          "reason": "native"
        }
      },
      "candidates": [
        {
          "key": "line:7"
        }
      ]
    },
    "expected_result": {
      "action": "count",
      "keys": [
        "line:7"
      ],
      "reason": ""
    }
  },
  {
    "name": "商品歧义提示",
    "input": {
      "request": {
        "phase": "decide",
        "raw": "SKU-A",
        "context": {
          "kind": "picking"
        },
        "parsed": {
          "kind": "product",
          "code": "SKU-A",
          "quantity": 1,
          "lot": "",
          "location": "",
          "package": "",
          "uom": "",
          "reason": "native"
        }
      },
      "candidates": [
        {
          "key": "line:7"
        },
        {
          "key": "line:8"
        }
      ]
    },
    "expected_result": {
      "action": "prompt",
      "keys": [],
      "reason": "Select a unique row"
    }
  }
]
```

## 边界

QR 中的数量为本次增量,和商品信息作为一个事件保存. 固定服务仍核对明细、单位、批次/序列号及公司权限. 本例不新增动作授权,不跨行分摊,不提供任意前端/ORM 调用. 发布新草稿前按真实标签和业务配置重新测试.

standard 是固定服务已经解析的快照,本页试算不替代原生 GS1 解码或实机采集回归.
