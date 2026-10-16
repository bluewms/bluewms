# blue_ai_client 模块与设置

更新：2026-10-16。现行依据：[云端知识、Tencent 配置与 AI 工作流](../architecture/cloud-knowledge-and-ai-workflow.md)。

## 已实现

- 技术名 `blue_ai_client`，独立扩展 MuK provider 与资产页面，不修改上游核心；使用 Chat Completions。
- Provider 共用服务地址和模型；每个 Odoo 用户保存自己的业务用户 Key 和准确的 Agent 名称。
- 设置在 MuK AI → 设置 → 宝蓝云端服务；每用户连接在配置 → 宝蓝用户连接维护。没有本地充值／扣费账本及剩余额度展示。
- 按代理初始化表单准确选择团队、Agent、任务，保留返回的标识；不猜 ID、不替换未知名称。当前团队固定 `odooAI`、任务固定“日常任务”。
- 资产页面创建会话并绑定当前资产、草稿摘要和正式基础版本，MuK 主持本地工具循环。
- `blue_read_code_asset` 读取绑定资产的草稿、测试、需求、接口版本与摘要；当前仍附带本地模板示例。
- `blue_submit_code_draft` 和 `blue_validate_code_draft` 以当前用户权限工作，检查并发修改和正式版本冲突；发布由用户操作。

## 云端已配置

TencentDB-Agent-Memory 1.0.2 已建立一个项目团队、各用户 Agent、五个业务分类 Task、团队共享 Wiki 及五个共享 Skill；更正画像与三层记忆提炼规则。共享访问、私有记忆隔离、Wiki 检索及三个示例九个用例已验证。

这些配置不表示本地工具能读取全部云端正文。代理的 shell/curl 加载说明与当前 Odoo 受限工具不匹配。

## 待实现

1. 受限只读 Skill／Wiki 检索及读取，返回批准状态、准确正文、来源和版本，执行用户／Agent 权限与资源限制。
2. 本地提供完整机器可读合同；当前 contract 仅版本标识。
3. 按资产 hook 选择五类 Task，处理会话身份、旧“日常任务”和旧会话兼容。
4. 把模板的运行定义与示例正文分离，验证后停止本地通用示例回传；继续保存策略代码、测试及发布历史。
5. 按固定合同扩展 ERP、WCS、设备和条码四类 AI 入口。

首期不拆 `blue_ai_memory`、私有示例库式 `blue_ai_skills` 或授权模块，不复制现有资产发布系统。官方 Skill 保留开发机器安装与云端分发两个位置，但不在客户 Odoo 另建知识库。

使用说明见 [模块 README](../../blue_ai_client/README.md)；历史验证见 [首期交付](../third-party/blue-ai-client-install-2026-10-13.md)。
