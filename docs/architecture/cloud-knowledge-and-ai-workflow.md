# Odoo AI 生成知识与维护资料入口

更新：2026-10-18。原综合文档按读者拆开：`docs/wiki/` 专供 Odoo 内的 AI 助手生成增强代码；工程维护和服务器资料留在 Wiki 之外。本页保留两类入口导航。

## Odoo AI 代码生成知识

| 内容 | 新位置 |
|---|---|
| 生成任务、真实输入、输出和能力边界 | [AI 生成通用规则](../wiki/basics/overview.md) |
| AI 读取、提交、验证草稿的步骤 | [工具规则](../wiki/basics/ai-generation-workflow.md) |
| 上架规范和三个已验证示例 | [上架规范](../wiki/domains/putaway/specification.md) · [示例目录](../wiki/domains/putaway/examples/README.md) |
| ERP、WCS、设备和条码 AI 规范／需求示例 | [五类入口目录](../wiki/README.md#五类-ai-入口) |
## 维护者工程资料

以下内容不作为 AI 生成知识发布：

- [原生 Wiki 检索与五类知识库规划](native-wiki-retrieval-plan.md)：最新 WCS /4 基线、标准工具、分库路由、批准与切换次序。

- [TencentDB-Agent-Memory 配置](tencent-memory-configuration.md)：服务、团队／Agent／Task、共享配置。
- [知识维护与发布](ai-generation-knowledge-maintenance.md)：人工新增、审阅、发布及失效流程。
- [发布映射](ai-generation-knowledge-publication-map.json)：生成来源与兼容云端资源的对应。
- [2026-10-16 历史记录](../third-party/tencent-memory-configuration-2026-10-16.md)：配置纠正、会话证据与历史决策。

远端2026-10-17基线只有上架具备AI草稿闭环; 本地2026-10-18的WCS增量见下节, ERP/设备/条码仍为planned.初次文件整理未自动发布。2026-10-18 用户授权后，六个 Wiki 的 29 份资料已发布并逐页核对；初次发布时 Odoo 路径保持原状，后续正式接入另见下节。

## 当前 Odoo 接入

上架与 WCS /4 的新会话使用腾讯原生 Wiki：读取绑定资产和真实合同 → 搜索通用及本领域知识 → 完整读页 → 提交前复核来源 → 保存并验证草稿 → 用户人工发布。资产与正式版本只保存真实引用、版本及摘要，不另建本地示例库；聊天记录仍按 MuK 机制保存实际工具输出供回放，不充当知识兜底。详见[原生 Wiki 与五类 Task 接入](../migrations/native-wiki-runtime-20.md)。

云端增加与模型同域的受限只读 HTTPS 通道，使用当前业务 Key 验证 Core ACL、Agent 绑定、批准／ready 状态及合同，再转发标准 search／read_page。管理凭据仅留在云端；不使用 Skill 文件中转，不重做检索。

五类入口分别绑定同名 Task，模型请求显式携带已验证的真实预选身份，不依赖代理碰巧弹出 Task 表单。ERP／设备／条码目前只开放知识沟通，不能因有 Task 或 Wiki 就生成可执行代码。

旧 Skill v4、已发布策略及 /1–/3 历史保留，旧代码会话须从资产页重开。新知识来源为 tencent_wiki；旧不可变代码版本的来源记录不重写。库存与设备业务仍按本地固定版本确定性执行。

## 2026-10-18 原生 Wiki 发布与验收

维护来源已核对，13 个案例、34 条声明试算及隔离库 219 项模块测试通过。六库发布与真实模型问答单独见[验收记录](../wiki-publication/native-wiki-20261018.md)；正式工具切换及真实 Task 路由见[接入记录](../migrations/native-wiki-runtime-20.md)。
