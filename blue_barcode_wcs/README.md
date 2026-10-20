# BlueWMS 条码 WCS 桥接

作业已启用 WCS 时注册条码“申请执行 WCS”动作. 先保存当前扫码事件,再调用 stock.picking.action_create_wcs_request_from_button 正式入口,不接受前端任意 move line ID 列表.

设备授权、AI /4 编排、货物覆盖、持久发送、回调和库存记账由现有 WCS 模块负责. WCS 请求失败不会重新增加先前已保存的扫码数量. 请求、设备完成和库存验证是不同状态.
