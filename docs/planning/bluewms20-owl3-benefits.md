# Odoo 20 与 Owl 3 对 BlueWMS 开发的帮助

> **2026-10-17 维护入口**：本文保留原日期的调查或交付记录；当前基础说明、五类 AI 规范与示例统一维护在 [Odoo AI 代码生成知识库](../wiki/README.md)。上架 AI 已读取云端批准示例，准确代码、本次测试与验证发布仍在本地；其他四类 AI 入口分别按合同验收。

## 2026-10-12 命名与分类更新

新 20 模块统一采用 `blue_<领域>_<功能>`：库存 `blue_stock_*`、设备 `blue_wcs_*`，条码独立为 `blue_barcode_*`；所有模块直接位于 `bluewms` 下，不建立分类目录。非 `blue_` 的额外 addon 按第三方来源管理，官方 Odoo 基础保持原名。旧 19 名称保留为代码调查和迁移引用，历史 `blueprj_*` 及单功能名称不作为新 20 命名标准。详细目标、来源核查和依赖边界见 [模块分类与命名规划](/Users/jianglang/odoo/bluewms20-doc/bluewms20-module-architecture.md)。

## 前端开发环境约定（2026-10-12）

条码、场景工作台和 AI 弹窗在本机 Docker Odoo 20 中开发与验证。自研及第三方前端模块均放在宿主机 `bluewms` 的直接子目录，挂载到容器 `/mnt/extra-addons`，通过 [bluewms/bluewms](https://github.com/bluewms/bluewms) 管理代码、上游版本和本地改动；不修改镜像中的 Odoo／Owl 核心。

下文 Owl 版本与 API 结论属于指定提交的调查结果，实际组件写法应核对容器所带版本。相邻 `odoo20` 源码当前未挂载成运行源码；宿主机文件修改已通过挂载进入容器，但 Python 重启、模块升级及前端资源重建仍按改动执行。完整环境、目录和版本约定见 [BlueWMS20 正式开发计划](/Users/jianglang/odoo/bluewms20-doc/bluewms20-development-plan.md) 的 2.4 节。

原调查日期：2026-10-11｜工程约定更新：2026-10-12  
适用方案：场景统一配置＋五类入口单点调整＋AI 生成本地数据库脚本。  
性质：源码与官方文档评估；性能收益尚未通过 BlueWMS20 实测。

## 1. 结论

**Odoo 20 与 Owl 3 更适合建设我们的场景配置工作台、AI 对话与状态展示。最主要的收益是配置联动更容易维护、共享状态更清晰、组件接口更明确，以及减少无关状态更新的机会。**

这套前端基础不会自动完成五类脚本的生成、后台验证、版本启用和灾难恢复；这些仍由宝蓝模块与云端服务实现。

## 2. 本次确认的实际版本

核查的 Odoo 20 提交为 `9fbff4fa4b81719496dc579d77e3f11b82c42efc`，随包 Owl 为 **3.0.0-alpha.49**。资产清单同时加载 Owl 2 兼容代码。开发应锁定 Odoo 20 自带版本与组件用法，不自行替换成上游最新 Owl 包。[随包 Owl 源码](https://raw.githubusercontent.com/odoo/odoo/9fbff4fa4b81719496dc579d77e3f11b82c42efc/addons/web/static/lib/owl/owl.js)

上游 Owl 3 文档仍有草稿和实验性 API。以下设计根据官方说明和随包能力提出；具体写法、取消机制和验证模式以锁定版本核对。特别是异步计算接口不作为首期必须依赖。

本地 `owl-master/package.json` 仍为 2.8.1，不能将该目录的示例当作 Owl 3 开发规范。

## 3. Owl 3 特性与项目收益

### 3.1 Signals／Proxy：明确区分场景、草稿和生效状态

Owl 3 以 signal、proxy 和计算值组织响应式状态。状态可以在组件或共享上下文中被消费，相关读取建立更新关系。[官方响应式说明](https://raw.githubusercontent.com/odoo/owl/master/doc/v3/owl/reference/reactivity.md)

应用设计：分别保存当前场景标识、正式版本、草稿、选中的定制点、生成任务状态与验证结果。

实际收益：AI 正在输出时更新对话与进度区域；用户修改条码草稿时更新条码摘要和相关提示；不用把整个场景和所有聊天记录都视为一个频繁变动的大状态。

草稿与生效配置分离是我们的设计责任。发布成功由服务器返回新场景版本后，再更新正式状态，避免把“AI 已生成”误显示成“已启用”。

### 3.2 Computed：配置联动和差异展示更容易保持一致

`computed` 自动追踪依赖，并按需要重新计算。它适合派生信息，例如修改项数量、单点覆盖标识、错误摘要和界面上的启用条件。[官方计算值说明](https://raw.githubusercontent.com/odoo/owl/master/doc/v3/owl/reference/computed_values.md)

项目应用：

- 统一显示“本次修改 1 个入口，另外 4 个保持原版”。
- 单点改动后更新场景摘要、差异和关联提示。
- 根据草稿变化使旧验证结果失效，提示重新验证。
- 显示是否存在未保存变更、版本冲突或待解决事项。

复杂跨入口业务校验仍由后端执行；前端 computed 汇总和展示结果。这样可以减少多个事件回调分别修改同一批标记造成的界面不一致。

### 3.3 Plugin：五个定制点共享同一场景上下文

Owl 3 的插件机制提供可组合的状态与功能共享。[官方插件说明](https://raw.githubusercontent.com/odoo/owl/master/doc/v3/owl/reference/plugins.md)

拟议 `SceneEditorPlugin` 在一个场景工作台范围内提供：场景 ID、基础版本、草稿、各入口摘要、单点覆盖、验证结果与发布操作。

ERP、WCS、设备、上架、条码的卡片和弹窗读取同一上下文。单点调整完成后，工作台统一更新差异与状态，不维护五套各自认为生效的配置副本。

插件按工作台／会话范围管理，不使用一个全局可变对象混合不同客户和仓库。服务器仍验证会话目标、公司、场景与基础版本。

未来标准设备模块可贡献自身摘要或效果预览组件，沿用同一发布接口，不复制整套 AI 设置页面。

### 3.4 useProps 与类型定义：统一组件更容易扩展

Owl 3 使用 `useProps` 和类型定义描述组件接收的数据，支持默认值和更明确的接口；props 校验主要用于开发模式。[官方 Props 说明](https://raw.githubusercontent.com/odoo/owl/master/doc/v3/owl/reference/props.md)

我们可以复用一个“定制点卡片”和一个“AI 调整弹窗”，明确声明入口代码、目标范围、基础版本、显示状态和事件回调。新增设备或 ERP 扩展时按相同结构提供数据，减少参数传错造成的维护问题。

这与前面讨论的配置类型有关，但用途不同：配置定义描述业务值，props 类型描述前端组件之间传的数据。客户端类型检查不能代替后端 schema 与业务校验。

### 3.5 Effect／Scope／事件监听：更好管理异步任务和扫码焦点

Owl 3 的作用域与副作用机制可以组织生命周期和清理工作。[官方 Scope 说明](https://raw.githubusercontent.com/odoo/owl/master/doc/v3/owl/reference/scope.md)

项目应用：AI 弹窗关闭时清理显示订阅，切换场景时避免旧响应回填到新目标，条码页面销毁后移除键盘与设备事件监听，验证结束后按操作流程恢复输入焦点。

我们仍需明确请求编号、场景绑定、去重、取消和焦点规则。界面关闭不会自动撤回已经送到云端的任务或设备命令；后台任务和本地发布状态由服务器跟踪。

### 3.6 ErrorBoundary：让失败限制在相关面板

Owl 3 提供声明式错误边界，可以为子组件失败显示替代内容。[官方错误边界说明](https://raw.githubusercontent.com/odoo/owl/master/doc/v3/owl/reference/error_boundary.md)

对代码预览、单点模拟结果或自定义设备摘要设置边界，组件异常时显示错误与重试入口，场景工作台和保存在父级／服务端的草稿仍可访问。

模型调用失败、代码验证错误和业务发布失败需要以明确结果展示；不能捕获错误后仍显示验证通过，也不能靠前端错误边界恢复数据库或设备动作。

### 3.7 Registry／Resource 与 Devtools：扩展和调试更有结构

Owl 3 的 Resource 可管理排序的响应式贡献项并按所属组件生命周期移除，Registry 适合有标识的注册项。[官方 Resource 说明](https://raw.githubusercontent.com/odoo/owl/master/doc/v3/owl/reference/resources.md)

应用于标准模块提供的场景摘要、工具栏命令、设备预览组件和受支持的条码处理器。实际接入优先遵循 Odoo 20 当前的 registry 与服务，不无差别重建已有机制。

官方 Devtools 可以查看组件、signal／computed／proxy 状态和渲染事件，帮助定位状态更新与频繁重绘。[官方 Devtools](https://raw.githubusercontent.com/odoo/owl/master/doc/v3/owl/tools/devtools_guide.md)

我们可测 AI 流式输出是否引起条码区域反复刷新，检查为何一个单点改动触发了全场景更新，再按证据优化。

## 4. 用户能感受到的变化

| 使用场景 | 计划中的提升 |
|---|---|
| 配置整套入库场景 | 一个工作台显示五类入口、当前版本、草稿差异和验证状态 |
| 只修改一个点 | 对话打开当前点，其他点保持原版本，主页面同步展示影响 |
| AI 检索与生成 | 分阶段显示检索示例、生成草稿、样例验证和等待启用 |
| 配置存在冲突 | 对应入口显示具体问题；解决后同步更新整体状态 |
| 查看代码与测试 | 普通用户看效果，技术人员展开代码、样例与精确来源 |
| 条码作业 | 减少与扫描无关的界面更新，明确维护焦点与事件生命周期 |
| 设备摘要组件出错 | 相关面板显示错误与重试，保留场景草稿和其他入口 |

这里的“计划中的提升”需要通过组件设计和测试实现，不能将框架能力写成已经完成的产品行为。

## 5. Odoo 20 后端变化与前端的配合

后端按类型管理配置、明确批次与单位模型，为前端的统一场景摘要、类型化输入和准确差异提供数据。五类脚本版本、发布与恢复仍由统一场景服务管理。

后端返回包含目标场景、基础版本、变更项、来源模板、验证状态和错误范围的结构化结果。前端负责协调展示与操作；“是否可启用”“是否越权”“代码是否符合协议”由后端重新检查。

20 的具体单位字段、批次依赖、配置接口和运行环境要求见 [平台选型与迁移评估](/Users/jianglang/odoo/bluewms20-doc/bluewms20-platform-assessment.md)。

## 6. 当前工程的迁移成本

静态检索得到下列出现次数，用于估计范围，不是确定的缺陷数；其中含 import、注释或重复使用：

| 范围 | useState | this.props | this.env | static props | t-esc |
|---|---:|---:|---:|---:|---:|
| 现有 stock_bluebarcode 前端 | 12 | 69 | 120 | 15 | 34 |
| 本地 MuK AI 19 前端 | 28 | 131 | 7 | 16 | 89 |

Owl 3 对状态、props、模板和引用有重要迁移变化，不能只修改模块清单。参考官方迁移指南，但按 Odoo 20 的实际兼容层核对。[官方迁移指南](https://raw.githubusercontent.com/odoo/owl/master/doc/v3/owl/migration_owl2_to_owl3.md)

两个已经从 Odoo 20 源码确认的细节：

1. 兼容层遇到旧 `static props/defaultProps` 会抛错，应该改用 `useProps`，不能假定兼容层全部接管旧组件。
2. Odoo 20 仍提供 `useService` 和部分 env／布局副作用兼容接口，不应把上游迁移草稿里的“服务被移除”理解为所有现有 Odoo 服务都必须重写。

证据：[Odoo 兼容层](https://raw.githubusercontent.com/odoo/odoo/20.0/addons/web/static/src/owl2/owl3_compatibility_layer.js)、[Odoo 服务 hook](https://raw.githubusercontent.com/odoo/odoo/20.0/addons/web/static/src/core/utils/hooks.js)。

MuK 使用正式的 20 分支并锁定提交；自有条码前端逐个迁移并验证。Odoo 20 的标准 Dialog 已采用 signal／proxy／useProps，可以作为 AI 场景弹窗实现参考。[标准 Dialog](https://raw.githubusercontent.com/odoo/odoo/20.0/addons/web/static/src/core/dialog/dialog.js)

## 7. 开发落地顺序

1. 锁定 Odoo 20 与 MuK 20；确定随包 Owl API 和现有兼容层。
2. 迁移最小条码组件集合，验证加载、扫码、焦点、装箱、批次和 WCS 按钮。
3. 新建场景工作台、定制点卡片、AI 弹窗、差异摘要和验证面板，共用一个场景编辑上下文。
4. 前端明确区分正式版本、草稿和单点覆盖，与后端发布协议对应。
5. 给所有异步响应绑定场景／任务编号，验证关闭、切换与重复点击。
6. 测量高频扫描、长 AI 对话和大差异列表中的响应与更新，依据实际瓶颈优化。
7. 逐步减少新自研模块对兼容 API 的依赖；已稳定的上游 Odoo／MuK 用法按其版本维护。

## 8. 收益的限度

Owl 3 不保证整个系统自动提速。AI 生成耗时由模型与检索决定，库存与 WCS 耗时取决于后端事务、数据量和设备协议。异步渲染也不是 Owl 3 首次具备的能力。[官方并发模型](https://raw.githubusercontent.com/odoo/owl/master/doc/v3/owl/reference/concurrency_model.md)

本项目应以界面一致性、单点修改可追踪、组件复用与维护性作为首要收益，再通过实测确认性能提升。客户生成的定制代码仍为后端受限制脚本；Owl 3 前端由标准模块提供支持能力，不在数据库里动态执行客户生成的任意浏览器代码。

## 2026-10-12 可编辑上架策略首期交付

用户已批准清单 3、4 的两个标准示例闭环。`blue_extension_contract`、`blue_config_asset`、`blue_stock_putaway` 已安装到本地 Docker 开发库，79 项联合测试通过。代码可以前端编辑，未来 AI 通过同一草稿接口提交，验证和发布使用同一流程。准确代码与版本在 Odoo 数据库保存，现场执行不请求云端。Tencent 知识／记忆 API 适配合并到拟开发的 `blue_ai_client`，不独立建 `blue_ai_memory`；本轮没有连接云端模型或 Key。

首期仅实现上架合同，场景草稿暂合并在 `blue.config.profile`，配合不可变版本／发布快照。五类完整场景、单点覆盖、云端同步队列和其他业务合同仍按后续计划推进。两个示例为优先集中，散件容量不足可以拆分；包裹／托盘／WCS、独占库位、精确来源追踪不在首期。开发库未自动绑定或启用仓库策略。详情见 [上架策略交付与使用说明](/Users/jianglang/odoo/bluewms/docs/migrations/putaway-policy-20.md)。

## 2026-10-12 系统优先与整托盘增强

用户确认补充代码只能进一步限制／排序, 不接管 Odoo。`blue_stock_putaway` 和 `blue_extension_contract` 已升级至 `20.0.1.1.0`。原生规则范围和优先级、存储类别、托盘数量、重量与混放设置先检查, 然后执行补充代码。新增同批次号限制示例支持不同产品, 按批次号文本比较。整托盘及内箱去重, 计入已上架和待上架托盘, 不自动拆托。112 项联合测试与独立事务最后一个托盘位争用检查通过。详情见 [托盘增强交付](/Users/jianglang/odoo/bluewms/docs/migrations/putaway-pallet-enhancement-20.md)。

## 2026-10-12 原生规则选择增强场景

用户确认将增强场景直接绑定到 stock.putaway.rule. 原生上架规则列表新增“增强策略”选择框, 策略定义移除仓库／作业类型／增强适用库区三个字段. 场景可复用, 单据按每条原生规则固定代码版本. 120 项联合测试及最后一个托盘位并发检查通过. 新方式见 [原生规则绑定增强策略](/Users/jianglang/odoo/bluewms/docs/migrations/putaway-rule-binding-20.md)。
