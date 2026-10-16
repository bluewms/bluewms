# BlueWMS 项目 Wiki

更新：2026-10-17。这里是人工维护、Git 审阅的知识来源；供 AI 使用的批准正文发布到 TencentDB-Agent-Memory。Odoo 不会扫描本目录生成代码，修改文件也不会自动更新云端。

## 先看哪里

| 需要维护的内容 | 文件 |
|---|---|
| 项目分工、本地与云端各保存什么、Code Graph 的定位 | [基础说明](basics/overview.md) |
| AI 收到什么、如何读取资产、提交、验证及发布 | [AI 生成工作流](basics/ai-generation-workflow.md) |
| Tencent 服务、团队、Agent、Task、Wiki 与 Skill 配置 | [TencentDB-Agent-Memory 配置](basics/tencent-memory-configuration.md) |
| 新增、审阅、发布、失效和历史记录怎么维护 | [维护约定](maintenance.md) |
| 本地文档与现有云端资源如何对应 | [发布映射](publication-map.json) |
| 新增示例时复制的格式 | [示例模板](templates/example-template.md) |
| 2026-10-16 配置纠正、联调与旧决策证据 | [历史记录](history/2026-10-16-configuration-and-verification.md) |

## 五类 AI 入口

每类一个目录；`specification.md` 只维护规范，`examples/` 只维护案例。每个可执行案例独立一页，代码、测试和证据放在一起。

| 业务领域 | hook | 规范 | 示例 | 实现状态 |
|---|---|---|---|---|
| 上架策略 | `putaway_policy` | [上架规范](domains/putaway/specification.md) | [示例目录](domains/putaway/examples/README.md) | 已实现 AI 草稿闭环，三个标准案例已验证 |
| ERP 接口 | `erp_mapping` | [ERP 规范草案](domains/erp/specification.md) | [需求示例](domains/erp/examples/README.md) | AI 合同与工具待实现 |
| WCS 生成策略 | `wcs_creation` | [WCS 规范草案](domains/wcs/specification.md) | [需求示例](domains/wcs/examples/README.md) | 已有 WCS 业务与手动策略，AI 入口待接入 |
| 设备连接接口 | `device_protocol` | [设备规范草案](domains/equipment/specification.md) | [需求示例](domains/equipment/examples/README.md) | AI 合同与工具待实现 |
| 条码扫描策略 | `barcode_policy` | [条码规范草案](domains/barcode/specification.md) | [需求示例](domains/barcode/examples/README.md) | AI 合同与工具待实现 |

当前实现说明以开发提交 `ad35793` 为依据，交付版本和验证范围见 [上架云端知识接入](../migrations/putaway-cloud-knowledge-20.md)。整理时该提交位于待合并的 PR #4；不要把开发机已安装理解为所有环境已经升级。

## 长期增加内容

1. 改共同原则、流程或配置，进入 `basics/`；改某类输入／输出／限制，进入该类规范。
2. 新案例从模板复制到该类 `examples/`，用稳定的英文文件名，并在该类示例目录添加链接。
3. 规划案例标记 `planned`；有准确代码和验证证据后标记 `verified`；云端批准发布另记状态，不能仅靠文件标签认定批准。
4. 经 PR 审阅后按发布映射更新云端，记录来源提交、发布版本和摘要。新增领域时创建相同结构并更新本页。

本目录不保存凭据、客户原始聊天、数据库备份或真实业务单据。运维记录按日期进入 `history/`，日常规范不要混入某次会话的排错经过。
