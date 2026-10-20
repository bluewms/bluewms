# 模块分类与依赖

更新：2026-10-20。所有 addon 直接位于仓库一级目录，按技术名前缀区分领域，不再套 `muk/`、`stock/` 或 `wcs/` 分类目录。

## 命名与维护归属

自研使用小写 `blue_<领域>_<功能>`。库存 `blue_stock_*`、WCS `blue_wcs_*`、条码 `blue_barcode_*` 分开；客户扩展采用 `blue_project_<项目>_<功能>`。第三方额外 addon 保留上游名称；Odoo 自带基础不属于宝蓝自研。

前缀不决定版权。旧 19 的 `stock_*`、`legion_*`、`blueprj_*` 等先核查来源，再分别处理模型、XML ID、资源、依赖和数据迁移，不直接全局改名。

## 当前模块

| 模块 | 职责 | 声明许可 |
|---|---|---|
| `blue_stock_base` | 库存、库位、包裹及汇总基础 | LGPL-3 |
| `blue_stock_rules` | 非负库存、冻结／禁止入库及授权例外 | AGPL-3 |
| `blue_stock_putaway` | 原生上架规则之后的受限增强 | AGPL-3 |
| `blue_extension_contract` | 纯数据合同、共享 JSON 受限解释器与资源边界 | LGPL-3 |
| `blue_config_asset` | 草稿、验证、不可变版本、发布／回滚与执行记录 | LGPL-3 |
| `blue_erp_interface` | ERP /1 映射、库存单与欠单、盘点差异、完成事件及持久发送／核对 | AGPL-3 |
| `blue_ai_client` | MuK 云端连接、原生 Wiki、五类 Task 与专用草稿工具 | LGPL-3 |
| `blue_wcs_base` | 设备、计划／任务、持久发送队列与认证回调 | AGPL-3 |
| `blue_wcs_extension` | 库存作业接入、/4 行决定与任务编排 | AGPL-3 |
| `blue_wcs_protocol` | 类别级可编辑 HTTP 协议、AI 草稿、固定版本及受控位置回写 | AGPL-3 |
| `blue_web_theme` | 品牌主菜单和产品界面，与库存基础分开 | LGPL-3 |
| `muk_*` 等第三方模块 | Web／主题、AI、Skills、MCP 底座，保留上游名称 | 以各模块清单与[第三方记录](third-party/muk-ai-install-2026-10-12.md)为准 |

版本以各 `__manifest__.py` 及部署实例为准，来源与许可细节保留在模块 LICENSE／NOTICE、`third-party/` 和 `migrations/*source-lock.json` 中。

## 后续分类

`blue_barcode_base`／`blue_barcode_inventory`／`blue_barcode_extension`、`blue_erp_base`／`blue_erp_<系统>`、库存包裹／盘点和交付资产按需求推进，不能因名称出现在规划中就视为已创建。常规 HTTP 厂家优先使用设备类别协议资产；新增传输形式或系统没有的认证算法再补通用能力。

界面扩展采用 `blue_web_*`；报表、培训、公共调度采用 `blue_report_*`、`blue_training_*`、`blue_system_*`。客户专属 ERP、设备或扫描动作放 `blue_project_*`，共性修复回到标准模块。

## 依赖边界

- 库存基础不反向依赖 AI、WCS、条码、品牌界面或客户模块。
- 库存硬约束与上架策略分别可选安装；AI 不能放宽固定模块的库存保护。
- 合同不依赖资产／AI；资产依赖合同，AI 依赖资产与 MuK。WCS、条码和 ERP 通过各自桥接接入资产，避免循环依赖。
- WCS 可以不扫码运行。未来 WCS／条码及条码／盘点桥接同时依赖对应领域，人工盘点不强制安装机器人。
- ERP 连接、主数据和单据处理不以 WCS 为必选；仅设备协同场景增加桥接。
- 云端 Wiki 和记忆适配合入 `blue_ai_client`，不增加客户本地 `blue_ai_memory` 或示例库式 `blue_ai_skills`。

实际依赖以清单为准。新增迁移必须列出来源、许可、消费者和数据迁移路径；待选库存功能见[迁移候选](planning/bluewms20-migration-selection.md)，实施顺序见[开发计划](planning/bluewms20-development-plan.md)。
