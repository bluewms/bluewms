# BlueWMS 可编辑设备协议

Odoo 20 设备类别级 HTTP／JSON 协议资产。新增厂家接口通过类别及代码版本交付；不为每个常规 HTTP 厂家再安装模块。

- WCS → 设备类别 → 新建类别自动采用统一 HTTP／JSON，保留现有连接字段，所属设备统一使用类别参数。
- 类别页与其他 AI 入口统一提供需求、可编辑代码、试算、代码版本、发布历史、审计记录六个页签，以及 AI 浮窗、验证、人工发布与回滚；设备从设备页面维护。
- `device_protocol/1` 只转换下发报文、响应与单条最终完成回调，固定服务执行网络、状态和受限位置回写。
- 任务固定协议发布版本与输入；存在未结束任务时冻结连接和关键范围，重复回报幂等。
- 包裹子位置和当前作业仓库内的实际库存库位分别处理。实际库位通过原生容量、托盘、重量、混放、冻结检查后同步库存明细；原计划位置和回报保留。
- 按用户确认保留旧 TUSK 无附加 Token 回调；填写回调凭据则验证 Bearer。原有 HIK 认证不变；WES 专用模块已退役，协议见[Wiki 参考](https://gitee.com/jch100322/bluewms-wiki/blob/master/wiki/domains/equipment/reference/wes-vzf.md)。

启用后先人工填写设备地址及相对任务路径。TUSK 下发路径 `/rpc/createTask`，兼容回调 `/api/blue_wcs_tusk/feedbackTask`；普通类别回调 `/blue_wcs/v1/categories/<category_id>/callback`。不再设置接口方式、认证模式、任务号字段或位置开关。Token 留空不附加默认认证，填写则默认 Bearer；特殊请求头由代码使用 $app_key／$app_secret 占位符，本地代入凭据，密钥不传给 AI。

代码和试算不会自动载入本地标准示例。AI 通过原生 Wiki 获取规范与案例，运行正式代码不依赖云端知识文件。测试数据仅在 tests/ 中使用，不在安装数据中发布业务策略。

首期支持 TUSK 风格的单条 JSON 回调；M4、Mita、Modula 是云端协议参考，完整批量反馈及取消／关闭／解绑等动作仍待适配。部分数量或多计划共享库存明细的目的库位变更进入人工核对，不直接改整行或历史库存。

使用与升级见 [设备接口交付](../docs/guides/equipment.md)，AI 资料见 [设备 Wiki](https://gitee.com/jch100322/bluewms-wiki/blob/master/wiki/domains/equipment/specification.md)。模拟及报文回归不代表真实厂商现场已验收。
