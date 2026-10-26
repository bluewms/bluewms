# Odoo AI 增强代码生成知识库

用途：供 **Odoo 内的宝蓝代码助手**理解用户业务需求，并生成指定入口的补充代码和测试。维护日期：2026-10-26。

这里的知识面向运行在 Odoo 中的代码生成助手，不面向仓库源码开发。内容只包含生成通用规则、各业务入口的输入／输出／限制及验证过的代码示例。项目架构、Git 操作、开发机安装、云服务器配置和联调历史单独放在工程文档中，不作为本知识库的生成资料。

## 通用生成说明

| AI 需要了解什么 | 资料 |
|---|---|
| 自己的任务、输入与输出、能力边界和代码取舍 | [AI 代码生成通用规则](basics/overview.md) |
| 如何读取当前资产、追问业务需求、提交并验证草稿 | [生成步骤与工具规则](basics/ai-generation-workflow.md) |
| 一个完整参考案例应包含什么 | [案例格式](templates/example-template.md) |

知识按“通用规则＋五类业务”分别维护在云端 Wiki；Odoo 不扫描本地文件夹充当示例兜底。读取方式以当前会话实际提供的工具为准，只有取得对应规范和案例正文后才能参考生成。知识只能解释已有能力，实际生成以当前会话返回的本地接口合同为准。

## 五类 AI 入口

每类独立保存 `specification.md` 规范和 `examples/` 案例。示例中的字段、语法和输出只能用于其标明的合同，不能跨领域照搬。

| 生成入口 | hook | 规范 | 示例 | 当前可用性 |
|---|---|---|---|---|
| 上架策略 | `putaway_policy` | [上架生成规范](domains/putaway/specification.md) | [三个已验证案例](domains/putaway/examples/README.md) | 可读取、提交并验证草稿；人工发布 |
| ERP 接口 | `erp_mapping` | [ERP /1 规范](domains/erp/specification.md) | [两个准确案例](domains/erp/examples/README.md) | 安装 blue_erp_interface 后可生成与验证草稿；云端批准及网关路由就绪后可生成；当前版本以发布回执为准 |
| WCS 生成策略 | `wcs_creation` | [WCS /4规范](domains/wcs/specification.md) | [已验证案例](domains/wcs/examples/README.md) | /4 合同及草稿工具已实现；生成前必须实际取得本领域批准正文 |
| 设备连接接口 | `device_protocol` | [设备协议规范](domains/equipment/specification.md) | [TUSK 准确案例](domains/equipment/examples/README.md) | 安装 device_protocol/1 后可生成、试算和验证草稿；人工发布；其他厂家见协议参考 |
| 条码扫描策略 | `barcode_policy` | [条码 /1 规范](domains/barcode/specification.md) | [准确案例与边界](domains/barcode/examples/README.md) | 安装 blue_barcode_extension 后可本地试算、验证与人工发布；云端批准后可用对应 Task 生成；当前批准版本以发布回执为准 |

只有当前入口已开放且合同匹配的规范／案例可用于生成。planned 文稿只帮助沟通业务需求，不能据此发明工具、接口字段或执行代码。每份新草稿都必须重新验证，参考案例的验证结果不能替代新代码的验证。

知识文稿 verified 表示准确代码与声明用例已通过当前纯数据解释器,不代替真实 ERP/设备/PDA 或新草稿的验证. 云端实际发布记录由维护者单独保存,不在生成知识中嵌入服务器配置或私有标识.
