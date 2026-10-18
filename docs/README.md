# BlueWMS20 开发文档

本仓库管理开发模块、Docker Compose、公开工程说明、知识来源、开发规划和交付记录。供 AI 使用的批准通用示例、业务知识与 Skill 正文集中在云端 TencentDB-Agent-Memory 发布／检索；Git 不充当客户本地私有知识库。

- [Odoo AI 代码生成知识库：生成规则、五类接口规范与示例](wiki/README.md)
- [维护者：TencentDB-Agent-Memory 配置](architecture/tencent-memory-configuration.md)
- [维护者：AI 生成知识的维护与发布](architecture/ai-generation-knowledge-maintenance.md)
- [维护者：原生 Wiki 检索与五类知识库规划](architecture/native-wiki-retrieval-plan.md)
- [六库知识发布与真实模型问答验收](wiki-publication/native-wiki-20261018.md)
- [开发规划](planning/bluewms20-development-plan.md)
- [模块分类与架构](planning/bluewms20-module-architecture.md)
- [迁移选择](planning/bluewms20-migration-selection.md)
- [原生上架规则与增强策略](migrations/putaway-rule-binding-20.md)
- [上架 AI 云端知识接入与本地接口调整](migrations/putaway-cloud-knowledge-20.md)
- [上架 AI 聊天浮窗](migrations/putaway-ai-floating-chat-20.md)
- [WCS 迁移交付](migrations/wcs-20.md)
- [WCS 迁移规划](planning/bluewms20-wcs-migration.md)
- [MuK AI 中文翻译](third-party/muk-ai-zh-2026-10-13.md)
- [Docker 开发环境](../docker/README.md)
- [多台 Mac 的 Git 同步](git-sync.md)

`docs/planning/` 收录原 `odoo/bluewms20-doc` 的规划文件。以后维护、同步规划时修改这里；仓库外的旧目录作为历史副本，Git 不会同步那个目录。

`wiki/` 仅维护供 Odoo 内 AI 生成增强代码使用的通用规则、五类接口规范和示例。项目源码开发、Git、服务器配置、知识发布操作和历史记录不放入这个生成知识库。人工维护方法见 [维护约定](architecture/ai-generation-knowledge-maintenance.md)，发布来源见 [映射](architecture/ai-generation-knowledge-publication-map.json)。

第三方模块来源、许可证、版本和验证记录在 `third-party/`；自研模块迁移、测试边界和源码摘要在 `migrations/`。

业务数据库、附件、登录密码和私有运行配置放在本机用户目录及 Docker 数据卷中，不能提交到公开 GitHub 仓库。

- [宝蓝 AI 云端连接交付](third-party/blue-ai-client-install-2026-10-13.md)：Chat Completions、按用户绑定、自动团队/Agent/任务选择与代码草稿闭环。
