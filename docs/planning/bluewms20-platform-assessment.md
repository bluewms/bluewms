# BlueWMS20 平台选型与迁移评估

> **2026-10-17 维护入口**：本文保留原日期的调查或交付记录；当前基础说明、五类 AI 规范与示例统一维护在 [Odoo AI 代码生成知识库](../wiki/README.md)。上架 AI 已读取云端批准示例，准确代码、本次测试与验证发布仍在本地；其他四类 AI 入口分别按合同验收。

## 2026-10-12 命名与分类更新

新 20 模块统一采用 `blue_<领域>_<功能>`：库存 `blue_stock_*`、设备 `blue_wcs_*`，条码独立为 `blue_barcode_*`；所有模块直接位于 `bluewms` 下，不建立分类目录。非 `blue_` 的额外 addon 按第三方来源管理，官方 Odoo 基础保持原名。旧 19 名称保留为代码调查和迁移引用，历史 `blueprj_*` 及单功能名称不作为新 20 命名标准。详细目标、来源核查和依赖边界见 [模块分类与命名规划](/Users/jianglang/odoo/bluewms20-doc/bluewms20-module-architecture.md)。

## 本地工程基线更新（2026-10-12）

本机 Docker 环境已运行：`bluewms20-odoo` 使用 `odoo:20`，`bluewms20-db` 使用 `postgres:16.0`。已读到容器 Python `3.12.3`、Odoo `20.0-20260926`；后续兼容验证以实际容器版本及镜像摘要为准，不把历史调查提交或新下载源码自动视作运行版本。

宿主机 `/Users/jianglang/odoo/bluewms` 挂载至 `/mnt/extra-addons`；自研、客户及第三方模块均放在该目录的直接子目录，由 [bluewms/bluewms](https://github.com/bluewms/bluewms) 开源与版本管理。第三方锁定来源与提交、保留许可；运行配置与凭据在仓库外，数据使用独立 Docker 卷。`odoo20` 为源码查阅目录，当前未替换镜像内的官方代码。详细基线见 [BlueWMS20 正式开发计划](/Users/jianglang/odoo/bluewms20-doc/bluewms20-development-plan.md) 的 2.4 节。

原调查日期：2026-10-11｜工程约定更新：2026-10-12  
目标：下一版本改以 Odoo 20 开发，继续采用五类 AI 对话定制、Tencent Wiki／Memory、宝蓝云端授权与本地代码版本。  
调查方式：官方发布说明、官方 20.0 源码、MuK 官方 20.0 分支与现有 BlueWMS19 静态对照；原调查时尚未安装或运行 Odoo 20；2026-10-12 已核查本机 Docker 基础环境运行状态，业务兼容测试另行完成。

## 1. 建议

**新产品可以选择 Odoo 20。推荐 Odoo 20 社区版＋MuK 20＋宝蓝自研 AI 定制模块；自研本地模块可以开源，云端知识、生成、验证、授权与资产服务收费。**

Odoo 20 已于 2026 年 9 月发布。对于尚未正式开始开发的下一版本，直接在 20 上建立入口协议和脚本版本体系，可以减少先做 19 再移植 20 的重复工作。[官方版本列表](https://www.odoo.com/page/release-notes)

旧 19 客户继续维护；本次转向新产品开发平台，不意味着把所有存量客户立即迁移。

## 2. “开源＋云端收费”的准确边界

宝蓝拥有版权、来源和依赖许可允许的自研 AI 模块，可以选择开源许可证并提供收费云服务。本地按钮、聊天、脚本执行器和代码版本功能可以公开；宝蓝网关对客户知识、批准示例、生成与验证服务、额度和项目权益进行鉴权。

Odoo 企业版原有 AI 源码是否能公开分发，仍由其许可证决定。20 的官方 OEEL 文本禁止分发企业软件及修改副本，依赖腾讯知识库不会改变这一条款。[Odoo 20 企业许可](https://raw.githubusercontent.com/odoo/documentation/20.0/content/legal/licenses/enterprise_license.txt)

因此主方案是参考企业 AI 的产品与架构，自行实现宝蓝模块。需要企业功能的客户可以在有效企业订阅下安装相应桥接扩展；不将 OEEL 核心代码重新声明为宝蓝开源代码。MuK 使用 LGPL，沿用其许可与版权信息。

云端服务是可执行的商业授权边界。客户已经获得的代码会存在本地，能够继续离线运行；本地开源系统的管理员也能修改客户端。收费价值来自持续生成、知识、验证、升级和服务，不承诺只靠隐藏 API 地址就永久防复制。

## 3. Odoo 20 的新增帮助

### 3.1 Agent 的交互与工具设计更贴近我们的产品

20 的官方 Agent 文档以 Skills、Tools 和 Sources 组织能力，增加记录创建／更新、文件上下文和处理状态展示。对于宝蓝五类入口，可借鉴“入口技能＋明确工具＋资料来源”的交互设计。[官方 Agent 文档](https://raw.githubusercontent.com/odoo/documentation/20.0/content/applications/productivity/ai/agents.rst)

产品中的五类定制仍按固定业务协议执行；Agent 能创建或更新记录，不代表其已经具备任意生成业务代码、验证和发布的完整能力。

### 3.2 官方 MCP 方案可参考

20 的 AI 文档提供 MCP 服务，将授权用户的服务器动作作为工具供外部 Agent 调用，包括独立 Key、作用域、期限和 `/mcp` 端点。可以参考其工具协议与身份设计。[官方 MCP 文档](https://raw.githubusercontent.com/odoo/documentation/20.0/content/applications/productivity/ai/mcp_server.rst)

当前免费社区主方案采用 MuK MCP。原生 AI 文档存在不等于相关企业功能已经包含在公开社区仓库中；企业 20 源码尚未在本地取得和核查。

### 3.3 数据库代码执行可继续使用，执行检查有新实现

保存 Python Text 后由标准入口调用的基础模式继续可用。20 将 `safe_eval` 拆为包，新增运行时调用、对象白名单和监控相关代码。[safe_eval 入口](https://raw.githubusercontent.com/odoo/odoo/20.0/odoo/tools/safe_eval/__init__.py)、[运行时实现](https://raw.githubusercontent.com/odoo/odoo/20.0/odoo/tools/safe_eval/runtime.py)

对宝蓝的帮助是可参考这些检查机制，减少自行实现底层执行检查。仍要定义允许的上下文、语法、辅助方法、输出结构和资源限制。源码存在检查不等于目标运行环境已强制启用；其实际策略、原生组件和失败行为需要在新环境验证。它也不能替代库存和设备业务约束。

### 3.4 配置读写更明确

20 的 `ir.config_parameter` 提供按类型读取／写入的接口，包括字符串、整数、浮点和 Boolean。适合宝蓝配置快照与恢复适配器明确处理 `false`、`0` 和类型。[官方配置参数源码](https://raw.githubusercontent.com/odoo/odoo/20.0/odoo/addons/base/models/ir_config_parameter.py)

### 3.5 库存与条码的新功能可减少部分自研

官方 20 发布说明列出条码欠单选择、批量批次／序列号、固定按钮位置、盘点数量输入、批次收货等改进，可用来重新评估已有条码功能的必要性。[官方发布说明](https://www.odoo.com/ca_ES/odoo-20-release-notes?trk=public_post_comment-text)

这些是官方产品能力，不保证自动出现在我们的社区 `stock_bluebarcode` 中。每项应确认模块归属、许可和实际实现后再决定复用或独立开发。不要把发行说明中的全部条码功能算作免费社区收益。

## 4. AI 成本与接入路线

20 的官方发布说明写明原生 AI 功能需要 IAP credits；官方 API Key 文档目前还在建设并指向 IAP 服务页。[AI Key 文档](https://raw.githubusercontent.com/odoo/documentation/20.0/content/applications/productivity/ai/apikeys.rst)

本次不能根据 19 企业版源码推断 20 可以原样切换成宝蓝模型网关。若要使用原生企业 AI，需要取得 20 企业代码，并核查 provider、IAP、服务端接口和订阅条件。

宝蓝自己的 MuK＋网关路线由宝蓝和模型供应商计费，不应主动接入原生 IAP 流程。不是所有第三方 AI 功能都受官方原生 AI 的 IAP 说明支配。

## 5. MuK 20 是否已有合适基础

官方 `muk-it/odoo-modules` 已有 20.0 分支，本次直接取得的 `muk_ai` 清单为 `20.0.1.25.1`、LGPL-3，依赖 `bus`、`mail`、`base_setup`、`muk_mcp`。

相关目录包括 `muk_ai`、`muk_ai_skills`、`muk_ai_automation`、`muk_ai_chatter`、`muk_ai_subagents`、`muk_mcp`、`muk_mcp_access`。README 明确描述社区版、私有部署、自有模型 Key、浮动窗口和独立 provider 扩展。[MuK 20 官方说明](https://raw.githubusercontent.com/muk-it/odoo-modules/20.0/muk_ai/README.md)

下一步使用锁定的 MuK 20 版本，不把本地 19 的 MuK 整包改清单后继续使用。当前本地 DeepSeek 实现是否包含在所选 20 版本，需单独核对；需要时通过独立 provider 扩展迁移，不覆盖上游核心。

## 6. 已查到的具体迁移变化

社区源码核查基线：`odoo/odoo@9fbff4fa4b81719496dc579d77e3f11b82c42efc` 的 20.0。

### 6.1 批次模块合并到 stock

20 的批次作业模型在 `addons/stock/models/stock_picking_batch.py`，视图和数据也由 `stock` 安装。原来的独立 `stock_picking_batch` 目录不在本次 20.0 addons 清单中。[批次模型源码](https://raw.githubusercontent.com/odoo/odoo/20.0/addons/stock/models/stock_picking_batch.py)

现有 BlueWMS 需要调整：

- `blue_wcs`、`stock_bluebarcode` 清单中的独立批次依赖。
- 条码批次视图继承的 `stock_picking_batch.stock_picking_batch_form`，对应 20 改为 `stock.stock_picking_batch_form`，并重新核对视图结构。
- 模型代码中通过旧 XML ID 打开批次表单的逻辑。
- 批次、波次、包装、自动合并和确认流程的回归验证。

### 6.2 单位字段有实际改名

对照现有 19 与官方 20：

| 对象 | 19 当前字段 | 20 字段 | 已受影响的位置 |
|---|---|---|---|
| `stock.move` | `product_uom` | `uom_id` | ERP 创建移动、条码与库存测试数据 |
| `stock.quant` | `product_uom_id` | `uom_id` | 库位单品单位计算、库存显示与相关字段 |

例如 `blue_wcs/controllers/main.py` 当前创建 `stock.move` 时仍写 `product_uom`；新模块必须按 20 的真实模型修改。[20 库存移动源码](https://raw.githubusercontent.com/odoo/odoo/20.0/addons/stock/models/stock_move.py)、[20 库存数量源码](https://raw.githubusercontent.com/odoo/odoo/20.0/addons/stock/models/stock_quant.py)

字段迁移按模型处理，不对整个项目全局替换字符串；`stock.move.line`、前端数据结构和协议字段必须分别核查。

### 6.3 原有配置参数调用要迁移

本次 20 源码中的配置接口改为 `get_str/get_bool/get_int/get_float` 和对应 setter，未发现原 `get_param/set_param` 方法定义。现有 BlueWMS 非 MuK Python 文件中检索到 30 行相关调用，含测试。

新版本按参数类型迁移，例如连接地址／token 使用字符串，开关使用 Boolean，计时／重试次数使用整数；同时核对新接口默认值与缺失行为。

### 6.4 关键 hook 的签名保持一致，但实现有变化

静态对照下列方法参数仍一致：

- `_get_putaway_strategy()`、`_check_can_be_used()`。
- `button_validate()`、`action_assign()`、`do_unreserve()`。
- `stock.move._prepare_move_line_vals()`、`_action_done()`。
- `stock.quant._update_available_quantity()`。

这是迁移的有利条件，五类入口方向无需推倒。源码内部实现已经发生变化，不能据此认定已有继承模块无需测试，尤其要验证数量、单位、预留、包裹与批次。[20 上架与库位源码](https://raw.githubusercontent.com/odoo/odoo/20.0/addons/stock/models/stock_location.py)

### 6.5 运行环境要求

锁定提交的 `release.py` 声明最低 Python 3.12、PostgreSQL 16。现有 README 中 PostgreSQL 15 的部署示例不作为 20 的安装方案。[版本运行要求](https://raw.githubusercontent.com/odoo/odoo/9fbff4fa4b81719496dc579d77e3f11b82c42efc/odoo/release.py)

新开发使用单独的 20 环境、数据库和依赖版本；旧 19 不共享被新版本修改的配置或数据库。

## 7. 对 Tencent 示例库的调整

示例至少标注 `odoo_series=20.0`、标准／客户模块版本、hook 协议版本、所需辅助方法和测试样例。19 示例可以作为迁移参考，不能未经验证成为 20 的批准模板。

明确分开：

- 宝蓝公开的标准入口与执行器源码。
- 宝蓝正式批准、可供客户检索的模板资产。
- 各客户自己的需求、代码、验证结果和启用版本。

旧配置包需要显式迁移，不能把 19 保存的原代码和数字 ID 直接作为 20 正式版本启用。

## 8. 开发顺序调整

在原 AI 开发路线前增加一个 **Odoo 20 兼容阶段，初步预留 1–2 周**，时间根据实际安装问题修正：

1. 基于已建立的本机 Docker 环境核对并锁定 Odoo 20、Python／PostgreSQL；将锁定的 MuK 20 及依赖放入 `bluewms` 后安装验证。
2. 迁移最小模块集合：`blue_stock`、核心条码、`blue_wcs` 及一款设备模拟适配器。
3. 修正批次依赖／XML ID、单位字段、配置接口和已发现的旧模型残留。
4. 验证基础入库、出库、移库、批次／包装、上架、条码、WCS 发送与回执。
5. 冻结第一版 20 的五类协议和能力目录。
6. 完成条码 AI 对话→Wiki 示例→代码草稿→样例验证→保存启用→本地执行→恢复的闭环。
7. 扩展其余入口和正式客户试点。

原来 12 周计划需要加上兼容阶段并重新估算，可先以 **13–14 周**作为评审目标。没有运行结果前不承诺整个 19 模块集合在两周内完整迁移。

## 9. 结论的实际范围

Odoo 20 对新产品有帮助，尤其是可以直接使用新版本基础、MuK 20、类型化配置接口和批次模块整合；原生 AI 交互也是有价值的参考。

“五类按钮生成可执行客户代码”的主体仍由宝蓝实现；20 不自动提供我们的 Tencent 示例库、商业授权、脚本验证启用和客户资产恢复体系。

原调查仅完成选型与迁移点分析。2026-10-12 已确认 `bluewms` 工程、独立 Docker 基础环境和 `odoo20` 查阅源码；尚未据此完成 BlueWMS／MuK 20 模块迁移、业务验证或客户数据库升级。企业 20 的完整源码和具体客户环境尚未核实，原生 IAP 的接入与企业功能归属需在选择该路线时补查。

## 2026-10-12 可编辑上架策略首期交付

用户已批准清单 3、4 的两个标准示例闭环。`blue_extension_contract`、`blue_config_asset`、`blue_stock_putaway` 已安装到本地 Docker 开发库，79 项联合测试通过。代码可以前端编辑，未来 AI 通过同一草稿接口提交，验证和发布使用同一流程。准确代码与版本在 Odoo 数据库保存，现场执行不请求云端。Tencent 知识／记忆 API 适配合并到拟开发的 `blue_ai_client`，不独立建 `blue_ai_memory`；本轮没有连接云端模型或 Key。

首期仅实现上架合同，场景草稿暂合并在 `blue.config.profile`，配合不可变版本／发布快照。五类完整场景、单点覆盖、云端同步队列和其他业务合同仍按后续计划推进。两个示例为优先集中，散件容量不足可以拆分；包裹／托盘／WCS、独占库位、精确来源追踪不在首期。开发库未自动绑定或启用仓库策略。详情见 [上架策略交付与使用说明](/Users/jianglang/odoo/bluewms/docs/migrations/putaway-policy-20.md)。

## 2026-10-12 系统优先与整托盘增强

用户确认补充代码只能进一步限制／排序, 不接管 Odoo。`blue_stock_putaway` 和 `blue_extension_contract` 已升级至 `20.0.1.1.0`。原生规则范围和优先级、存储类别、托盘数量、重量与混放设置先检查, 然后执行补充代码。新增同批次号限制示例支持不同产品, 按批次号文本比较。整托盘及内箱去重, 计入已上架和待上架托盘, 不自动拆托。112 项联合测试与独立事务最后一个托盘位争用检查通过。详情见 [托盘增强交付](/Users/jianglang/odoo/bluewms/docs/migrations/putaway-pallet-enhancement-20.md)。

## 2026-10-12 原生规则选择增强场景

用户确认将增强场景直接绑定到 stock.putaway.rule. 原生上架规则列表新增“增强策略”选择框, 策略定义移除仓库／作业类型／增强适用库区三个字段. 场景可复用, 单据按每条原生规则固定代码版本. 120 项联合测试及最后一个托盘位并发检查通过. 新方式见 [原生规则绑定增强策略](/Users/jianglang/odoo/bluewms/docs/migrations/putaway-rule-binding-20.md)。
