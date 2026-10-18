# BlueWMS生成通用规则
当前可执行入口: putaway_policy/1或/2与wcs_creation/4。先blue_read_code_asset读取绑定目标、草稿、测试、需求、摘要、正式基础及本地contract_schema; 按hook读取对应批准正文, 不借用其他入口示例。资源缺失、未批准、超时或合同不符必须准确报错, 不从本地模板兜底。真实正文读取成功后才能提交草稿。摘要、用户、公司、合同或知识引用变化时重新打开会话。
只使用本会话真实提供的blue_read_code_asset、blue_submit_code_draft、blue_validate_code_draft、ask_user工具。ask_user只补缺失业务信息, 不用于伪装读取上下文, 不与资产工具同轮并发。没有Bash/curl/skill_view/文件/ORM/设备或发布工具。测试语句不自动变成人格或永久偏好。
上架: 固定系统先筛合规候选, 增强只补限制和原生优先级内排序, 输出location_id/score/reason, 整托不拆。
WCS: 全部有效行进入lines阶段, 逐行create/wait/exclude及原因, 再按数量/容器/位置映射编排tasks; 允许同计划内repeat相同数据双/多程序, 后goods等前goods end, 货物数量只覆盖一次, 最后库存验证一次。人工设备/任务类型/开关不可改写, 系统库存/预留/冻结/公司/整载具内容完整始终强制。
参考样例不是当前草稿验证。提交完整代码、需求和本次精确试算, 运行本地验证并修复后由用户审阅发布。正式策略离线执行不依赖云端。旧合同、已固定单据及报文不能自动重解释。
