# TencentDB-Agent-Memory 配置说明

本文属于工程维护资料，供管理员配置和排错使用，不属于 Odoo AI 代码生成 Wiki，也不加入其云端正文发布清单。生成规范与案例见 [Odoo AI 代码生成知识库](../wiki/README.md)。

状态：维护说明，含 2026-10-16 验证快照。整理：2026-10-17。实际资源状态以服务端当前记录为准；文档整理没有重新执行服务器健康检查或云端发布。

## 服务与私有配置

| 服务 | 2026-10-16 现场镜像 | 职责 |
|---|---|---|
| `tdai-memory-hub` | `agentmemory/memory-hub:1.0.2` | Hub 面板及 Knowledge 正文服务 |
| `tdai-memory-core` | `agentmemory/memory-core:1.0.2` | 用户／团队／Agent／资产元数据、记忆与 Skill |
| `tdai-proxy` | `agentmemory/memory-proxy:1.0.2` | 模型代理、身份初始化、上下文注入及 Skill bridge |

现场内部端口为 Hub 8125、Knowledge 8424、Core 8420、Proxy 8096；对外入口、白名单、凭据以私有部署配置为准。Hub／Knowledge 数据位于 `tdai-panel-data` 卷的 `/data/knowledge`；Core 数据位于 `tdai-memory-core-data` 卷的 `/data/tdai-memory`。修改前备份 SQLite 的已提交数据（含 WAL）、知识文件、画像及配置。

运维 API 和 Odoo 工具分别授权。Core `/v3/meta/*`、`/v3/memory-prompt/*`、`/v3/skill/*`、`/v3/core/read`、`/v3/core/write` 与 Knowledge `/v3/wiki/*` 是管理／服务接口，不代表模型可以调用。管理 Key 不放进提示词或业务用户配置。

## 团队、Agent 与 Task

一个项目使用 `odooAI` 团队。现有三位用户及各自 Agent 保持原名称和身份；每个 Odoo 用户配置自己的业务用户 Key 和准确 Agent 名称。默认每用户初始化一个 Agent，不表示只能有一个 Agent；确有角色分工再增加。

| 业务 Task | hook | 当前 Odoo AI 接入 |
|---|---|---|
| 上架策略 | `putaway_policy` | 新上架代码会话使用 |
| ERP接口 | `erp_mapping` | 已有云端分类，AI 入口待实现 |
| WCS生成策略 | `wcs_creation` | 同上；现有 WCS 业务能力另行验收 |
| 设备连接接口 | `device_protocol` | AI 入口待实现 |
| 条码扫描策略 | `barcode_policy` | AI 入口待实现 |
| 日常任务 | 兼容任务 | 普通聊天、测试连接及升级前旧会话保留 |

这些 Task 共享批准的项目知识，不为每类业务复制团队或人格。Task 是协作分类，不是隐私边界；该版本 L2／L3 路径按 team + agent 隔离。跨客户或严格权限边界使用独立团队、ACL 或等价隔离。

## Wiki 与 Skill

项目 Wiki 名称为 **BlueWMS20 Project Knowledge and Approved Policy Examples**。原配置纠正时验收为 ready／版本 3；后续公开配置文档同步的 2026-10-16 回执记录为 ready／版本 5，项目 Skill 为版本 4。它们是不同时间的快照，不能把旧版本号当作长期目标。

| 共享 Skill | 用途 |
|---|---|
| `odoo-guidelines` | Odoo 模块／后端开发规范 |
| `odoo-web-guidelines` | JS／Owl／SCSS 开发规范 |
| `odoo-security` | Odoo 权限和安全审查 |
| `odoo-review` | Odoo 源码变更审查 |
| `bluewms-policy-authoring` | 五类入口规划、受限策略和批准示例 |

官方 Skill 保留原文、引用文件、源提交和许可证；源码规范不赋予运行时策略 ORM 或 shell 权限。开发机器的 Codex／CodeBuddy 安装与云端分发分别更新，不自动互相同步。

共享资产由团队可读，并显式绑定目标 Agent；原私有 Skill 和个人聊天不自动公开。配置完成后分别验证不同成员的可访问列表、正文读取和私有记忆隔离，不能只看面板上是否出现名称。

当前 Odoo 读取固定项目 Skill 的三个资源；没有直接查询任意 Wiki／Code Graph 的工具。正文与来源文件对应关系见 [发布映射](ai-generation-knowledge-publication-map.json)。

## 记忆与知识质量

L1／L2／L3 提炼按团队使用事实规则：区分已确认事实、测试、规划和推测，不由测试句构造人格；不把实例记录 ID 当跨机器稳定标识。原始聊天默认私有，有价值的经验先审阅／脱敏，再发布团队知识。

原 Wiki 自动加工曾出现 FILE 块缺少 `path="..."` 的解析问题；维护者核对原文后锁定批准页。后续更新须保留准确代码，自动草稿先作候选，不能直接覆盖批准案例。详细证据留在 [历史记录](../third-party/tencent-memory-configuration-2026-10-16.md)。

## 日常变更与排错

修改知识／绑定／画像前保留备份和审计，更新后记录来源提交、云端版本及摘要。新会话读取新配置；旧代理会话可能保留首次版本或缓存。

先核对服务健康、实际镜像、用户／Agent／Task、绑定与可见性、ready／批准状态、资源路径、大小和工具是否存在。错误说明不要回显服务正文、Key 或客户数据。部署与身份细节放私有运维记录，长期通用知识只留可复用的配置方法。
