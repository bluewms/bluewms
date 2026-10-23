# 条码扫描策略 /1

hook: `barcode_policy`. 合同: `barcode_policy/1`. 更新: 2026-10-21. 状态: 本地合同及准确试算已实现;云端知识须独立批准和发布,Git 合并不会自动开放联网生成.

## 输入与执行

输入只有 JSON: `request` 和 `candidates`. request 包含 `phase`（parse/decide）、完整 `raw`、`context` 和 `parsed`. parse 阶段 candidates 为空、parsed 为空. decide 阶段接收固定服务确认的候选明细与已校验解析结果. 原码最长 8192 字符,候选最多 200 条,输出文本最长 512 字符.

context 包含公司、作业种类、会话及已确认扫描步骤. 作业 parse 的 `context.standard` 提供原生／基础解析结果,有歧义时为空;不能把它当成用户权限或直接执行的授权. 首页没有作业类型,使用公司通用配置;作业类型可覆盖. 策略随会话固定,不在每次扫码调用云端 AI.

## parse 输出

必须准确返回 kind、code、quantity、lot、location、package、uom、reason. kind 仅 product/location/lot/package;code 非空. quantity 为有限正数,表示本次增量;未使用的文本字段为空字符串. product 的 code 匹配产品或已配置包装单位条码. location 指来源位置,追踪和库存维度由本地复核. 不得从原码生成任意模型、记录方法、HTML 或前端命令.

解析格式一旦匹配但分隔符、商品或数量错误就停止,不回退为加 1. 多字段作为一个有效事件提交;缺追踪信息时先补扫,不提前增加数量. 同名批次、重码、多位置或多货主时必须唯一匹配,否则提示补扫／选择.

## decide 输出

返回 action、keys、reason,以及可选 after. action 为 count/prompt/select. count 的 keys 必须且只能包含一个真实候选 key;prompt 和 select 的 keys 为空. select 用于已解析的位置、源包裹或批次选择,固定服务仍复核范围. 多候选应通过明确规则选择一行或提示选择,当前 /1 不接受跨多行数量分摊输出.

after 可为空或 next_group/wcs/validate/pack. 它只请求固定注册的后续动作;装箱和 WCS 必须已有人工授权,本地再校验. 先保存有效扫码结果,再处理后续动作,失败不能重新累计本次扫描. 原生库存验证保留警告和欠单流程,完成一组不等于整单记账.

## 受限语法与二维码

复用纯 JSON 解释器的条件、对象读取、有限切片、标量转换、单层候选循环及本地列表构造. 不允许 import/eval/exec、ORM、网络、任意对象属性、正则或通用 split. 本合同增加 `between(raw, separator, start, end)`: 分隔符长 1–16 字符,start/end 为 1 起算的出现次数,满足 1 <= start < end <= 64. 空段保留,缺少边界明确失败.

完整接口描述见[合同附件](barcode-policy-v1-contract.json),准确示例见[案例目录](examples/README.md). 每份新草稿须提供 2–20 个 expected_result 准确试算,同时覆盖 parse 和 decide,验证后人工发布. 案例通过不等于新代码或客户现场已验证.
