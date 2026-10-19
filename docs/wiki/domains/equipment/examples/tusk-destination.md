# TUSK 完成后确定实际库存库位

- 知识 ID：`equipment.tusk_destination`
- 知识状态：`verified`（准确代码与声明试算经本地合同验证；云端批准另行记录）
- hook：`device_protocol`
- 适用合同：`device_protocol/1`
- 来源：Odoo 19 `bluewms19` `7d77ae7` 的 `blue_wcs_tusk` 协议；本实例设备合同与回归文件 `blue_wcs_protocol/tests/data/protocol_regression_cases.json`
- 代码 SHA-256：`ce6a756985bb0c90c6c5e65fbea8e9702df22779af4a0864fe3432c5dbce2823`
- 复核日期：2026-10-18

## 使用前提

人工创建设备类别，统一采用 HTTP／JSON，填写设备地址和 `/rpc/createTask`，按旧 TUSK 配置完成回调。该回调只在最终完成时发送；成功应答为 code=200、msg=success。地址和密钥不由代码修改。由代码输出 destination_code 选择库存库位回写。回报编码必须在当前作业仓库、同一公司内唯一匹配现有内部库位；原生容量、重量、混放和冻结约束必须通过。

本地准确合同优先；保存草稿后必须试算、验证并由用户发布。重复回报幂等，未知地址、多个匹配或库存不满足时待核对。真实设备验收与此报文试算分开。

## 准确代码

```python
if request["phase"] == "request":
    result = {"body": {"taskId": request["task"]["task_id"], "targets": [request["task"]["source"], request["task"]["destination"]], "configId": request["task"]["template"]}}
elif request["phase"] == "response":
    result = {"state": "accepted" if request["message"].get("msg", "") == "success" else "unknown", "reason": "按厂商响应确认接受状态"}
else:
    result = {"task_id": request["message"]["taskId"], "event": "end", "point": request["message"]["targetPoint"], "subposition": "", "destination_code": request["message"]["targetPoint"], "response": {"code": 200, "msg": "success"}}
```

## 完整试算 JSON

```json
[
  {
    "name": "request",
    "input": {
      "request": {
        "phase": "request",
        "task": {
          "task_id": "WCS-example-1",
          "source": "A",
          "destination": "B",
          "template": "TRANSFER",
          "carrier": "PALLET-1",
          "device_code": "",
          "role": "goods",
          "operation": "incoming"
        },
        "message": {},
        "http_status": 0,
        "parameters": {}
      },
      "candidates": [
        {
          "product_code": "SKU-1",
          "quantity": 10,
          "uom": "Units",
          "lot": ""
        }
      ]
    },
    "expected_result": {
      "body": {
        "taskId": "WCS-example-1",
        "targets": [
          "A",
          "B"
        ],
        "configId": "TRANSFER"
      }
    }
  },
  {
    "name": "response",
    "input": {
      "request": {
        "phase": "response",
        "task": {
          "task_id": "WCS-example-1",
          "source": "A",
          "destination": "B",
          "template": "TRANSFER",
          "carrier": "PALLET-1",
          "device_code": "",
          "role": "goods",
          "operation": "incoming"
        },
        "message": {
          "msg": "success"
        },
        "http_status": 200,
        "parameters": {}
      },
      "candidates": [
        {
          "product_code": "SKU-1",
          "quantity": 10,
          "uom": "Units",
          "lot": ""
        }
      ]
    },
    "expected_result": {
      "state": "accepted",
      "reason": "按厂商响应确认接受状态"
    }
  },
  {
    "name": "response",
    "input": {
      "request": {
        "phase": "response",
        "task": {
          "task_id": "WCS-example-1",
          "source": "A",
          "destination": "B",
          "template": "TRANSFER",
          "carrier": "PALLET-1",
          "device_code": "",
          "role": "goods",
          "operation": "incoming"
        },
        "message": {
          "msg": "unknown"
        },
        "http_status": 200,
        "parameters": {}
      },
      "candidates": [
        {
          "product_code": "SKU-1",
          "quantity": 10,
          "uom": "Units",
          "lot": ""
        }
      ]
    },
    "expected_result": {
      "state": "unknown",
      "reason": "按厂商响应确认接受状态"
    }
  },
  {
    "name": "callback",
    "input": {
      "request": {
        "phase": "callback",
        "task": {
          "task_id": "WCS-example-1",
          "source": "A",
          "destination": "B",
          "template": "TRANSFER",
          "carrier": "PALLET-1",
          "device_code": "",
          "role": "goods",
          "operation": "incoming"
        },
        "message": {
          "taskId": "WCS-example-1",
          "deviceId": "ROBOT-1",
          "targetPoint": "BIN-C"
        },
        "http_status": 0,
        "parameters": {}
      },
      "candidates": [
        {
          "product_code": "SKU-1",
          "quantity": 10,
          "uom": "Units",
          "lot": ""
        }
      ]
    },
    "expected_result": {
      "task_id": "WCS-example-1",
      "event": "end",
      "point": "BIN-C",
      "subposition": "",
      "destination_code": "BIN-C",
      "response": {
        "code": 200,
        "msg": "success"
      }
    }
  }
]
```

示例中的 WCS 任务号和库位编码均为测试值，生成时必须使用当前任务与本地合同字段。由代码输出 destination_code 选择库存库位回写。回报编码必须在当前作业仓库、同一公司内唯一匹配现有内部库位；原生容量、重量、混放和冻结约束必须通过。

规范见 [设备协议规范](../specification.md)，配置见 [使用说明](../configuration-guide.md)。
