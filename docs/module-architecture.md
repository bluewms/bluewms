# BlueWMS20 模块分类与命名规划

版本：1.0｜日期：2026-10-12｜状态：目录与命名原则已确认；具体拆分及旧模块对应关系用于迁移评审，尚未执行改名。

## 1. 已确认的原则

- 所有可安装模块直接放在 `bluewms` 的一级子目录，不再建立 `muk/`、`stock/`、`wcs/` 等模块分类目录；文档、Docker 和资源记录仍可使用自己的管理目录。
- 宝蓝维护的新模块统一使用小写 `blue_<领域>_<功能>`，以 `blue_wcs_*`、`blue_stock_*` 等前缀区分职责；不使用大写 `blue_WCS`。
- 条码独立为 `blue_barcode_*`，不归入 `blue_stock_*`，但可依赖库存基础；设备联动通过桥接模块实现。
- 新 20 工程中，不以 `blue_` 开头的非官方 addon 按第三方模块管理，保留上游名称、来源、许可、版本与补丁；已引入的 `muk_*` 保持名称。Odoo 自带 `stock`、`web` 等属于官方基础，不是宝蓝自研模块。
- 前缀表示工程维护归属，不改变原代码版权或许可证。旧 19 中的 `stock_*`、`legion_*` 等历史命名不能仅凭前缀判定来源；迁入新 20 前逐项核查自研、第三方和修改版。
- 本次确定规划，不在运行数据库中直接改目录名。新 20 开发采用目标名称；旧模块的模型、XML ID、导入、依赖、资源和数据分别迁移，不做全局字符串替换。旧 19 工程保持原有名称与运行方式。

## 2. 分类与名称

下表是目标职责及名称示例，不代表全部模块已创建，也不要求每个小功能单独建模块。基础模块拟使用 `_base`，与领域命名保持一致。

| 分类 | 前缀／目标名称 | 职责 |
|---|---|---|
| 第三方基础 | `muk_*`、其他上游原名 | 官方版本的主题、AI、Skills、MCP 等；已有 MuK 模块已安装 |
| 库存与仓库基础 | `blue_stock_base`、`blue_stock_package`、`blue_stock_putaway`、`blue_stock_inventory` | 库位、批次、包裹、库存约束、上架与人工盘点；按独立安装需求决定拆分 |
| 条码作业 | `blue_barcode_base`、`blue_barcode_inventory`、`blue_barcode_extension` | 扫描、手持终端、条码盘点、策略能力与场景桥接 |
| WCS／设备 | `blue_wcs_base`、`blue_wcs_mita`、`blue_wcs_m4`、`blue_wcs_tusk`、`blue_wcs_modula`、`blue_wcs_barcode` | 任务、设备注册、持久发送、回执及厂商协议；独立条码／盘点桥接 |
| ERP／外部接口 | `blue_erp_base`、`blue_erp_<系统>` | 鉴权、产品／单据映射、幂等创建与反馈；从旧 WCS 接口逐步分离 |
| 场景、合同与资产 | `blue_extension_contract`、`blue_config_asset`、`blue_delivery_asset` | 业务合同、受限执行器、版本、统一发布、应用事件、导出与恢复；无 AI 也能运行 |
| AI／知识／授权 | `blue_ai_client`、`blue_ai_skills`、`blue_ai_license` | MuK provider 与专用工具、blue_ai_client 内的云端知识／记忆适配、授权入口；云端账本另行管理 |
| 产品界面 | `blue_web_theme`、`blue_web_login` | 宝蓝主菜单、品牌和登录界面；通过继承扩展 MuK，不修改上游核心 |
| 看板与培训 | `blue_report_stock`、`blue_training_exam` | 可选报表、看板、培训考试，不进入库存基础强依赖 |
| 公共平台辅助 | `blue_system_cron`、`blue_dev_environment` | 确有需求时提供秒级任务等；开发标识模块只供开发环境 |
| 客户项目 | `blue_project_<项目>_<功能>` | 建议替代新 20 的 `blueprj_*` 命名，使宝蓝客户模块同样具有 `blue_` 前缀；不复制标准模块 |

`blue_stock_base`、`blue_wcs_base`、`blue_barcode_base`、`blue_project_*` 为本规划的目标命名，迁移前复核各模块的实际来源与依赖；没有执行安装和代码改名。显示名称与技术名分别维护。

## 3. 依赖边界

- `blue_stock_base` 依赖必要的 Odoo 基础，不依赖 AI、WCS、登录动画或培训模块。
- `blue_barcode_base` 依赖库存基础；库存基础不反向依赖条码。
- `blue_wcs_base` 依赖库存基础；无需扫码的自动化作业可以不安装条码。
- `blue_wcs_barcode` 同时依赖 WCS 与条码，负责扫码触发设备任务；通用 WCS 不强制依赖条码。
- `blue_barcode_inventory` 同时依赖条码与盘点。机器人盘点的任务核心和厂商适配在 WCS 中，人工盘点不强制依赖设备。
- `blue_erp_base` 不强制依赖 WCS；只有需要创建设备任务的业务才通过桥接依赖 WCS。
- 合同模块不依赖资产或 AI；资产依赖合同；AI 依赖资产和 MuK。条码／WCS／ERP 的定制桥接分别接入资产，不形成循环依赖。
- 界面、报表、培训与客户模块依赖对应业务模块，基础业务不反向依赖这些配套模块。

## 4. 旧 19 模块的迁移对应

这是迁移清单，不是已执行的目录重命名。第三方来源核查优先于把模块改成 `blue_` 名称。

| 旧名称／职责 | 目标名称或处理方式 |
|---|---|
| `muk_web_*`、`muk_ai`、`muk_ai_skills`、`muk_mcp` | 保留第三方原名，使用官方 20.0 版本和来源锁 |
| `blue_stock` | 库存通用能力迁入 `blue_stock_base`；菜单／品牌分离至 `blue_web_theme` |
| `stock_bluebarcode` | 来源核查后迁入 `blue_barcode_base`；前端逐项适配 Owl 3 |
| `blue_wcs` | 任务／设备通用逻辑迁入 `blue_wcs_base`；ERP 接口分离至 `blue_erp_base` |
| `blue_wcs_mita/m4/tusk/modula` | 保留已符合领域前缀的名称，依赖转向目标 WCS 基础 |
| `stock_barcode_wcs` | `blue_wcs_barcode`；仅承担条码和 WCS 联动 |
| `blue_wcs_mita_barcode` | 保留名称，作为 Mita 专有条码桥接，不混入厂商基础适配 |
| `stock_inventory_ajustement` | 来源核查后迁入 `blue_stock_inventory`，统一拼写和盘点职责 |
| `stock_inventory_barcode_bridge` | `blue_barcode_inventory` |
| `stock_inventory_robot`、`stock_inventory_mita` | 目标 `blue_wcs_inventory_robot`、`blue_wcs_inventory_mita`；同时重新检查人工盘点和条码依赖边界 |
| `stock_empty_package_storage` | 来源核查后目标 `blue_stock_empty_package`，按需独立安装 |
| `blue_auto_unpack` | 目标 `blue_stock_auto_unpack` |
| `stock_putaway_same_picking` | 与同批次能力共用 `blue_stock_putaway`；首期重新实现可编辑同入库单示例，不复制旧执行逻辑 |
| `stock_same_lot` | 在 `blue_stock_putaway` 中重新实现可编辑同产品同批次示例；旧 WCS 耦合不迁入 |
| `stock_location_lockdown`、`stock_no_negative` | 原码来源核查后再决定保留第三方原名或新增 `blue_stock_*` 扩展；不能根据已改写的清单作者判定版权 |
| `legion_hide_odoo`、`legion_hide_odoo_tab` | 核查来源；宝蓝品牌逻辑通过 `blue_web_theme` 等独立模块实现，不整包抹去上游归属 |
| `sc_login_animation` | 核查来源与许可；第三方保留原名，宝蓝登录扩展用 `blue_web_login`；从库存基础强依赖中移出 |
| `spreadsheet_dashboard_stock` | 核查来源后，宝蓝扩展目标 `blue_report_stock` |
| `blue_survey_exam` | 目标 `blue_training_exam` |
| `blue_cron_seconds` | 目标 `blue_system_cron`，不作为所有业务模块强制依赖 |
| 原拟议 `blue_delivery` | 新规划使用 `blue_delivery_asset` |
| 原拟议 `blueprj_*` | 新 20 建议使用 `blue_project_<项目>_<功能>`；旧 19 不直接改名 |

现有 `blue_stock` 的库存摘要、可用库位统计、容量明细维护和公司权限问题，应在迁移中修正并验证。分类不能替代功能设计和测试。

## 5. 迁移实施规则

1. 登记来源、维护归属、原许可、旧名、目标名、模型／XML ID 和所有消费者。
2. 从已通过安装验证的 MuK 基础继续，先迁移库存基础与产品界面，再迁移独立条码和 WCS／ERP。
3. 先在独立 Odoo 20 测试库验证安装、数量／单位／批次／库位及相关交互。
4. 旧名字的字符串按用途处理：模块依赖、Python／JS 导入、资源路径、外部 ID、模型名、数据库表名不是同一类标识。
5. 新库安装采用目标名称；已装旧模块的数据库必须有迁移步骤，防止重复模型、重复菜单或数据丢失。
6. 来源锁、迁移对应、测试与恢复说明进入 `bluewms` Git；第三方许可、版权与补丁记录保留。

分类规划编制后，`blue_stock_base` 与 `blue_web_theme` 已按本分类完成首批迁移并安装。现有 MuK 模块名称、Docker 挂载及 addons 路径保持原样；旧 19 模块未直接改名。实际交付范围和验证见 `bluewms/docs/migrations/blue-stock-20.md`，条码／WCS 等仍按对应工作包推进。

## 2026-10-12 已批准库存约束

清单 1、2 已迁移至独立 `blue_stock_rules`（AGPL-3），没有并入 `blue_stock_base`。43 项最终联合测试及可选模块卸载／重装通过，开发库已安装。用户随后批准在 `blue_stock_putaway` 中完成两个可编辑示例的闭环；最新交付见 `docs/migrations/putaway-policy-20.md`。

## 可编辑上架与 AI 客户端合并

`blue_stock_putaway` 与合同／资产模块完成首期闭环，79 项联合测试通过；详见 [上架策略交付与使用说明](/Users/jianglang/odoo/bluewms/docs/migrations/putaway-policy-20.md)。用户确认 Tencent 知识／记忆 API 适配放入 `blue_ai_client`，不单独建 `blue_ai_memory`。安装两个模板，不自动启用仓库策略。

## 2026-10-12 系统优先与整托盘增强

用户确认补充代码只能进一步限制／排序, 不接管 Odoo。`blue_stock_putaway` 和 `blue_extension_contract` 已升级至 `20.0.1.1.0`。原生规则范围和优先级、存储类别、托盘数量、重量与混放设置先检查, 然后执行补充代码。新增同批次号限制示例支持不同产品, 按批次号文本比较。整托盘及内箱去重, 计入已上架和待上架托盘, 不自动拆托。112 项联合测试与独立事务最后一个托盘位争用检查通过。详情见 [托盘增强交付](/Users/jianglang/odoo/bluewms/docs/migrations/putaway-pallet-enhancement-20.md)。

## 2026-10-12 原生规则选择增强场景

用户确认将增强场景直接绑定到 stock.putaway.rule. 原生上架规则列表新增“增强策略”选择框, 策略定义移除仓库／作业类型／增强适用库区三个字段. 场景可复用, 单据按每条原生规则固定代码版本. 120 项联合测试及最后一个托盘位并发检查通过. 新方式见 [原生规则绑定增强策略](/Users/jianglang/odoo/bluewms/docs/migrations/putaway-rule-binding-20.md)。
