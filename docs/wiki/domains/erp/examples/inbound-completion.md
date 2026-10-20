# ERP 接收与部分完成反馈

知识 ID：erp.inbound_completion。hook：erp_mapping。合同：erp_mapping/1。知识状态：verified。更新：2026-10-20。

来源：blue_erp_interface/tests/data/mapping.json，同版本解释器及业务回归验证。通用脱敏协议案例，不包含客户认证。入库案例的字段映射可按真实报文修改；每份新草稿必须重新试算。

## 前提与边界

人工配置 complete，或 count_gain／count_loss 操作代码与实际路径；已有唯一商品 ERP-PRODUCT，库存单位 Units（现场按本地真实名称），公司与位置已授权。代码不建主数据、不获取 Token、不调用网络。

## 准确代码

```python
if request["phase"] == "receive":
    lines = []
    for candidate in candidates:
        lines.append({"external_line_id": str(candidate["id"]), "product_code": candidate["product"], "quantity": candidate["qty"], "uom": candidate["unit"], "lot": candidate.get("lot", ""), "source_code": candidate.get("source", ""), "destination_code": candidate.get("destination", ""), "group": candidate.get("group", "")})
    result = {"documents": [{"external_id": str(request["message"]["id"]), "number": request["message"]["number"], "partner_code": "", "lines": lines}]}
elif request["phase"] == "complete":
    result = {"actions": [{"operation": "complete", "body": {"event_id": request["event_key"], "id": request["external_id"], "lines": candidates}}]}
elif request["phase"] == "inventory":
    gains = []
    losses = []
    for candidate in candidates:
        if candidate["difference_quantity"] > 0:
            gains.append(candidate)
        else:
            losses.append(candidate)
    actions = []
    if len(gains) > 0:
        actions.append({"operation": "count_gain", "body": {"event_id": request["event_key"], "lines": gains}})
    if len(losses) > 0:
        actions.append({"operation": "count_loss", "body": {"event_id": request["event_key"], "lines": losses}})
    result = {"actions": actions}
else:
    result = {"state": "unknown", "external_number": ""}
    if request["http_status"] == 200:
        if request["message"].get("success") == True:
            result = {"state": "accepted", "external_number": request["message"].get("number", "")}
        elif request["message"].get("rejected") == True:
            result = {"state": "rejected", "external_number": ""}
```

## 准确试算

```json
[
  {
    "name": "receive",
    "input": {
      "request": {
        "phase": "receive",
        "kind": "incoming",
        "event_key": "event-example",
        "external_id": "ERP-1",
        "number": "PO-1",
        "message": {
          "id": "ERP-1",
          "number": "PO-1",
          "lines": [
            {
              "id": "10",
              "product": "ERP-PRODUCT",
              "qty": 10,
              "unit": "Units"
            }
          ]
        },
        "http_status": 0,
        "operation": ""
      },
      "candidates": [
        {
          "id": "10",
          "product": "ERP-PRODUCT",
          "qty": 10,
          "unit": "Units"
        }
      ]
    },
    "expected_result": {
      "documents": [
        {
          "external_id": "ERP-1",
          "number": "PO-1",
          "partner_code": "",
          "lines": [
            {
              "external_line_id": "10",
              "product_code": "ERP-PRODUCT",
              "quantity": 10,
              "uom": "Units",
              "lot": "",
              "source_code": "",
              "destination_code": "",
              "group": ""
            }
          ]
        }
      ]
    }
  },
  {
    "name": "partial-completion",
    "input": {
      "request": {
        "phase": "complete",
        "kind": "incoming",
        "event_key": "event-example",
        "external_id": "ERP-1",
        "number": "PO-1",
        "message": {},
        "http_status": 0,
        "operation": ""
      },
      "candidates": [
        {
          "external_line_id": "10",
          "product_code": "ERP-PRODUCT",
          "quantity": 6,
          "cumulative_quantity": 6,
          "acknowledged_quantity": 0,
          "planned_quantity": 10,
          "uom": "Units",
          "lot": "",
          "source_code": "",
          "destination_code": "",
          "package": ""
        }
      ]
    },
    "expected_result": {
      "actions": [
        {
          "operation": "complete",
          "body": {
            "event_id": "event-example",
            "id": "ERP-1",
            "lines": [
              {
                "external_line_id": "10",
                "product_code": "ERP-PRODUCT",
                "quantity": 6,
                "cumulative_quantity": 6,
                "acknowledged_quantity": 0,
                "planned_quantity": 10,
                "uom": "Units",
                "lot": "",
                "source_code": "",
                "destination_code": "",
                "package": ""
              }
            ]
          }
        }
      ]
    }
  },
  {
    "name": "accepted",
    "input": {
      "request": {
        "phase": "response",
        "kind": "incoming",
        "event_key": "event-example",
        "external_id": "ERP-1",
        "number": "PO-1",
        "message": {
          "success": true,
          "number": "ERP-DONE"
        },
        "http_status": 200,
        "operation": "complete"
      },
      "candidates": []
    },
    "expected_result": {
      "state": "accepted",
      "external_number": "ERP-DONE"
    }
  },
  {
    "name": "timeout-ambiguous",
    "input": {
      "request": {
        "phase": "response",
        "kind": "incoming",
        "event_key": "event-example",
        "external_id": "ERP-1",
        "number": "PO-1",
        "message": {},
        "http_status": 502,
        "operation": "complete"
      },
      "candidates": []
    },
    "expected_result": {
      "state": "unknown",
      "external_number": ""
    }
  },
  {
    "name": "rejected",
    "input": {
      "request": {
        "phase": "response",
        "kind": "incoming",
        "event_key": "event-example",
        "external_id": "ERP-1",
        "number": "PO-1",
        "message": {
          "rejected": true
        },
        "http_status": 200,
        "operation": "complete"
      },
      "candidates": []
    },
    "expected_result": {
      "state": "rejected",
      "external_number": ""
    }
  }
]
```

## 验证范围

本页代码与试算逐项对比同版本解释器。业务回归另覆盖重复推送、欠单 6+4、累计超量拒绝、原生库存调整快照及公司隔离；均为隔离库与模拟 HTTP，不作为真实 ERP 联调结果。
