# Modula 旧协议参考

来源：bluewms19 7d77ae7，blue_wcs_modula。状态：协议参考，尚非已验证设备合同案例。

旧 HTTP 下发使用 IMP_ESEGUI_ORDINI_RIGHE 包装，包含 ORD_ORDINE、ORD_TIPOOP、ORD_DES、ORD_PRIOHOST 及订单行 RIG_ORDINE、RIG_ARTICOLO、RIG_QTAR、RIG_UMI、RIG_UDC、RIG_POSX、RIG_POSY、RIG_HOSTINF。数量单位、XY 坐标和行身份必须有准确来源，不能从其他厂家字段套用。

旧 `/api/blue_wcs_modula/in_out_storage_result` 无 Token 校验，从 DATA.EXP_ORDINI_RIGHE_STO 数组的 STO_HOSTINF 定位任务。多行聚合、实际数量及 TransactionStatus 语义要按实际厂商版本确认，旧函数直接完成任务不等于该语义已证实。

当前单条最终完成合同不等于 Modula 完整数组协议。须先补行关联、聚合及准确回归，再适配当前合同或新增受控版本。旧模型字段、库存及物料业务不由生成代码创建。

规范见 [设备合同](../specification.md)，结构见 [准确案例](../examples/README.md)。
