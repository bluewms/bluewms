# BlueWMS 文档

更新: 2026-10-26。当前文档按用途维护,阶段性开发过程从 Git 历史查阅。

## 业务使用

| 内容 | 指南 |
|---|---|
| 库位、包裹、非负库存、冻结和禁止入库 | [库存基础](guides/stock.md) |
| 原生规则之后的候选过滤与排序 | [上架策略](guides/putaway.md) |
| 盘库范围、实盘、快照与原生记账 | [盘库](guides/inventory.md) |
| 行决定、数量、repeat/relay、回执与核对 | [WCS](guides/wcs.md) |
| 类别级 HTTP/JSON、认证与受控位置回写 | [设备接口](guides/equipment.md) |
| 入库/出库/调拨、完成及盘点差异事件 | [ERP 接口](guides/erp.md) |
| PDA、分组分页、数量、欠单和操作码 | [条码](guides/barcode.md) |
| 五类 AI 入口、资产、草稿与人工发布 | [AI 使用](guides/ai.md) |

## 开发、部署与维护

- [模块架构](module-architecture.md) · [开发规则](planning/bluewms-development.md) · [当前计划](planning/bluewms20-development-plan.md)。
- [Docker 配置](../docker/README.md) · [升级与恢复](operations/upgrades.md) · [Git 同步](git-sync.md)。
- [云端服务/用户接入](operations/cloud.md) · [知识发布流程](operations/knowledge-publication.md)。
- [测试与验收](testing/README.md) · [结构化核对记录](validation/README.md) · [第三方依赖](third-party/README.md)。

## AI 知识

[docs/wiki](wiki/README.md) 是唯一生成知识来源,仅包含通用规则、五类规范、合同与准确案例。工程文档、服务器信息、凭据和开发流水不上传到生成库。实际云端状态见 [发布记录](wiki-publication/README.md),六库逻辑绑定见 [注册表](architecture/native-wiki-knowledge-registry.json)。

源码实现、数据库安装、知识批准、真实模型/设备验收分别核对。Git 不同步业务数据或自动发布云端知识。正式 Odoo 发行包排除整个 docs,云端服务源码仍保留在 [cloud](cloud/README.md)。
