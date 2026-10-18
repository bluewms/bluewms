# M4 旧协议参考

来源：bluewms19 7d77ae7，blue_wcs_m4。状态：协议参考，尚非已验证设备合同案例。

旧 HTTP POST 使用 entityName／entityValue 包装。任务有 id、kind、fromBin、toBin、fromBinList、toBinList、container 等字段；认证头名称 xyy-app-id、xyy-app-key，实际值由人工专用凭据注入，不写入 AI 代码。

旧 `/api/blue_wcs_m4/feedbackTask` 不校验 Token。报文虽有 id，旧逻辑主要用 container 匹配进行中任务，status=unloaded 时完成，bin 为细点。内部调拨曾截去 bin 末两字符匹配库位并直接改库存行；只有实际编码约定成立才可参考此截取，不能作为通用规则。

新代码须准确关联任务，输出子位置或 destination_code，由固定服务唯一匹配、校验并同步；不复制 sudo 搜索或直接改库存。缺少 kind、位置列表等真实输入时先补合同输入，不能发明 ORM 字段。关闭／更新动作不属于首期合同。

规范见 [设备合同](../specification.md)，代码结构可参考 [准确案例](../examples/README.md)，再用真实 M4 报文补试算和现场验收。
