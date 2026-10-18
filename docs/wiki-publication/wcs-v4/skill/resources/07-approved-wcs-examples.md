<!-- bluewms-knowledge {"hook_code":"wcs_creation","contracts":["wcs_creation/4"],"approved":true} -->
# WCS已验证示例代码目录
完整精确试算与边界位于同一Wiki的domains/wcs/examples/<key>.md; 以下代码与这些页面逐字一致。示例ID均是稳定知识ID, 不是现场数据库ID。生成新草稿时须按本地合同建立本次测试。

## wcs.ready AI全部基础行直达
```python
if request["phase"] == "lines":
    result = []
    for candidate in candidates:
        action = "create"
        quantity = candidate["available_quantity"]
        reason = "满足搬运条件"
        result.append({"line_id": candidate["line_id"], "action": action, "quantity_basis": "confirmed" if request["operation"] == "incoming" else "reserved", "quantity": quantity, "group_key": candidate["line_key"], "source_ref": "line_source", "destination_ref": "line_destination", "reason": reason})
else:
    result = [request["base_task"]]
```
验证用例: 逐行决策, 任务编排。

## wcs.repeat AI同数据双作业
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
验证用例: 逐行决策, 任务编排。

## wcs.triple AI同数据三作业
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
    second = {"equipment_id": first["equipment_id"], "location_res_id": first["location_res_id"], "location_dest_id": first["location_dest_id"], "source_ref": first["source_ref"], "destination_ref": first["destination_ref"], "role": first["role"], "task_type": first["task_type"], "movement": "repeat", "dependency_step": 1, "dependency_event": "end", "dependency_point": first["dependency_point"], "reason": "同数据第二个程序"}
    result = [first, second, {"equipment_id": second["equipment_id"], "location_res_id": second["location_res_id"], "location_dest_id": second["location_dest_id"], "source_ref": second["source_ref"], "destination_ref": second["destination_ref"], "role": second["role"], "task_type": second["task_type"], "movement": "repeat", "dependency_step": 2, "dependency_event": second["dependency_event"], "dependency_point": second["dependency_point"], "reason": "同数据第三个程序"}]
```
验证用例: 逐行决策, 任务编排。

## wcs.filter AI逐行排除和等待
```python
if request["phase"] == "lines":
    result = []
    for candidate in candidates:
        action = "create"
        quantity = candidate["available_quantity"]
        reason = "满足搬运条件"
        if candidate["product_code"] == "MANUAL":
            action = "exclude"
            quantity = 0
            reason = "该商品人工搬运, 无需WCS"
        elif not candidate["picked"]:
            action = "wait"
            quantity = 0
            reason = "等待本行已拣选"
        result.append({"line_id": candidate["line_id"], "action": action, "quantity_basis": "confirmed" if request["operation"] == "incoming" else "reserved", "quantity": quantity, "group_key": candidate["line_key"], "source_ref": "line_source", "destination_ref": "line_destination", "reason": reason})
else:
    result = [request["base_task"]]
```
验证用例: 逐行决策, 任务编排, 条件等待, 人工搬运排除。

## wcs.all_picked AI整单全部拣选后搬运
```python
if request["phase"] == "lines":
    result = []
    for candidate in candidates:
        action = "create"
        quantity = candidate["available_quantity"]
        reason = "满足搬运条件"
        if not request["all_confirmed"]:
            action = "wait"
            quantity = 0
            reason = "等待整单全部拣选"
        result.append({"line_id": candidate["line_id"], "action": action, "quantity_basis": "confirmed" if request["operation"] == "incoming" else "reserved", "quantity": quantity, "group_key": candidate["line_key"], "source_ref": "line_source", "destination_ref": "line_destination", "reason": reason})
else:
    result = [request["base_task"]]
```
验证用例: 逐行决策, 任务编排, 条件等待。

## wcs.container AI容器货物组合
```python
if request["phase"] == "lines":
    result = []
    for candidate in candidates:
        action = "create"
        quantity = candidate["available_quantity"]
        reason = "满足搬运条件"
        result.append({"line_id": candidate["line_id"], "action": action, "quantity_basis": "confirmed" if request["operation"] == "incoming" else "reserved", "quantity": quantity, "group_key": candidate["carrier_key"], "source_ref": "line_source", "destination_ref": "line_destination", "reason": reason})
else:
    result = [request["base_task"]]
```
验证用例: 逐行决策, 任务编排。

## wcs.weight AI容器达到显式8重量单位阈值
```python
if request["phase"] == "lines":
    result = []
    for candidate in candidates:
        action = "create"
        quantity = candidate["available_quantity"]
        reason = "满足搬运条件"
        if not candidate["carrier_weight_complete"]:
            action = "wait"
            quantity = 0
            reason = "缺少产品重量基础数据"
        elif candidate["carrier_weight"] < 8:
            action = "wait"
            quantity = 0
            reason = "未达到显式重量阈值8"
        result.append({"line_id": candidate["line_id"], "action": action, "quantity_basis": "confirmed" if request["operation"] == "incoming" else "reserved", "quantity": quantity, "group_key": candidate["carrier_key"], "source_ref": "line_source", "destination_ref": "line_destination", "reason": reason})
else:
    result = [request["base_task"]]
```
验证用例: 逐行决策, 任务编排, 条件等待, 重量缺失等待。

## wcs.scope AI按单据库区点位搬运
```python
if request["phase"] == "lines":
    result = []
    for candidate in candidates:
        action = "create"
        quantity = candidate["available_quantity"]
        reason = "满足搬运条件"
        result.append({"line_id": candidate["line_id"], "action": action, "quantity_basis": "confirmed" if request["operation"] == "incoming" else "reserved", "quantity": quantity, "group_key": candidate["route_key"], "source_ref": "picking_source", "destination_ref": "picking_destination", "reason": reason})
else:
    result = [request["base_task"]]
```
验证用例: 逐行决策, 任务编排。

## wcs.relay AI同货接力
```python
if request["phase"] == "lines":
    result = []
    for candidate in candidates:
        action = "create"
        quantity = candidate["available_quantity"]
        reason = "满足搬运条件"
        result.append({"line_id": candidate["line_id"], "action": action, "quantity_basis": "confirmed" if request["operation"] == "incoming" else "reserved", "quantity": quantity, "group_key": candidate["carrier_key"], "source_ref": "line_source", "destination_ref": "handoff", "reason": reason})
else:
    first = request["base_task"]
    result = [first, {"equipment_id": request["secondary_equipment_id"], "location_res_id": request["positions"]["handoff"], "location_dest_id": request["positions"]["line_destination"], "source_ref": "handoff", "destination_ref": "line_destination", "role": first["role"], "task_type": request["secondary_task_type"], "movement": "relay", "dependency_step": 1, "dependency_event": first["dependency_event"], "dependency_point": first["dependency_point"], "reason": "交接后的第二段"}]
```
验证用例: 逐行决策, 任务编排。

## wcs.empty AI货物和空载具配合
```python
if request["phase"] == "lines":
    result = []
    for candidate in candidates:
        action = "create"
        quantity = candidate["available_quantity"]
        reason = "满足搬运条件"
        result.append({"line_id": candidate["line_id"], "action": action, "quantity_basis": "confirmed" if request["operation"] == "incoming" else "reserved", "quantity": quantity, "group_key": candidate["carrier_key"], "source_ref": "line_source", "destination_ref": "line_destination", "reason": reason})
else:
    first = request["base_task"]
    result = [first, {"equipment_id": first["equipment_id"], "location_res_id": request["positions"]["line_destination"], "location_dest_id": request["positions"]["line_source"], "source_ref": "line_destination", "destination_ref": "line_source", "role": "empty_return", "task_type": first["task_type"], "movement": "empty", "dependency_step": 1, "dependency_event": "point_or_take", "dependency_point": request["position_details"]["line_source"]["point"], "reason": "取货后回空"}]
```
验证用例: 逐行决策, 任务编排。
