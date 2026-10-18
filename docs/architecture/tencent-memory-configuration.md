# TencentDB-Agent-Memory 配置

更新：2026-10-18。本文供管理员维护，不发布到 Odoo AI Wiki。业务流程见[AI 架构](cloud-knowledge-and-ai-workflow.md)，部署只读通道见[cloud/README](../../cloud/README.md)。

## 服务与凭据

现场已验证的 Tencent Hub／Core／Proxy 基线为 1.0.2。实际镜像、地址、访问限制、资源 ID 和秘密以部署记录为准，不复制到公开仓库。

| 服务 | 职责及内部接口 |
|---|---|
| Hub／Knowledge | 面板 8125、知识服务 8424；索引和标准 Wiki 工具 |
| Core | 8420；用户、团队、Agent、Task、资产元数据、ACL、记忆与 Skill |
| Proxy | 8096；模型代理、会话身份、上下文注入与记忆调用 |
| BlueWMS 只读通道 | 仅监听回环 8430，经模型原 HTTPS 域的 `/odoo-wiki/v1/` 转发 |

Hub／Knowledge 的 `tdai-panel-data` 卷挂载到 `/data/knowledge`；Core 的持久卷位于 `/data/tdai-memory`。备份 SQLite 时包含已提交的 WAL 数据，并实际检查知识目录归档。备份存在不等于恢复演练完成。

Odoo 只保存当前用户的业务 Key 与准确 Agent 名称。通道服务凭据只在云端专用账号可读的私有文件中；不放在 Odoo、提示词、浏览器、公开示例或 Git。知识管理／写入接口与运行时模型工具分别授权。

## 用户、团队和 Task

当前项目使用一个 `odooAI` 团队，各用户保留自己的 Key 与 Agent。每用户默认一个 Agent 不代表平台只能创建一个；新增角色或客户项目先确定权限边界。

| hook | 运行中的 Task 名称 | 当前能力 |
|---|---|---|
| putaway_policy | 上架策略 | 绑定资产的生成／验证，以及只读知识沟通 |
| wcs_creation | WCS生成策略 | /4 生成／验证，以及只读知识沟通 |
| erp_mapping | ERP接口 | 仅知识沟通，执行合同 planned |
| device_protocol | 设备连接接口 | 仅知识沟通，执行合同 planned |
| barcode_policy | 条码扫描策略 | 仅知识沟通，执行合同 planned |
| 普通聊天 | 日常任务 | 普通聊天与测试连接，不作为业务回退 |

业务 Task 须归当前用户所有、处于运行状态并关联其 Agent。代理只有一个候选 Task 时会自动选中，因此不能仅凭本地任务名称或“没有弹选择框”认定路由正确。新客户端使用已验证的实际预选 ID，并固定云端绑定；更改后需重新打开会话。

Task 是业务分类，不是跨客户隐私边界。该部署记忆隔离不能仅凭 Task 名称保证；严格隔离使用独立团队、ACL 或等价机制。

## 六个项目 Wiki

| 逻辑范围 | 现有名称 | 用途／状态 |
|---|---|---|
| common | bluewms-odoo | 通用规则、工具步骤、案例格式 |
| putaway | Odoo-AI-上架策略 | 上架规范及三个准确案例 |
| wcs | Odoo-AI-WCS任务生成 | /4 规范、合同核对及十个准确案例 |
| erp | Odoo-AI-ERP接口 | planned 需求资料 |
| equipment | Odoo-AI-设备接口 | planned 需求资料 |
| barcode | Odoo-AI-条码策略 | planned 需求资料 |

当前六库均有索引，通用／上架／WCS 资产已批准；后三类仍为 candidate，`generation_ready=false`。资源目录只说明可发现，不等于读过正文，更不等于获得生成／发布权限。

资料设置团队可读并显式绑定目标 Agent。通道按固定逻辑清单检查用户 ACL、团队、Agent 绑定、用途、合同、批准页、索引状态和真实摘要；不接受任意 Wiki ID。Wiki 版本为字符串，不能套用旧 Skill 的整数版本规则。

## 新用户接入检查

1. 建立用户、项目成员和准确 Agent 身份，生成该用户业务 Key。
2. 绑定通用＋五类 Wiki，核对可见性和 Core ACL，不公开其私有记忆。
3. 为该用户建立或核对五个同名运行中 Task，并关联其 Agent；保留日常任务给普通聊天。
4. 在 Odoo 用户连接填写业务 Key／Agent；不填写服务管理 Key。
5. 从新会话验证标准搜索、完整读页和真实 Task 注册；缺少权限／Task／知识批准时应明确失败。

## 记忆和 Skill 的分工

个人聊天默认私有；测试问句不推断职业、性格或长期偏好。记忆提炼区分已确认事实、测试、规划和推测，通用经验先脱敏／审阅，再加入团队知识。跨 Mac 的数据库记录 ID 不能作为稳定业务身份。

开发机的四个 Odoo 开发／审查 Skill 服务于源码开发；是否在云端分发与本地安装分开维护。它们不能给运行时策略增加 ORM、shell 或设备权限。旧 `bluewms-policy-authoring` Skill 留作旧客户端兼容，新 Odoo 已不通过它中转案例，也不再维护一份离线 Skill 正文包。

## 变更与排错

先检查实际服务健康、用户／Agent／Task、固定绑定、Core ACL、ready／批准状态、当前合同和摘要，不能仅检查 HTTP 200。draft 索引可能返回空结果，单个候选 Task 也可能被自动选中。

改知识、绑定、Task 或记忆规则前保留可恢复备份及回执；新会话验证新状态，旧会话不得静默混用版本。自动 LLM 加工不能改写准确代码；使用[知识发布流程](ai-generation-knowledge-maintenance.md)建立锁定页并读回核对。错误日志和公开说明不回显 Key、上游正文或客户数据。
