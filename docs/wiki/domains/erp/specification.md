# ERP 接口 AI 生成规范

hook：`erp_mapping`。合同：`erp_mapping/1`，schema_version=1。知识状态：`verified`。更新：2026-10-20。仅用于已安装此合同且云端批准本知识版本的会话。

## 生成目标

ERP 入库、出库、内部调拨单映射到 WMS 库存单；库存单验证完成后回传本次实际完成数量；盘点按差异生成外部报文。代码只处理纯 JSON，连接、权限、建单、库存、发送队列和幂等由固定模块执行。

接口管理中人工维护公司、ERP 连接、作业类型、允许来源／目的位置、ERP 顶层明细数组字段、接收凭据与允许的外部操作代码／路径。盘点接口选择准确内部库位，不自动包含子库位，同库位仅启用一个接口。每条接口独立维护代码资产及正式版本，共用既有 ERP接口 Task。

## 输入与语法

准确字段以本地 `blue_read_code_asset` 返回的合同为准，完整附件见 [JSON 合同](erp-mapping-v1-contract.json)。输入只有 request、candidates。

request 固定字段：phase、kind、event_key、external_id、number、message、http_status、operation。phase 为 receive／complete／inventory／response；kind 为 incoming／outgoing／internal／inventory。接收时 message 为 ERP 报文，配置的一个顶层明细数组作为 candidates；完成／盘点时 candidates 为固定服务快照；响应时 message 为 ERP JSON。

沿用受限 JSON 解释器：变量赋值、if/else、单层 `for candidate in candidates`、字典 get、局部数组 append、str／int／float／len、切片及有限运算。不能导入、调用 ORM、读密钥、访问网络或任意执行 Python。代码不超过 32768 字符，输入不超过 256 KiB，每数组最多 200 项。

## 输出

- receive：仅输出 documents，1—20 个单据。每个单据包含 external_id、number、partner_code、lines。每行准确字段为 external_line_id、product_code、quantity、uom、lot、source_code、destination_code、group。数量为正；单据 ID 和行 ID 为稳定文本。同单内行 ID 唯一。group 用于拆分本地库存单。
- complete／inventory：仅输出 actions，1—10 个有序操作，每项为 operation、body，以及可选 headers。operation 必须来自人工批准列表，不能输出 URL、模型名或数据库写入指令。
- response：仅输出 state 和 external_number；state 为 accepted／rejected／unknown。固定服务将非 2xx、超时、无效 JSON 或解释失败视为待核对。

接收使用已有唯一商品 default_code，uom 必须等于商品库存单位的原始名称（lang=None，不随界面语言变化）。往来单位按 ref 唯一匹配；显式批次必须已存在。source_code／destination_code 使用允许位置范围内的唯一条码，留空使用人工配置位置。未知或重复编码应修正主数据，不猜测或自动创建。

## 完成与盘点语义

完成快照行包括 external_line_id、product_code、quantity、cumulative_quantity、acknowledged_quantity、planned_quantity、uom、lot、source_code、destination_code、package。quantity 是本次完成数量；累计量及已反馈量是产生事件当时的快照。每次部分完成使用不同稳定 event_key，相同事件重试保持原键。累计不超过原计划。

盘点快照行包括 product_code、uom、lot、location_code、package、owner_code、book_quantity、counted_quantity、difference_quantity。差异正数为盘盈，负数为盘亏。保存调整前快照，不能在发送时重新读取当前库存覆盖历史数量。零差异不产生事件。

多个 actions 按顺序发送，已成功的操作不重发。Idempotency-Key 由固定服务维护，代码不得覆盖；发送前持久化 sending，未知结果必须核对后处理。WMS 完成和 ERP 同步状态分别管理。

headers 可使用 `$app_key`／`$app_secret` 占位符，本地发送时替换；凭据不得写进代码、报文试算或 Wiki。只支持单次 JSON POST，不能自行获取动态 Token，不能从前一步响应给后一步注入参数。需要额外能力时先实现正式执行服务。

## 试算与发布

提供 3—20 个 name／input／expected_result 准确案例。入出库／调拨覆盖 receive、complete、response；盘点覆盖 inventory、response。试算不建业务单、不联网；固定服务回归与真实 ERP 联调分别验证。保存和验证不等于发布，人工发布后新单据使用新版，原单及欠单保持固定版本。

示例见 [ERP 示例目录](examples/README.md)。当前已验证通用 JSON 合同和模拟服务，不代表 E10、金蝶等客户现场协议已验收。其他 ERP 协议先取得准确文档和脱敏报文，再按本地合同适配。

## 生成前的需求澄清

先完整读取[五类入口需求澄清规则](../../basics/requirements-clarification.md), 再结合绑定资产检查: 准确厂商文档与脱敏报文、阶段和编码体系、稳定单/行/事件标识、数量/单位与本次/累计语义、拆单和成功/拒绝/未知响应. 未知主数据、动态认证或协议能力缺失不是可凭策略猜测完成的配置. 已明确或当前合同可读取的内容无需重问; 相关关键选择未明确时 ask_user 并等待回答, 不先写代码/提交草稿. 固定执行器不支持的行为应说明能力缺口, 不能仅凭纯 JSON 输出声称已实现.
