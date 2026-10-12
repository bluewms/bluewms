# BlueWMS 五类 AI 定制：MuK 与 Odoo 官方实现对照

## 2026-10-12 命名与分类更新

新 20 模块统一采用 `blue_<领域>_<功能>`：库存 `blue_stock_*`、设备 `blue_wcs_*`，条码独立为 `blue_barcode_*`；所有模块直接位于 `bluewms` 下，不建立分类目录。非 `blue_` 的额外 addon 按第三方来源管理，官方 Odoo 基础保持原名。旧 19 名称保留为代码调查和迁移引用，历史 `blueprj_*` 及单功能名称不作为新 20 命名标准。详细目标、来源核查和依赖边界见 [模块分类与命名规划](/Users/jianglang/odoo/bluewms20-doc/bluewms20-module-architecture.md)。

## 当前开发基线更新（2026-10-12）

本报告中的 Odoo 19／企业源码与 MuK 19 对照保留为历史调查。后续新开发统一采用本机 Docker Odoo 20＋MuK 20，自研及第三方模块均安装于宿主机 `bluewms` 的直接子目录，并挂载至容器 `/mnt/extra-addons`；不将旧 19 模块原样当作已验证的 20 实现。

`bluewms` 关联 [bluewms/bluewms](https://github.com/bluewms/bluewms)，作为开源与版本控制仓库。MuK 等第三方模块记录上游来源、20.0 分支、准确提交与完整依赖，保留原许可；宝蓝扩展通过独立模块实现。凭据与运行数据不提交。Docker 实际运行版本与相邻 `odoo20` 查阅源码分开记录，完整约定见 [BlueWMS20 正式开发计划](/Users/jianglang/odoo/bluewms20-doc/bluewms20-development-plan.md) 的 2.4 节。

原调查日期：2026-10-11｜工程约定更新：2026-10-12  
性质：源码调查与开发选型；本次没有安装模块、调用付费模型、上传企业源码或修改业务代码。

## 1. 结论与开发选择

**现有 MuK AI 可以作为 BlueWMS 的 AI 对话与工具基础；它不能仅靠安装和写提示词就完成“五类入口、Tencent Wiki 示例、生成代码、验证、保存启用、本地执行、版本恢复”的完整产品。新开发以 Odoo 20 社区版＋MuK 20 为基础，在 `bluewms` 仓库开发独立的 `blue_` 扩展模块；19 对照仅作迁移参考。**

用户已确认的主流程保持：

```text
五类入口中的 AI 定制按钮
  → 对话描述需求
  → 宝蓝云端检索 Tencent Wiki 与批准示例版本
  → 生成本入口支持的 Python 代码
  → 创建代码草稿并做样例验证
  → 用户保存并启用
  → 对应 WMS 入口执行数据库中的正式代码版本
```

参考 Odoo 企业版的入口绑定、上下文、知识检索、工具 schema 和返回值约定；使用社区版现有代码字段编辑器与 `safe_eval` 基础能力；复用 MuK 的聊天和会话系统。五类业务接入和脚本发布体系由宝蓝独立实现。

## 2. 本次核查的源码版本

| 来源 | 基线／范围 | 查到的内容 |
|---|---|---|
| 本地 MuK | `addons/rent/master@36ebf06`；`muk_ai` 19.0.1.6.17 | 浮动聊天、会话、追问、provider、工具、审批、Skills 与数据库工具代码 |
| 本地企业版 | `odoo19企业/odoo-19.0+e.20260101/odoo/addons` | `ai`、`ai_app`、`ai_server_actions`、`ai_fields`、Knowledge／Documents 桥接等 |
| 官方 `saas-19.1` | 查询时提交 `7dc77de313adb2e98cfde10e7e7e09995a5c23f1` | addons 顶层 629 项；没有 `ai`／`ai_app`／`knowledge` 等独立 AI 核心目录；有通用服务器动作代码机制 |
| 官方 `20.0` | 查询时提交 `9fbff4fa4b81719496dc579d77e3f11b82c42efc` | addons 顶层 642 项；没有上述独立 AI 核心目录；有通用服务器动作代码机制 |

官方目录通过 GitHub API 核实；另检查这两个分支 `web`、`html_editor`、`base_automation` 子树中 AI 命名的 Python／JS／XML 文件，没有发现可直接承担本需求的独立实现。文件名检查不等于整个仓库不存在任何 AI 相关字样或接入点。

用户提供的 [saas-19.1 addons](https://github.com/odoo/odoo/tree/saas-19.1/addons) 和 [20.0 addons](https://github.com/odoo/odoo/tree/20.0/addons) 都属于公开 `odoo/odoo` 仓库，不是企业 AI 模块源码目录；本地企业包才是此次完整 AI 实现的主要调查来源。

## 3. MuK 对本需求的满足程度

| 用户需求 | 当前 MuK 能力 | 宝蓝需要补的内容 |
|---|---|---|
| 点击按钮打开 AI 对话 | 已有 `muk_ai.chat_window` 服务和 `ChatWindow` | 五类按钮、入口范围绑定；若需要居中弹窗，封装专用 Dialog |
| 多轮沟通、追问 | 已有会话、流式事件、`ask_user` | 五类需求提示、缺失业务资料的追问规则 |
| 自动带入当前设置 | 已有 `view_context` 和页面上下文 | 永久绑定 hook、公司、仓库／设备、设置与基础版本；不能仅依赖随导航变化的 UI context |
| 根据示例生成 Python | 已有通用模型对话与工具调用 | 精确模板检索、完整示例取回、协议约束、结构化代码草稿 |
| Tencent Wiki 与客户记忆 | 当前选定模块未发现专用 Tencent 适配 | 宝蓝云端适配器、租户隔离、模板版本和 Memory 联动 |
| 保存代码到数据库 | `muk_mcp.tool.code` 已能保存 Python；通用工具能操作允许的 ORM 对象 | 五类设置／代码版本模型、授权写入和草稿状态 |
| 运行数据库代码 | MuK 数据库工具通过 `safe_eval` 运行并读取 `result` | 独立 WMS 脚本执行器及五个确定调用位置 |
| 保存并启用 | 已有通用工具执行和风险审批 | 样例验证、版本检查、冻结内容、原子切换、运行错误处理 |
| 历史与恢复 | MuK 有提示字段历史，Odoo 有服务器动作历史 | 客户脚本正式版本、准确代码全文、模板引用、云端导出与恢复 |
| 一把 Key 对应客户授权 | 有模型 API Key 与 MCP Key | 宝蓝项目权益、服务期、额度、部署身份、密钥轮换与账单 |

不能把“模型能够输出一段 Python”视为完整代码定制能力，也不能把“可以创建一条 MCP 工具记录”视为已接上 ERP、WCS、设备、上架与条码流程。

### 3.1 可直接复用的 MuK 实现

- [聊天窗口服务](/Users/jianglang/odoo/odoo19/addons/rent/muk_ai/static/src/chat/window/chat_window_service.js:24)：通过 session ID 打开浮动窗口，可为五类按钮共用。
- [会话组件逻辑](/Users/jianglang/odoo/odoo19/addons/rent/muk_ai/static/src/chat/session/use_ai_session.js:65)：复用流式输出、消息、追问与工具卡片；“保存草稿／验证／保存并启用”需增加业务结果区域。
- [provider 工厂](/Users/jianglang/odoo/odoo19/addons/rent/muk_ai/models/provider.py:115)：支持独立模块注册宝蓝 provider，保持 MuK 原代码不变。
- [工具分派](/Users/jianglang/odoo/odoo19/addons/rent/muk_ai/models/session.py:1033)：复用 MCP 工具调用与事件记录。
- [数据库工具执行](/Users/jianglang/odoo/odoo19/addons/rent/muk_mcp/models/tool.py:256)：代码执行后读取 `result`，可作为自有脚本接口的设计参照。

本地 `providers/REGISTRY` 当前包含 OpenAI、Anthropic、Google 和 DeepSeek。README 的“三种 provider”描述未覆盖本地 DeepSeek 实现，因此接入能力以实际源码为准。OpenAI 使用 Responses，DeepSeek 使用 Chat Completions；宝蓝网关要选定并验证协议，不仅替换域名。

### 3.2 需要明确补强的 MuK 细节

1. `tool_filter` 空列表表示允许全部工具，五类定制 Agent 应发布明确工具清单。
2. 当前 `_assess_risk()` 依赖模型敏感标记；只依赖这套通用审批不能覆盖脚本启用、公司范围和模板状态。
3. `muk_ai.revision.mixin` 是提示字段历史，不是任意业务代码的完整发布记录。
4. `muk_ai_skills` 可以提供固定流程和附件，但不是 Tencent Wiki 的远程检索接口；其本地内容也不应成为宝蓝私有示例库的整库副本。
5. provider 层支持 `text_schema`，但当前默认聊天 `_stream_provider_round()` 没有为本需求强制代码结果 schema。可以用固定的“保存代码草稿”工具参数表达结果，再在服务器独立校验；不用从自由文本 Markdown 中猜代码。
6. 当前 MCP 数据库工具提供 `env` 等能力。它适合受信任的工具实现，客户生成代码应进入范围受限的专用执行器，不自动注册成可任意调用的通用 AI 工具。

## 4. 企业版有哪些实现可以参考

### 4.1 AI 按钮、上下文与结果回填

企业版 `ai.composer` 记录入口类型、目标模型、Agent 与默认提示；`aiChatLauncher.launchAIChat()` 创建对应会话并携带当前记录资料，支持将回答关联到调用组件。

对宝蓝的启发：建立明确的“入口→上下文→会话→目标草稿”关联。五类按钮自动带入 `hook_code` 与设置范围，结果回到这条定制设置，而不是只出现在一个普通聊天里。

证据：[ai_composer.py](/Users/jianglang/odoo/odoo19企业/odoo-19.0+e.20260101/odoo/addons/ai/models/ai_composer.py:17)、[聊天启动服务](/Users/jianglang/odoo/odoo19企业/odoo-19.0+e.20260101/odoo/addons/ai/static/src/ai_chat_launcher_service.js:65)。

### 4.2 Sources 与知识检索

`ai.agent._generate_response()` 在请求模型之前构建系统上下文与 RAG 资料，并提供 Topic 对应工具。`_build_rag_context()` 从启用的来源里取得相关片段，携带附件／来源信息。

对宝蓝的启发：生成前先取当前版本支持的示例，并把精确模板 ID、版本与摘要一起传入；生成后记录来源。宝蓝采用 Tencent Wiki 时，无需同时复制 Odoo 的本地向量索引体系。

证据：[生成流程](/Users/jianglang/odoo/odoo19企业/odoo-19.0+e.20260101/odoo/addons/ai/models/ai_agent.py:511)、[RAG 上下文](/Users/jianglang/odoo/odoo19企业/odoo-19.0+e.20260101/odoo/addons/ai/models/ai_agent.py:625)。

### 4.3 AI 工具的 schema 与执行结果

企业版 `ai/models/ir_actions_server.py` 将服务器动作标记为 AI 工具，定义描述与参数 schema；调用时校验参数，将数据注入执行上下文。代码类型动作执行后通过 `ai["result"]` 返回结果。

对宝蓝的启发：AI 使用固定工具，例如查示例、创建草稿和做样例验证；工具返回明确结构。客户脚本自身有独立的输入／输出协议，使用 `result` 或等价约定。

证据：[AI 工具目录](/Users/jianglang/odoo/odoo19企业/odoo-19.0+e.20260101/odoo/addons/ai/models/ir_actions_server.py:142)、[AI 工具执行](/Users/jianglang/odoo/odoo19企业/odoo-19.0+e.20260101/odoo/addons/ai/models/ir_actions_server.py:320)。

该实现部分流程检查外层 AI 动作后跳过工具自己的动作权限检查，并有相应提醒。宝蓝发布与执行流程应在每个工具重新核对目标与权限，不能直接照搬其调用假设。

### 4.4 `ai_server_actions` 的真实职责

本地 `ai_server_actions` 增加 `evaluation_type="ai_computed"` 和更新提示，随后调用 `_fill_ai_field()` 为目标字段生成并写入值。`ai_fields` 也是围绕字段值生成。

这可以用于生成一个 Text 字段的候选内容，但它本身没有提供五类脚本协议、模板版本、验证启用、在途版本固定和恢复。因此不能把该模块名理解为完整的 AI 代码生成发布系统。

另外，真正的 AI 选工具、执行服务器动作流程主要位于基础 `ai/models/ir_actions_server.py`，需要和单独的 `ai_server_actions` 模块区分。

证据：[ai_server_actions](/Users/jianglang/odoo/odoo19企业/odoo-19.0+e.20260101/odoo/addons/ai_server_actions/models/ir_actions_server.py:25)、[AI 填字段](/Users/jianglang/odoo/odoo19企业/odoo-19.0+e.20260101/odoo/addons/ai_fields/models/models.py:127)。

### 4.5 本地企业 AI 的直接依赖

该快照的 `LLMApiService` 接入 OpenAI 与 Google；配置从 Odoo 参数或环境变量读取，未发现宝蓝项目授权和 Tencent 专用适配。基础 `ai` 安装检查 PostgreSQL vector 扩展，RAG 使用本地 embedding 存储。

这些是该 2026-01-01 快照的事实，不能据此断言最新企业版仍完全相同。

## 5. 公开分支中的可参考基础机制

`saas-19.1` 和 `20.0` 的社区源码都保留 `ir.actions.server.code`、代码约束检查、服务器动作代码执行与历史展示／恢复。

两者 `_run_action_code_multi()` 仍调用 `safe_eval` 执行 Text 代码；通用服务器动作读取的是 `action` 返回值，主要用于 Odoo UI 动作，并不是为五类业务结果定义的协议。[saas-19.1 官方源码](https://raw.githubusercontent.com/odoo/odoo/saas-19.1/odoo/addons/base/models/ir_actions.py)、[20.0 官方源码](https://raw.githubusercontent.com/odoo/odoo/20.0/odoo/addons/base/models/ir_actions.py)

这证明数据库代码机制可以参考社区版实现，没必要为了这个能力切换 Odoo 20 或企业版。历史对照中的 Odoo 19 已具备基础能力；BlueWMS20 应按 Docker 实际 Odoo 20 版本签名实现自己的业务返回与触发位置。

原生服务器动作历史按数量清理，不能作为客户永久代码资产的唯一记录。精确代码全文、当前启用版本、模板引用与恢复材料仍进入宝蓝版本体系。

## 6. 许可与可复用范围

本地 `ai`、`ai_app`、`knowledge` 的清单为 OEEL-1。`ai_server_actions`、`ai_fields` 等部分模块清单为 LGPL-3，但依赖链仍指向企业 `ai`；不能把部分 LGPL 桥接模块当成完整的社区 AI 系统。

本项目继续基于社区版，因此参考企业架构与产品流程，独立实现对应扩展；不将 OEEL 核心源码复制到免费 BlueWMS 发布包。若未来提供企业版专用版本，可在有效企业订阅范围内按许可通过依赖扩展。[Odoo 官方企业许可](https://raw.githubusercontent.com/odoo/documentation/19.0/content/legal/licenses/enterprise_license.txt)

MuK 当前模块为 LGPL-3；通过独立模块继承、注册 provider、添加工具与 UI 扩展复用，保留第三方版权及许可信息。

## 7. 建议采用的具体实现

### 7.1 UI 与会话

在五个设置位置增加同一个按钮组件。首次点击由后端检查授权和设置访问范围，创建或恢复一个绑定的 MuK session，再通过聊天窗口或专用 Dialog 打开。

会话固定关联 `customization_id`、`hook_code`、公司、仓库／设备、基础代码版本和 schema 版本；页面导航不能改变本会话的发布目标。

AI 区域复用 MuK 消息、流式内容、追问和工具卡片；增加代码候选效果、样例测试、“保存草稿／保存并启用”以及启用状态。普通用户不用逐项选择规则。

### 7.2 Wiki 检索与生成

由宝蓝云端持有 Tencent 服务凭据；客户本地只持有自己的宝蓝 Key。检索顺序为：目标入口＋当前模块／协议版本＋客户范围→相关模板→取回完整批准版本→生成代码。

使用固定的草稿工具提交 `code`、需求说明、模板引用、输入／输出 schema 与样例，避免依靠聊天文本粘贴。服务器实际验证结构、内容和作用域。

生成服务与记忆服务分工：Wiki 提供资料与示例，模型负责生成，Memory 保留实施结论；保存启用由宝蓝业务服务控制。

### 7.3 固定工具与运行脚本

拟议固定工具：`blue_search_templates`、`blue_read_template_version`、`blue_read_hook_contract`、`blue_save_hook_candidate`、`blue_validate_candidate`、`blue_preview_candidate`。

启用按钮调用专用发布方法，检查冻结内容、授权、用户权限、测试结果和基础版本。若允许 AI 发起启用申请，它只能引用已验证的候选，用户确认仍绑定这一份内容。

AI 工具在实施时帮助生成与保存；日常 WMS 执行入口从 `blue.customization` 取得已启用版本，在本地受限制执行器运行，不再创建 AI 会话或请求云端模型。

### 7.4 模块划分沿用开发计划

| 模块 | 本轮确认的职责 |
|---|---|
| `blue_extension_contract` | 五类输入／输出协议、受限制执行器、能力目录和结果校验 |
| `blue_config_asset` | 定制设置、代码草稿、不可变版本、启用指针、导出与恢复 |
| `blue_ai_client` | MuK provider、五类按钮／弹窗、会话绑定、固定工具、Tencent 知识／记忆 API 适配与草稿保存 |
| `blue_wcs_extension`／`blue_barcode_extension` | 将实际业务方法接到统一脚本协议 |

客户端授权与云端项目账本分开；运行时脚本权限不依赖 Agent 的提示词或“允许本会话”的通用审批。

## 8. 开发前应冻结的最小协议

1. 首个入口选择条码，明确当前前端支持的策略键和返回结构。
2. 确定一条代表性需求与批准示例：如内部移库要求扫描来源、产品和目标库位。
3. 固定允许的 Python 语法与辅助方法、输入大小、结果结构和错误行为。
4. 定义代码版本创建、草稿验证、保存启用、并发冲突与历史恢复。
5. 固定会话目标绑定和 Wiki 模板版本引用，验证其他客户或公司不能越权。
6. 确定宝蓝网关采用的模型协议；验证流式、工具调用、取消与错误，不凭 provider 名称推断兼容。

## 9. 首个开发闭环的验收

- 点击条码设置中的 AI 按钮能打开绑定本设置的对话。
- 依据批准的 Wiki 示例生成代码，有明确来源版本。
- 草稿保存后尚不影响实际作业。
- 验证样例后保存启用，实际条码行为按代码结果变化。
- 非法调用、无界循环、未知返回键和版本冲突不能启用。
- 断开云端访问后，已启用的本地代码继续执行。
- 修改形成新版本，恢复原版后行为恢复；记录完整代码与操作来源。
- 即使用户导航到另一仓库，当前会话不能向新目标发布。

这个闭环通过后，把相同 UI、会话、代码版本与生成工具体系扩展到其余四个入口；各入口只增加自身输入准备、结果校验和标准业务接入。

## 10. 本次调查的限制

结论来自实际源码和官方仓库查询，不是安装测试结果。未验证 MuK 模块在目标 BlueWMS 数据库中的安装、腾讯实例能力、付费模型兼容或设备联调；这些列入首个开发闭环。当前阶段已明确 Odoo 20 社区路线和本地 Docker 工程边界，基础容器已运行；MuK／WMS 模块安装与业务验证仍待实施，不要求安装企业模块。

## 2026-10-12 可编辑上架策略首期交付

用户已批准清单 3、4 的两个标准示例闭环。`blue_extension_contract`、`blue_config_asset`、`blue_stock_putaway` 已安装到本地 Docker 开发库，79 项联合测试通过。代码可以前端编辑，未来 AI 通过同一草稿接口提交，验证和发布使用同一流程。准确代码与版本在 Odoo 数据库保存，现场执行不请求云端。Tencent 知识／记忆 API 适配合并到拟开发的 `blue_ai_client`，不独立建 `blue_ai_memory`；本轮没有连接云端模型或 Key。

首期仅实现上架合同，场景草稿暂合并在 `blue.config.profile`，配合不可变版本／发布快照。五类完整场景、单点覆盖、云端同步队列和其他业务合同仍按后续计划推进。两个示例为优先集中，散件容量不足可以拆分；包裹／托盘／WCS、独占库位、精确来源追踪不在首期。开发库未自动绑定或启用仓库策略。详情见 [上架策略交付与使用说明](/Users/jianglang/odoo/bluewms/docs/migrations/putaway-policy-20.md)。

## 2026-10-12 系统优先与整托盘增强

用户确认补充代码只能进一步限制／排序, 不接管 Odoo。`blue_stock_putaway` 和 `blue_extension_contract` 已升级至 `20.0.1.1.0`。原生规则范围和优先级、存储类别、托盘数量、重量与混放设置先检查, 然后执行补充代码。新增同批次号限制示例支持不同产品, 按批次号文本比较。整托盘及内箱去重, 计入已上架和待上架托盘, 不自动拆托。112 项联合测试与独立事务最后一个托盘位争用检查通过。详情见 [托盘增强交付](/Users/jianglang/odoo/bluewms/docs/migrations/putaway-pallet-enhancement-20.md)。

## 2026-10-12 原生规则选择增强场景

用户确认将增强场景直接绑定到 stock.putaway.rule. 原生上架规则列表新增“增强策略”选择框, 策略定义移除仓库／作业类型／增强适用库区三个字段. 场景可复用, 单据按每条原生规则固定代码版本. 120 项联合测试及最后一个托盘位并发检查通过. 新方式见 [原生规则绑定增强策略](/Users/jianglang/odoo/bluewms/docs/migrations/putaway-rule-binding-20.md)。
