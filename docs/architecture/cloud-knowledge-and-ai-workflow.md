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

- [TencentDB-Agent-Memory 配置](tencent-memory-configuration.md)：服务、团队／Agent／Task、共享配置。
- [知识维护与发布](ai-generation-knowledge-maintenance.md)：人工新增、审阅、发布及失效流程。
- [发布映射](ai-generation-knowledge-publication-map.json)：生成来源与兼容云端资源的对应。
- [2026-10-16 历史记录](../third-party/tencent-memory-configuration-2026-10-16.md)：配置纠正、会话证据与历史决策。

远端2026-10-17基线只有上架具备AI草稿闭环; 本地2026-10-18的WCS增量见下节, ERP/设备/条码仍为planned.文件整理没有自动替换云端正文，也未改变现有 Odoo 工具读取路径。

## 2026-10-18 本地WCS /4整合增量

远端PR #4的上架云端知识、Task身份路由、草稿参考版本记录与聊天浮窗保留。WCS /4已完成全部行增强、同数据双／多程序及库存一次记账；与上架共用浮窗和会话绑定保护，使用“WCS生成策略”Task。工具返回完整contract_schema及兼容别名，按hook实际读取批准云端正文，WCS固定01/06/07与真实Wiki ID、版本，上架保持01/03/04。成功读取前不修改AI草稿，无本地示例或跨hook回退。

生产WCS只保留无示例正文的基础接口定义；原18个出厂定义归档并按摘要清理原始正文，客户修改与策略历史保留。例子与配置说明按主题存入[Wiki源文件](../wiki/domains/wcs/specification.md)，[离线发布包](../wiki-publication/wcs-v4/README-用户最后写入.md)供用户最后写入既有Wiki/Skill，包含原上架资源及WCS新增资源。当前仅实际只读验证了上架Skill v4，WCS云端发布待用户完成；本轮未写云端。

/1-/3历史、人工权限边界、固定计划与报文继续保留，不自动改绑或发布。其他ERP／设备／条码入口仍planned。

后续架构意图：用户拟在另一台电脑用Memory Hub原生Wiki检索替代额外Skill副本。本次仅交付现有代码，尚未实现或验证Odoo会话的原生Wiki自动检索／注入。当前上架与WCS仍强制Skill bridge，详见[跨电脑交接](../migrations/wcs-v4-handoff.md)。
