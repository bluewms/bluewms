# 设备协议 AI 接入与位置回写

日期：2026-10-18。模块：`blue_wcs_protocol` 20.0.1.0.0；配套 `blue_wcs_base` 20.0.1.4.0、`blue_wcs_extension` 20.0.1.5.0、`blue_ai_client` 20.0.1.5.0。实际部署及测试以同名 validation.json 为准。

## 使用入口

WCS → 设备类别，人工新增类别并选择“可编辑 HTTP 接口”。原有适配方式、公司、负责人、IP、任务路径、Key／Secret、回调凭据继续人工维护，所属设备统一使用类别连接。类别页移除直接新增设备的明细，保留查看设备和数量；设备从设备页面添加并选择类别。

类别保存后创建空的协议资产，提供 AI 生成／修改浮窗、代码和需求、报文试算／验证、发布、新建草稿、回滚及历史。三个阶段采用独立 `device_protocol/1`，与 WCS 创建 /4 分开；AI 只能保存、验证草稿，不能发布或改人工连接。

## TUSK 与其他接口

人工填写 TUSK 的 `/rpc/createTask`，下发报文为 taskId／targets／configId，HTTP 200 且 msg=success 确认接受。用户确认最终完成回调 taskId／deviceId／targetPoint 保留旧 `/api/blue_wcs_tusk/feedbackTask` 路径、不要求新增 Token，请在类别启用此兼容方式。已有 HIK／WES 回调认证不变。

通用类别还可使用 `/blue_wcs/v1/categories/<类别编号>/callback`，人工指定任务号字段及兼容／Bearer 模式。首期仅单条 JSON 最终完成回调；旧 M4、Mita、Modula 资料按厂家分开存入设备 Wiki 参考目录，批量关联／应答、关闭、取消、解绑、盘点等未因此自动实现。

## 位置回写

- 包裹子位置：AI 解析细点，固定程序只写当前任务关联的包裹／载具。配置了容量位置时须唯一匹配空闲位置，包含设备完成但库存尚未入账的占用。
- 实际库存库位：人工启用并指定允许目的库区，AI 只输出编码；固定程序按同公司、批准库区、条码／AGV 编码唯一匹配既有内部库位，检查原生容量、托盘、重量、混放及冻结后，同步 WCS 实际目的位置与对应库存明细。
- 原计划位置、实际位置、原始回调及协议版本同时保留。部分数量、多计划共用库存行、中间接力、未知／重复库位、越界和原生约束不满足时待核对；不自动新建库位或改已经完成的库存历史。
- 位置写回与事件确认在同一事务内。重复完成回报不重复记账，库存验证后仍保留已批准子位置。错误回调不确认完成，也不盲目重新下发。

## 发布与运行

每张任务在创建时固定协议版本和报文输入；类别发布新代码只影响后续任务。在途任务禁止更换类别连接、设备绑定、回调定位字段和允许范围。已发送任务必须经过该固定协议解析，不能用普通设备回执绕过。

真实发送仍使用现有持久队列：先落库声明发送，再进行 HTTP，再记录结果。超时／中断保持待核对。报文试算只计算 JSON，不连接设备；正式发布的转换代码在本地执行，不逐次请求模型。

## 安装与跨机器升级

先备份数据库与 filestore，并核对库存、草稿、发布、类别连接及在途任务。已安装模块按实际清单升级，新协议模块需显式安装：

```sh
docker compose -f docker/compose.yaml stop odoo
docker compose -f docker/compose.yaml -f docker/compose.test.yaml run --rm --no-deps odoo odoo -c /etc/odoo/odoo.conf -d 本机数据库名 -u blue_ai_client,blue_wcs_base,blue_wcs_extension -i blue_wcs_protocol --stop-after-init --no-http --max-cron-threads=0
docker compose -f docker/compose.yaml up -d odoo
```

上述 -u 仅保留本机已安装模块；新库或未启用 WCS 创建扩展的实例按依赖安装，不自动导入旧 19 数据或建立真实厂家类别。各开发机仍用自己的数据库、Key、Agent 和连接配置。

云端共用原有设备 Task 与设备 Wiki，不创建额外 Task 或 Skill。设备合同与批准规范可用后才开放生成，Git 合并不自动部署网关／发布 Wiki。资料维护见[发布流程](../architecture/ai-generation-knowledge-maintenance.md)，准确生成资料见[设备规范](../wiki/domains/equipment/specification.md)。

本轮不向真实设备发送任务。报文、模型及模拟发送验证与真实设备现场验收分别记录。
