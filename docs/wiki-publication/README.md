# 知识发布证据

本目录只保留实际发布与验收材料，不保存一份 Wiki 或 Skill 正文副本。

| 文件 | 说明 |
|---|---|
| [发布记录](native-wiki-20261018.md) | 六库 29 份资料的发布、准确读回及当时的临时问答范围 |
| [准确来源清单](native-wiki-20261018.manifest.json) | 来源提交、文件、源摘要和发布正文摘要 |
| [问答证据](native-wiki-20261018.qa.json) | 八组真实问答及搜索／读页摘要，不能代替真实 Task 路由验收 |
| [设备协议发布](device-protocol-20261018.md) | 通用／设备 Wiki 版本 4、TUSK 真实生成及隔离执行范围 |
| [设备协议准确来源](device-protocol-20261018.manifest.json) | 本轮 15 页的来源提交及摘要，不覆盖其他四库历史来源 |

正式 Odoo 原生接入、五类真实 Task 及代码生成验证以[接入记录](../migrations/native-wiki-runtime-20.md)和[最新验收](../migrations/native-wiki-runtime-20.validation.json)为准。

设备 /1 的新增能力、安装及最终验收见[设备交付](../migrations/device-protocol-20.md)和[设备验收](../migrations/device-protocol-20.validation.json)。

维护来源只有 [docs/wiki/](../wiki/README.md)，操作流程见[维护与发布](../architecture/ai-generation-knowledge-maintenance.md)。旧 `wcs-v4` Skill 候选包和重复综合知识稿已从当前工作树移除，历史通过 Git 追溯；云端现存旧 Skill 和业务数据未因文档整理被删除。
