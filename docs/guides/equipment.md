# 设备类别接口

适用模块: `blue_wcs_protocol`；合同: `device_protocol/1`，可选 headers 需 schema_version=2。更新: 2026-10-26。

## 设置步骤

1. WCS → 设备类别，新建并填写名称、公司和负责人。新类别统一 HTTP/JSON。
2. 人工填写地址、相对任务路径、App Key/Token、App Secret、回调凭据；设备实例从设备页建立并选择类别，连接共用类别配置。
3. 编辑协议资产或打开 AI 浮窗。需求、代码、试算、版本、发布历史和审计页共用资产流程；代码覆盖 request/response/callback 三阶段，验证后人工发布。
4. 在隔离环境试运行，再按厂商协议完成现场联调。AI 不改地址、密钥、Task、设备或人工能力开关。

Token 空则不附默认认证，有值默认 Bearer。特殊请求头由代码输出 `$app_key`/`$app_secret` 占位符，本地服务代入；不能覆盖传输控制头或注入换行。回调凭据为空不要求 Token，有值必须 Bearer。

通用回调: `/blue_wcs/v1/categories/<类别编号>/callback`。系统先从 JSON 值中匹配唯一真实任务号，再运行该任务固定的协议版本；任务号匹配不能代替来源认证。首期处理单条最终完成回调，不以容器编码代替任务号。

## 位置与状态

- `subposition` 只更新当前任务关联包裹/载具的细点，不等同于库存库位。
- `destination_code` 仅在同公司、当前作业仓库内唯一匹配已有内部库位；核对容量、托盘、重量、混放、冻结及实际数量后，才同步实际位置和未完成库存明细。
- 保留原计划、实际位置和原始回报；部分数量、多计划共行、中间接力、后续路线不确定、未知/重码或原生约束不满足时待核对。
- 位置更新与完成事件在同一受控事务内；重复回报不重复写入或记账，不改已完成库存历史。

每张任务固定协议版本和准确输入；在途任务不能随意更换连接或类别。先持久化发送，再处理 HTTP；未知结果不自动认作完成。代码回滚不撤销物理移动。

## 已有协议及扩展

TUSK 下发路径 `/rpc/createTask`，旧 `/api/blue_wcs_tusk/feedbackTask` 保留兼容，最终完成回调不另加开关。HIK 既有认证保持原样。M4/Mita/Modula/WES 文档为协议参考，不据此宣称批量回调、取消、解绑或盘点已实现。

准确语法、回调结构、TUSK 案例及厂商参考见 [设备知识](https://gitee.com/jch100322/bluewms-wiki/blob/master/wiki/domains/equipment/specification.md)。WES 专用模块已退役，旧实例先按 [升级说明](../operations/upgrades.md) 卸载。
