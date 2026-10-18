# 设备连接接口 AI 生成规范

hook：device_protocol。合同：device_protocol/1。复核：2026-10-18。适用安装本合同的实例；云端批准与本地安装状态分别确认。

## 人工设置与类别资产

设备类别维护一份协议资产，所属设备共用类别连接。人工创建类别并填写适配方式、公司、负责人、地址、任务路径、App Key／Token、App Secret、回调凭据、认证方式及允许回写范围。设备从设备页面创建，维护实例编码和任务模板。

AI 只修改绑定资产的代码、需求和试算，不创建类别、设备、Task 或模块，不改地址、路径、认证、密钥、自动开关、公司及允许库区。真实密钥不在生成输入内。非秘密厂商参数通过人工配置的 parameters 传入；认证值只放专用凭据字段。

## 三个阶段及准确结构

完整输入始终是 request 和 candidates 两个键。request 必须包含 phase、task、message、http_status、parameters。代码写在顶层，赋值给 result，不用 def／return／import。完整字段与输出见 [合同附件](device-protocol-v1-contract.json)，本实例工具返回的 contract_schema 优先。

| 输入 | 含义 |
|---|---|
| phase | request、response、callback |
| task | task_id、source、destination、template、carrier、device_code、role、operation |
| message | 厂商响应或单条回调 JSON 对象；下发阶段为空对象 |
| http_status | 响应状态整数，其他阶段为 0 |
| parameters | 人工批准的非秘密参数对象 |
| candidates | 至多 200 条货物；product_code、quantity、uom、lot，实际字段以本地合同为准 |

role 为 goods／empty_supply／empty_return，operation 为 incoming／outgoing／internal。不存在 ORM 对象，不能假定未返回字段。

| 阶段 | result 准确结构 |
|---|---|
| request | body 一个键，值为厂商 JSON 请求对象；地址、POST 路径和请求头由固定服务注入 |
| response | state 和 reason；state 为 accepted／rejected／unknown，reason 为至多 512 字符说明 |
| callback | task_id、event、point、subposition、destination_code、response 六个键；前五个为至多 256 字符文本，response 为有界厂商应答对象 |

callback.task_id 必须等于当前任务号，event 只能为 end。没有子位置或库存库位更新时，对应字段填空字符串。HTTP 非 200、超时、无效或超大响应按 unknown 处理，不因请求发出就认定接受或完成。rejected 只能用于明确的厂商拒绝，不猜测或盲目重发。

## 完成位置回写

- subposition：提取／转换细点，固定服务更新当前任务关联包裹或载具，不因此改变库存库位。类别必须人工允许该能力。
- destination_code：提取／转换既有库位编码。类别须人工允许并指定目的库区；固定服务在同公司、批准库区内按条码或 AGV 编码唯一匹配，核对原生容量、托盘、重量、混放和冻结，随后同步 WCS 实际目的位置及对应未完成库存明细。

保留原计划位置与原始回报。不得模糊取第一条、自动创建库位或改已完成库存历史。部分数量、多计划共用库存行、未知／多个位置匹配、原生约束不满足时待核对；中间接力不能提前写最终位置。位置更新与完成事件在同一受控事务内执行，重复回报不重复写入或记账。

生成代码只输出受限意图，不直接写 ORM、改任意字段或验证库存单据。回滚代码不撤销已发生的物理移动及库存变动。

## 允许语法及验证

允许 JSON 常量、局部赋值、if／else、比较与有界计算、字典 .get、文本／数组切片、局部列表 .append、str／int／float／len，以及单层 for candidate in candidates。不允许任意循环、推导式、对象属性、ORM、导入、网络、文件、eval、exec 或 shell。

代码最多 32768 字符，输入／输出最多 256 KiB，集合 200 项，文本 8192 字符，嵌套 16 层，执行 30000 步；个别字段限制更小。试算采用 name／input／expected_result，3 至 20 条并覆盖全部三个阶段。每份新草稿都重新验证，人工发布；报文试算不会发设备请求。

生成前先读取本地资产、通用规则、本领域规范及至少一个匹配合同的完整案例。不能将搜索摘要或旧参考代码作为已经验证的实现。

## 回调与版本

首例 TUSK 沿用 /api/blue_wcs_tusk/feedbackTask，无附加 Token，用户已确认只在最终完成回调；类别须人工启用此兼容地址。其他类别可人工配置 Bearer，AI 不修改认证。任务号检查不是来源身份认证。

每张任务固定协议发布版本和准确输入；新发布不替换在途任务。有未结束任务时不能更换连接、类别、任务定位字段或允许范围。普通回调不能绕过协议解析，错误完成回报进入待核对。

案例见 [准确案例](examples/README.md)，使用见 [配置说明](configuration-guide.md)，厂商差异见 [旧协议参考](reference/legacy-interfaces.md)。取消、关闭、解绑、位置查询、盘点和旧模块直接改库存等，不因上传了参考就成为本合同能力。
