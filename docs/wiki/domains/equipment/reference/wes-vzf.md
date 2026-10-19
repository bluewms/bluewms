# WES VZF HTTP 接口参考

知识状态：planned。用途：厂家协议沟通和接口生成前的能力核对，不是已验证的 device_protocol/1 可执行案例。

来源：BlueWMS20 提交 f6c6d462e606e683e38f72cd8d003913891b4495 中的原 blue_wcs_wes 模块；协议映射参考 bluewms19 ZF 622afc8。Copyright 2026 宁波宝蓝物流科技有限公司，AGPL-3.0-or-later。本文不含真实地址或凭据。

## 连接和凭据

WES 是仓库执行系统，BlueWMS 通过 HTTP(S) 对接，再由 WES 调度实际设备。厂家协议使用通用设备类别连接参数，不需要单独的 WES 配置字段。

| 通用字段 | 厂家字段／用途 |
|---|---|
| IP 地址与任务接口路径 | 人工配置批准的服务地址及入库／出库路径 |
| App Key / Token | appId，或接口明确支持时填写已取得的 Token |
| App Secret | appSecret |
| 回调凭据 | 接收完成回调时校验的 Bearer 凭据 |

appId 不是 access_token。旧协议先 POST `/api-auth/oauth/token`，表单提交 appId、appSecret，并携带厂商指定的 Authorization 请求头；响应 access_token 用于下发请求的 Blade-Auth 请求头。随后以 JSON POST 任务。所有认证值只放本地专用凭据字段，不能写进 Wiki、业务参数、生成代码或试算。

当前 device_protocol/1 仅处理单次 JSON 任务请求、响应及单条最终完成回调，不执行上述两阶段表单取 Token。仅填写 appId／appSecret 不能完成自动取 Token；对接时先核对厂家是否提供兼容接口，否则先补通用认证能力。不得生成自行联网获取 Token 的策略代码。

## 下发报文

入库路径参考 `/into-order-hd/manual-order-vzf`，出库路径参考 `/out-order/manual-order-vzf`。JSON 响应 code=200 表示接受，不代表设备完成。发送后超时或结果不明确应待核对，禁止盲目重发。

共同字段：whCode（仓库）、whRoomCode（库房）、ownerCode（货主）、carBillCode（完整稳定 WCS 任务号）。这些业务编码需依据实际接口及当前合同配置，不由 AI 发明。

入库：planOrderType、planItemVOList。每项包含 carBillCode、SAPOrderNo（完整任务号）、SAPOrderItemNo（准确计划明细编号）、batchAttr04（批次）、materialCode、materialQuantity，以及 intoOrderInParamsVzf 中的 traceCode（包裹／载具）、matQty、wholePallet。

出库：outOrderType、outOrderItemList。每项包含共同任务／明细标识、batchAttr04、matCode、outQty、stgTypCode，以及 outPalletAllocationList 中的 traceCode 和 outQty。

旧适配按商品／批次／包裹逐项发送，数量换算到产品库存单位；现场 WES 物料单位必须一致。旧协议需要载具，不据此推断支持散件、任意库区或同货物重复出入库。

## 完成反馈

旧入库回调路径 `/api/into-container/back`，旧出库回调路径 `/api/out-container/back`。任务由 carBillCode 或 SAPOrderCode 定位；SAPOrderItem 标识计划明细；binCode 表示实际位置。出库仅 END_PICK 表示最终完成。

原适配验证 Bearer 凭据，按明细幂等累计，全部计划明细完成后才结束任务；实际位置与批准目的点不一致时停止自动完成。旧专用模块及其回调路由已退役，新增对接使用统一类别回调地址。

当前单条最终完成合同不能直接接收并累计逐明细反馈。须由上游提供整任务最终完成，或先补通用明细聚合能力并回归；不能把第一条明细反馈当成整任务完成。真实厂家报文和现场验收仍需单独完成。
