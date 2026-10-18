# Mita 旧协议参考

来源：bluewms19 7d77ae7，blue_wcs_mita。状态：协议参考，尚非已验证设备合同案例。

旧报文有 taskNo、containerCode、stationCode、zoneCode、priority、details、重量和容器结构。入出库路径、字段和动作须按实际设备版本确认，不能从名称推断。

旧 `/api/blue_wcs_mita/feedbackTask` 无 Token 校验，details 数组逐条有 taskNo、containerCode、taskStatus、stackCode，只有 taskStatus=FINISHED 才完成。应答为顶层 code=0、msg=success 及逐条 details 结果。另一个 `/api/blue_wcs_mita/packageLocation` 是包裹位置回报，不能把位置通知当任务完成。

当前 device_protocol/1 接收单条任务回调，资料存在不等于已支持批量消息。旧创建 WCS、出库业务、关闭、解绑和条码触发分别属于其他流程，不能复制到协议代码；先补准确输入、批量关联／应答和回归，再宣布完整兼容。

固定业务编码可用人工非秘密 parameters，身份凭据由专用字段注入。位置输出仍遵循 [设备规范](../specification.md)。
