# AI同数据双作业

知识ID: wcs.repeat; hook: wcs_creation; contract: wcs_creation/4。状态: verified；云端批准状态以发布清单与平台资产元数据为准。声明用例均已通过实际解释器; 新草稿仍需本次验证和人工发布。

## 准确代码

```python
if request["phase"] == "lines":
    result = []
    for candidate in candidates:
        action = "create"
        quantity = candidate["available_quantity"]
        reason = "满足搬运条件"
        result.append({"line_id": candidate["line_id"], "action": action, "quantity_basis": "confirmed" if request["operation"] == "incoming" else "reserved", "quantity": quantity, "group_key": candidate["line_key"], "source_ref": "line_source", "destination_ref": "line_destination", "reason": reason})
else:
    first = request["base_task"]
    result = [first, {"equipment_id": first["equipment_id"], "location_res_id": first["location_res_id"], "location_dest_id": first["location_dest_id"], "source_ref": first["source_ref"], "destination_ref": first["destination_ref"], "role": first["role"], "task_type": first["task_type"], "movement": "repeat", "dependency_step": 1, "dependency_event": "end", "dependency_point": first["dependency_point"], "reason": "同数据第二个程序"}]
```

## 完整试算

```json
[
  {
    "name": "逐行决策",
    "input": {
      "request": {
        "phase": "lines",
        "picking_id": 1,
        "state": "assigned",
        "company_id": 1,
        "operation": "internal",
        "wcs_type": "out",
        "all_confirmed": true,
        "picking_source_id": 15,
        "picking_destination_id": 25
      },
      "candidates": [
        {
          "line_id": 101,
          "line_key": "line:101",
          "carrier_id": 31,
          "carrier_key": "package:31",
          "route_key": "route:31:10:20",
          "product_id": 21,
          "product_code": "AUTO",
          "lot_id": false,
          "owner_id": false,
          "uom_id": 1,
          "quantity": 10,
          "covered_quantity": 0,
          "available_quantity": 10,
          "picked": true,
          "stock_state": "assigned",
          "source_id": 10,
          "destination_id": 20,
          "carrier_all_picked": true,
          "carrier_same_uom": true,
          "carrier_quantity": 10,
          "carrier_weight": 10,
          "carrier_weight_complete": true,
          "carrier_volume": 0,
          "carrier_volume_complete": false,
          "package_max_weight": 20,
          "package_type_id": 41
        }
      ]
    },
    "expected_result": [
      {
        "line_id": 101,
        "action": "create",
        "quantity_basis": "reserved",
        "quantity": 10,
        "group_key": "line:101",
        "source_ref": "line_source",
        "destination_ref": "line_destination",
        "reason": "满足搬运条件"
      }
    ]
  },
  {
    "name": "任务编排",
    "input": {
      "request": {
        "phase": "tasks",
        "picking_id": 1,
        "state": "assigned",
        "company_id": 1,
        "operation": "internal",
        "wcs_type": "out",
        "all_confirmed": true,
        "picking_source_id": 15,
        "picking_destination_id": 25,
        "positions": {
          "line_source": 10,
          "line_destination": 20,
          "picking_source": 15,
          "picking_destination": 25,
          "source_parent": 15,
          "destination_parent": 25,
          "handoff": 30
        },
        "base_task": {
          "equipment_id": 1,
          "location_res_id": 10,
          "location_dest_id": 20,
          "source_ref": "line_source",
          "destination_ref": "line_destination",
          "role": "goods",
          "task_type": "TRANSFER",
          "movement": "primary",
          "dependency_step": 0,
          "dependency_event": "end",
          "dependency_point": "",
          "reason": "满足搬运条件"
        },
        "equipment": {
          "1": {
            "name": "Primary",
            "task_type": "TRANSFER",
            "adapter": "simulation"
          },
          "2": {
            "name": "Secondary",
            "task_type": "LEG2",
            "adapter": "simulation"
          }
        },
        "primary_equipment_id": 1,
        "secondary_equipment_id": 2,
        "secondary_task_type": "LEG2",
        "position_details": {
          "line_source": {
            "id": 10,
            "name": "A",
            "point": "A"
          }
        },
        "lines": {
          "101": {
            "line_id": 101,
            "line_key": "line:101",
            "carrier_id": 31,
            "carrier_key": "package:31",
            "route_key": "route:31:10:20",
            "product_id": 21,
            "product_code": "AUTO",
            "lot_id": false,
            "owner_id": false,
            "uom_id": 1,
            "quantity": 10,
            "covered_quantity": 0,
            "available_quantity": 10,
            "picked": true,
            "stock_state": "assigned",
            "source_id": 10,
            "destination_id": 20,
            "carrier_all_picked": true,
            "carrier_same_uom": true,
            "carrier_quantity": 10,
            "carrier_weight": 10,
            "carrier_weight_complete": true,
            "carrier_volume": 0,
            "carrier_volume_complete": false,
            "package_max_weight": 20,
            "package_type_id": 41
          }
        },
        "decisions": {
          "101": {
            "line_id": 101,
            "action": "create",
            "quantity_basis": "reserved",
            "quantity": 10,
            "group_key": "line:101",
            "source_ref": "line_source",
            "destination_ref": "line_destination",
            "reason": "满足搬运条件"
          }
        }
      },
      "candidates": [
        {
          "equipment_id": 1,
          "location_res_id": 10,
          "location_dest_id": 20,
          "source_ref": "line_source",
          "destination_ref": "line_destination",
          "role": "goods",
          "task_type": "TRANSFER",
          "movement": "primary",
          "dependency_step": 0,
          "dependency_event": "end",
          "dependency_point": "",
          "reason": "满足搬运条件"
        }
      ]
    },
    "expected_result": [
      {
        "equipment_id": 1,
        "location_res_id": 10,
        "location_dest_id": 20,
        "source_ref": "line_source",
        "destination_ref": "line_destination",
        "role": "goods",
        "task_type": "TRANSFER",
        "movement": "primary",
        "dependency_step": 0,
        "dependency_event": "end",
        "dependency_point": "",
        "reason": "满足搬运条件"
      },
      {
        "equipment_id": 1,
        "location_res_id": 10,
        "location_dest_id": 20,
        "source_ref": "line_source",
        "destination_ref": "line_destination",
        "role": "goods",
        "task_type": "TRANSFER",
        "movement": "repeat",
        "dependency_step": 1,
        "dependency_event": "end",
        "dependency_point": "",
        "reason": "同数据第二个程序"
      }
    ]
  }
]
```
