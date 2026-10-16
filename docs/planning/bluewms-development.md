# BlueWMS 开发规则 V1 · 起步版

> **2026-10-16 现行知识决策**：原调查与按日期的交付条目保留为历史，不能把“当时尚未连接云端”当作当前状态。云端示例／说明／Skill 统一管理，本地保留真实运行合同、策略代码和验证发布；当前仅上架完成 AI 草稿闭环。详见 [云端知识与 AI 工作流](../architecture/cloud-knowledge-and-ai-workflow.md)。

## 2026-10-12 命名与分类更新

新 20 模块统一采用 `blue_<领域>_<功能>`：库存 `blue_stock_*`、设备 `blue_wcs_*`，条码独立为 `blue_barcode_*`；所有模块直接位于 `bluewms` 下，不建立分类目录。非 `blue_` 的额外 addon 按第三方来源管理，官方 Odoo 基础保持原名。旧 19 名称保留为代码调查和迁移引用，历史 `blueprj_*` 及单功能名称不作为新 20 命名标准。详细目标、来源核查和依赖边界见 [模块分类与命名规划](/Users/jianglang/odoo/bluewms20-doc/bluewms20-module-architecture.md)。

## BlueWMS20 本地开发与版本管理约定（2026-10-12）

本版开发在本机 Docker 中运行 Odoo 和 PostgreSQL；宿主机 `/Users/jianglang/odoo/bluewms` 挂载至 Odoo 容器 `/mnt/extra-addons`。后续自研标准模块、客户模块及第三方模块均放在 `bluewms` 下，每个可安装模块直接占一个子目录，沿用现有 addons 路径。

`bluewms` 是开源与版本控制仓库，远端为 [bluewms/bluewms](https://github.com/bluewms/bluewms)，当前分支 `main`。第三方模块保留原名、版权和许可证，记录上游来源、分支、提交与本地补丁；Python／系统依赖在 Docker 镜像中管理。运行配置、凭据、数据库、filestore 和备份不进入公开仓库。

相邻的 `odoo20` 官方源码用于查阅和兼容对照，当前未挂载为容器运行源码；开发、安装、升级和测试以 Docker 实际版本为准。具体环境和交付约定见 [BlueWMS20 正式开发计划](/Users/jianglang/odoo/bluewms20-doc/bluewms20-development-plan.md) 的 2.4 节。

版本：1.0.4（原共享规则）＋20 工程补充｜更新日期：2026-10-12｜适用于开发人员、CodeBuddy 和 Codex。

现在先执行以下五条，遇到实际问题再逐步补充。

<!-- BLUEWMS_DISTRIBUTION_ENTRY_START -->
## 1. 先复用，再开发

开发前先看相关代码和配置。现有功能能解决就直接使用；需要新增时，先判断是通用功能还是客户定制。

## 2. 模块归属与命名

- 新 20 标准模块：`blue_<领域>_<功能>`，如 `blue_stock_base`、`blue_wcs_mita`、`blue_barcode_base`。
- 新 20 客户模块建议：`blue_project_<项目名>_<功能>`，如 `blue_project_zf_putaway`。
- 非 `blue_` 的新 20 额外模块按第三方来源管理，保留上游名；历史模块先核查来源，不能只靠前缀判定版权。

所有模块直接置于 `bluewms` 一级子目录。使用小写英文、数字和下划线；条码与库存分开。旧 19 模块不直接改名，新 20 迁移按对应清单逐项处理。客户功能放独立模块，通过继承扩展；通用功能和公共修复回到 master。不直接修改 Odoo 官方源码，不复制整套标准模块做客户版本。

## 3. 按 Odoo 的模块方式扩展

模块依赖写入 `__manifest__.py`，模型和视图优先用继承。覆盖方法保留父方法的返回和原有流程，通常调用 `super()`。不要为了一个小需求复制整段业务流程。

## 4. 客户项目优先从五处扩展

客户需求优先在下表对应位置扩展。标准版逐步固定这些位置的前后端接入点，项目模块通过接入点实现差异。

| 方向 | 项目扩展内容 | 现有后端入口 | 现有前端入口 |
|---|---|---|---|
| ERP 产品、单据同步 | 字段与单据映射 | `blue_wcs`：`product_sync()`、`picking_create()` | 现无标准接入点，后续开发优先实现 |
| WCS 单据创建 | 场景与创建方法 | `stock.picking.action_create_wcs_request()` | `stock_barcode_wcs`：`validate()` |
| 设备对接 | 共用协议放标准模块，客户差异放定制模块；连接参数用配置 | `wcs.request.button_execute()`；设备模块如 `button_execute_mita()` | 现无标准接入点，后续开发优先实现 |
| 上架与存储类别 | 准入与位置分配规则 | `stock.location._get_putaway_strategy()`、`_check_can_be_used()` | 现无标准接入点，后续开发优先实现 |
| 条码扫描 | 配置、扫描顺序与处理方法 | `stock.picking.type._get_barcode_config()` | `BarcodePickingModel._processBarcode()` |

表中已有方法作为当前参考入口，尚未全部固定为扩展接口；缺失的标准接入点优先补充，前后端接口由后续标准开发逐步固定，谨慎增加新的扩展点如必要需同步更新这份开发规则文档

## 5. 改完验证，并说明结果

验证本次功能和受影响的原有流程，涉及库存时核对数量、批次和库位。交付只需说明：改了哪个模块、解决什么问题、验证结果；没验证的如实写明。
<!-- BLUEWMS_DISTRIBUTION_ENTRY_END -->

旧项目继续正常维护，不要求统一重构；Odoo16 只参考经验，不迁移老项目。

复用、继承和验证原则继续参考旧共享规则；本文的 BlueWMS20 目录、领域命名及迁移约定以新正式计划和分类规划为准，已按用户确认更新。旧 19 共享规则的权威文件、目录和运行方式保持原样，不把新 20 命名变更自动分发到旧项目。

## 2026-10-12 可编辑上架策略首期交付

用户已批准清单 3、4 的两个标准示例闭环。`blue_extension_contract`、`blue_config_asset`、`blue_stock_putaway` 已安装到本地 Docker 开发库，79 项联合测试通过。代码可以前端编辑，未来 AI 通过同一草稿接口提交，验证和发布使用同一流程。准确代码与版本在 Odoo 数据库保存，现场执行不请求云端。Tencent 知识／记忆 API 适配合并到拟开发的 `blue_ai_client`，不独立建 `blue_ai_memory`；本轮没有连接云端模型或 Key。

首期仅实现上架合同，场景草稿暂合并在 `blue.config.profile`，配合不可变版本／发布快照。五类完整场景、单点覆盖、云端同步队列和其他业务合同仍按后续计划推进。两个示例为优先集中，散件容量不足可以拆分；包裹／托盘／WCS、独占库位、精确来源追踪不在首期。开发库未自动绑定或启用仓库策略。详情见 [上架策略交付与使用说明](/Users/jianglang/odoo/bluewms/docs/migrations/putaway-policy-20.md)。

## 2026-10-12 系统优先与整托盘增强

用户确认补充代码只能进一步限制／排序, 不接管 Odoo。`blue_stock_putaway` 和 `blue_extension_contract` 已升级至 `20.0.1.1.0`。原生规则范围和优先级、存储类别、托盘数量、重量与混放设置先检查, 然后执行补充代码。新增同批次号限制示例支持不同产品, 按批次号文本比较。整托盘及内箱去重, 计入已上架和待上架托盘, 不自动拆托。112 项联合测试与独立事务最后一个托盘位争用检查通过。详情见 [托盘增强交付](/Users/jianglang/odoo/bluewms/docs/migrations/putaway-pallet-enhancement-20.md)。

## 2026-10-12 原生规则选择增强场景

用户确认将增强场景直接绑定到 stock.putaway.rule. 原生上架规则列表新增“增强策略”选择框, 策略定义移除仓库／作业类型／增强适用库区三个字段. 场景可复用, 单据按每条原生规则固定代码版本. 120 项联合测试及最后一个托盘位并发检查通过. 新方式见 [原生规则绑定增强策略](/Users/jianglang/odoo/bluewms/docs/migrations/putaway-rule-binding-20.md)。
