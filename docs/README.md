# BlueWMS20 开发文档

本仓库管理开发模块、Docker Compose、公开工程说明、知识来源、开发规划和交付记录。供 AI 使用的批准通用示例、业务知识与 Skill 正文集中在云端 TencentDB-Agent-Memory 发布／检索；Git 不充当客户本地私有知识库。

- [云端知识、Tencent 配置与今日 AI 工作流（2026-10-16）](architecture/cloud-knowledge-and-ai-workflow.md)
- [开发规划](planning/bluewms20-development-plan.md)
- [模块分类与架构](planning/bluewms20-module-architecture.md)
- [迁移选择](planning/bluewms20-migration-selection.md)
- [原生上架规则与增强策略](migrations/putaway-rule-binding-20.md)
- [上架 AI 云端知识接入与本地接口调整](migrations/putaway-cloud-knowledge-20.md)
- [WCS 迁移交付](migrations/wcs-20.md)
- [WCS 迁移规划](planning/bluewms20-wcs-migration.md)
- [MuK AI 中文翻译](third-party/muk-ai-zh-2026-10-13.md)
- [Docker 开发环境](../docker/README.md)
- [多台 Mac 的 Git 同步](git-sync.md)

`docs/planning/` 收录原 `odoo/bluewms20-doc` 的规划文件。以后维护、同步规划时修改这里；仓库外的旧目录作为历史副本，Git 不会同步那个目录。

第三方模块来源、许可证、版本和验证记录在 `third-party/`；自研模块迁移、测试边界和源码摘要在 `migrations/`。

业务数据库、附件、登录密码和私有运行配置放在本机用户目录及 Docker 数据卷中，不能提交到公开 GitHub 仓库。

- [宝蓝 AI 云端连接交付](third-party/blue-ai-client-install-2026-10-13.md)：Chat Completions、按用户绑定、自动团队/Agent/任务选择与代码草稿闭环。
