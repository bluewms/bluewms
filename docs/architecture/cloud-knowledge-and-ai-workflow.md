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

远端2026-10-17基线只有上架具备AI草稿闭环; 本地2026-10-18的WCS增量见下节, ERP/设备/条码仍为planned.初次文件整理未自动发布。2026-10-18 用户授权后，六个 Wiki 的 29 份资料已发布并逐页核对；Odoo 页面内正式工具路径仍保持原状。

## 当前代码与兼容路径

WCS /4 已完成全部行增强、同数据双／多程序及库存一次记账，与上架共用浮窗、会话绑定和草稿保护，使用“WCS生成策略”Task。真实工具返回完整 contract_schema 及兼容别名，提交前复核基础版本和草稿摘要；人工发布，固定计划继续使用原版本。

页面中的 `blue_read_code_asset` 当前仍从固定 Skill bridge 读取批准正文：上架要求 01／03／04，WCS 要求独立 01／06／07 及 Wiki 来源。云端旧 Skill v4 保持原样，没有补写 06／07，因此现有 WCS 兼容分支仍会报告缺少 Skill 正文，不能把新 Wiki 发布成功当作该代码路径已打通。已有正式策略和无 AI 基础路径仍在本地执行。

生产 WCS 的基础接口定义不保存示例正文；客户修改、/1–/3 历史和固定计划保留。示例与说明的维护来源为[分篇 Wiki](../wiki/domains/wcs/specification.md)。[旧离线 Skill 候选包](../wiki-publication/README.md)仅作兼容追溯，不是新 Wiki 发布指令。原生 Wiki 切换需同时修改上架和 WCS 的工具、引用与提交保护，详见[接入规划](native-wiki-retrieval-plan.md)。

## 2026-10-18 原生 Wiki 发布与验收

维护来源已核对，13 个案例、34 条声明试算及隔离库 219 项模块测试通过。六库发布与真实模型问答单独见[验收记录](../wiki-publication/native-wiki-20261018.md)；当前正式 Odoo 页面内的原生工具切换仍待后续接入。
