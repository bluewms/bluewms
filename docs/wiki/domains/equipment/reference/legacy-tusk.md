# TUSK 旧协议参考

来源：bluewms19 7d77ae7，blue_wcs_tusk/models/blue_wcs_request.py 与 contorllers/main.py。只保留协议事实，真实地址、任务及设备编号未收录。

下发 POST `/rpc/createTask`，JSON 为 taskId、targets 起终点数组、configId 任务模板。旧实现以 HTTP 200 且 msg=success 确认接受；其他结果保守按 unknown 处理，不盲目重发。

回调 POST `/api/blue_wcs_tusk/feedbackTask`，字段 taskId、deviceId、targetPoint。用户确认只在最终完成时回报，旧方式无附加 Token。成功应答 `{"code": 200, "msg": "success"}`。已配置厂商设备编码时须匹配 deviceId。细点写子位置还是匹配库存库位，由发布代码选择，并由固定服务按当前作业仓库和原生规则复核。

旧模块还提供 `/rpc/cancelTask`，当前不开放取消。旧直接完成任务的 ORM 逻辑由固定状态机替代。

准确代码见 [子位置](../examples/tusk-subposition.md) 与 [实际库位](../examples/tusk-destination.md)。
