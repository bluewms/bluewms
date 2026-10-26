# BlueWMS WCS 基础

Odoo 20 的设备类别、设备、作业团队、作业阶段、固定计划、货物明细、WCS作业和不可变回执. 界面沿用 ZF 原 WCS 的主要菜单、表单字段和库存关联, 依赖库存基础/硬约束, 不依赖 AI.

任务先持久保存，再由独立队列事务下发。发送中断或不确定响应进入待核对，不自动重发。使用稳定任务号、公司权限和受保护的流程方法；模拟设备动作仅限库存管理员。

原作业类型默认支持单作业、入库双作业、出库双作业, 增加同货两段接力. 创建配置直接生成任务起终点和依赖, 不再使用独立线路配置; 旧线路模型仅保留历史数据. 接力必须等待前段完成; 空载具配合保留原take/point触发及完成事件兜底. 空载具任务不携带商品数量, 载具身份需由对应设备任务模板/站点能力确定.

海康国标任务可配置完整下发 URL、App Key/Secret，默认验证 TLS，不复制旧默认凭据。JSON 网关响应合同为 `{"accepted": true}`。厂家接口统一通过 blue_wcs_protocol 配置；WES VZF 协议见[Wiki 参考](https://gitee.com/jch100322/bluewms-wiki/blob/master/wiki/domains/equipment/reference/wes-vzf.md)。

标准回执：POST `/blue_wcs/v1/devices/<device_id>/events`，请求头 `Authorization: Bearer <callback_token>`。正文包含 `task_id`、`event_id`、`event`，可选 `point` 和 `actual_destination`。支持 start/take/point/end/outbin/notifyPodArr，任务必须已发送；重复事件幂等，错用事件号或实际落点不一致拒绝。

兼容海康回调路径 `/api/blue_wcs_hik/reporter/task` 同样要求设备回调凭据；现场设备不能添加该认证头时，需要经过认证的协议网关，不开放无认证回调。

本次是向新 Odoo 20 库迁移功能，不自动导入 Odoo 19 在途任务或设备现场状态。部署配置、真实协议验证和已接受任务取消需单独核对。已发送计划不能通过“取消未发送计划”释放数量；不确定结果提供带核对依据的恢复入口。
