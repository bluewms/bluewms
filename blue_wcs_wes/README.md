# WES VZF 适配

设备适配选择 WES VZF，配置完整任务 URL、同主机 Token URL、Authorization、App ID/Secret，以及仓库/库房/货主/单据类型；出库还需存储类型。所有凭据仅系统管理员可访问，默认留空。

协议路径参考 ZF：`/api-auth/oauth/token`、`/into-order-hd/manual-order-vzf`、`/out-order/manual-order-vzf`。每次下发先取 token，再带 Authorization/Blade-Auth 发送。认证失败为未发送失败；命令发送后的超时或非确定响应为待核对，禁止盲目重试。

WES 物料数量按 Odoo 产品库存单位换算，现场 WES 物料单位必须与此合同一致；一张任务按商品/批次/包裹分别发送明细。SAPOrderNo 使用完整稳定任务号，SAPOrderItemNo 使用计划明细编号，不复用旧库存数字 ID。

入/出库回调路径 `/api/into-container/back`、`/api/out-container/back` 均要求设备的 Bearer 回调凭据。提供 carBillCode 或 SAPOrderCode（准确任务号），SAPOrderItem（准确计划明细编号）。出库完成需 END_PICK。多商品任务等待所有计划明细完成才完成任务/释放后段；重复明细回执幂等。

实际 binCode 与批准目的点不一致会停止自动完成，需现场核对。尚未迁入动态实际库位自动改写、物料/盘点同步及客户 MES/E10；这些属于后续独立场景。没有真实设备联调，本轮验证使用模拟设备及模拟 HTTP 响应。
