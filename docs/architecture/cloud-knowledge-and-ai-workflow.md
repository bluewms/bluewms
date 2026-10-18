# Odoo AI 生成知识与维护资料入口

更新：2026-10-17。原综合文档按读者拆开：`docs/wiki/` 专供 Odoo 内的 AI 助手生成增强代码；工程维护和服务器资料留在 Wiki 之外。本页保留两类入口导航。

## Odoo AI 代码生成知识

| 内容 | 新位置 |
|---|---|
| 生成任务、真实输入、输出和能力边界 | [AI 生成通用规则](../wiki/basics/overview.md) |
| AI 读取、提交、验证草稿的步骤 | [工具规则](../wiki/basics/ai-generation-workflow.md) |
| 上架规范和三个已验证示例 | [上架规范](../wiki/domains/putaway/specification.md) · [示例目录](../wiki/domains/putaway/examples/README.md) |
| ERP、WCS、设备和条码 AI 规范／需求示例 | [五类入口目录](../wiki/README.md#五类-ai-入口) |
## 维护者工程资料

以下内容不作为 AI 生成知识发布：

- [TencentDB-Agent-Memory 配置](tencent-memory-configuration.md)：服务、团队／Agent／Task、共享配置。
- [知识维护与发布](ai-generation-knowledge-maintenance.md)：人工新增、审阅、发布及失效流程。
- [发布映射](ai-generation-knowledge-publication-map.json)：生成来源与兼容云端资源的对应。
- [2026-10-16 历史记录](../third-party/tencent-memory-configuration-2026-10-16.md)：配置纠正、会话证据与历史决策。

当前只有上架具备 AI 草稿闭环，其他四类规范／需求示例明确标为 planned。文件整理没有自动替换云端正文，也未改变现有 Odoo 工具读取路径。
