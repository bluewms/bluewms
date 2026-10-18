# BlueWMS20 文档

更新：2026-10-18。这里按当前实现维护工程说明和知识来源。旧交付步骤、旧 Skill 发布包及已替代的调查稿已从当前目录移除，可通过 Git 历史追溯。

本目录保留在开发 Git 仓库中，正式 Odoo 发行包排除整个 `docs/`。云端配套服务源码与部署材料统一放在 `cloud/`，由云服务器独立部署。

## 开发与部署

| 需要了解什么 | 文档 |
|---|---|
| 当前已完成什么、下一步做什么 | [开发计划](planning/bluewms20-development-plan.md) |
| 设备接口 AI 的已确认需求与实施顺序 | [设备接口规划](planning/device-protocol-ai-plan.md) |
| 类别级设备 AI、TUSK 回调与两类位置回写 | [设备接口交付](migrations/device-protocol-20.md) |
| 模块命名、依赖和已实现模块 | [模块架构](module-architecture.md) |
| 开发、验证、权限和提交约定 | [开发规则](planning/bluewms-development.md) |
| 尚未选择／迁移的库存功能 | [迁移候选](planning/bluewms20-migration-selection.md) |
| 安装、运行、备份与模块升级 | [Docker 说明](../docker/README.md) |
| 多台电脑同步与 PR 合并 | [Git 协作](git-sync.md) |

## 当前业务与 AI

| 内容 | 文档 |
|---|---|
| 库存基础与界面拆分 | [库存基础](migrations/blue-stock-20.md) |
| 禁止负库存、冻结与禁止入库 | [库存硬约束](migrations/stock-rules-20.md) |
| 原生上架规则、托盘和增强策略 | [上架使用说明](migrations/putaway-policy-20.md) |
| WCS 参数、任务创建、版本与设备边界 | [WCS 使用说明](migrations/wcs-20.md) · [编排设计](design/wcs-v4-orchestration.md) |
| 原生 Wiki、五类 Task、页面入口及验证 | [AI 接入说明](migrations/native-wiki-runtime-20.md) · [脱敏验收](migrations/native-wiki-runtime-20.validation.json) |

上架、WCS /4 与设备协议 /1 提供 AI 草稿流程；设备以 TUSK 和受控位置回写先行，见设备接口交付。ERP、条码目前只开放知识沟通，执行合同仍为 planned。已发布业务在本地执行，知识正文和云端服务不能放宽本地合同或库存约束。

## 云端与知识维护

- [AI 工作流与职责](architecture/cloud-knowledge-and-ai-workflow.md)：本地资产、腾讯原生工具、鉴权、版本和 Task 的关系。
- [Tencent 配置](architecture/tencent-memory-configuration.md)：服务、用户／Agent／Task、共享与记忆质量。
- [云端配套服务](cloud/README.md)：原生 Wiki 接入服务源码、部署模板与测试，不随 Odoo 发行包交付。
- [知识维护与发布](architecture/ai-generation-knowledge-maintenance.md)：如何审阅、发布、校验和更新。
- [六库逻辑清单](architecture/native-wiki-knowledge-registry.json)：维护范围与接口，不包含实例 ID 或凭据。
- [发布证据](wiki-publication/README.md)：准确来源、正文摘要及真实问答记录。
- [Odoo AI 代码生成知识库](wiki/README.md)：**唯一维护来源**，只给 Odoo 内助手提供通用规则、五类规范与示例。

`wiki/` 不是项目开发或运维 Wiki。不得把 Git、服务器配置、凭据、调试记录或已过期 Skill 包混入其云端发布。运行时从云端读取批准版本，不扫描本地文档兜底；聊天工具输出按 MuK 机制保留供回放，资产版本保存引用和摘要。

第三方版权、原许可及上游版本锁保留在 `third-party/`；迁移来源锁保留在 `migrations/`。历史测试数字只对应各记录的日期和范围，不累加为当前测试总数。

仓库内的开发计划是版本控制入口。仓库外旧 `bluewms20-doc` 仅作历史参考；密码、数据库、filestore、原始联调记录和部署资源 ID 留在私有运行目录，不进 Git。
