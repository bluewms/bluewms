# 结构化核对记录

本目录保留既有来源锁、脱敏验收与历史发布摘要，统一从原 migrations/wiki-publication 目录迁入。文件内的日期、来源提交和结果对应当时版本，不表示本轮重新执行，也不代表当前部署状态。

- `*source-lock.json` 保留相关模块来源与版本核对信息。
- `*.validation.json` 保存当时的模块/模型/业务验收范围。
- 既有 Wiki manifest/qa JSON 保存当时的准确来源及问答结果。

当前使用入口见 [指南](../README.md)，新的准确发布回执见 [发布记录](../wiki-publication/README.md)。私有 Key、实例 ID、原始日志、数据库与附件备份不放本目录。

2026-10-26 原生会话接入验证见 [身份与无声明关联实测](native-session-routing-20261026.json): 20 项网关回归、五领域无 Task-Agent 声明关联的真实接口检查，以及同事环境条码真实模型连接检查；不代表完整草稿生成或实机验收。
