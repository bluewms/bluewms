# 验证与验收

更新: 2026-10-26。验证分层记录，不累加不同日期/范围的历史数字。

| 层次 | 入口 | 能证明什么 |
|---|---|---|
| 文档/知识 | 链接检查、`python3 scripts/validate_ai_wiki.py --offline` | 准确代码/输入/预期、合同附件和文档链接一致 |
| 只读云端网关 | `python3 -m unittest discover -s docs/cloud/tests` | 身份、ACL、合同、范围、版本与摘要门禁 |
| Odoo 模块 | 各模块 tests，指定隔离 `*_test` 数据库及匹配 dbfilter | 模型、业务约束、权限与回归 |
| 并发/恢复 | scripts 中 inventory/barcode/putaway/wcs 并发及发送恢复脚本 | 真实事务的幂等、串行与恢复行为 |
| 实际界面 | 独立预览和真实键盘事件 | 操作、导航、焦点、数量与向导返回 |
| 外部联调 | 实际模型工具调用、ERP/设备/PDA/相机 | 对应现场的真实端到端行为 |

纯数据解释器通过不等于 ORM、真实模型或设备通过；页面存在不等于已安装。禁止在主库运行库存/设备测试夹具。业务操作前后保留基线，升级见 [运维说明](../operations/upgrades.md)。

[条码验收场景](barcode-scenarios.md) 保留逐项异常和恢复用例。其他领域的业务回归保存在模块 tests；不把测试用的旧案例定义安装到生产。

历史准确来源锁和脱敏验收 JSON 位于 [validation](../validation/README.md)，原始日志和备份在私有运行目录。旧阶段日志从 Git 历史查阅；当前云端状态见 [发布记录](../wiki-publication/README.md)。
