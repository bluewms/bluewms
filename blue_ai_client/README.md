# 宝蓝 AI 云端连接

Odoo 20 的 MuK 扩展：使用当前用户的业务 Key／Agent，提供原生 Wiki 搜索、完整读页、五类真实 Task 路由及专用草稿工具。服务管理凭据只留在云端，模块不维护本地示例库或 Skill 正文副本。

## 使用入口

- MuK AI → 设置 → 宝蓝云端服务：配置服务、模型和当前用户连接；日常任务只表示普通聊天。
- 上架／WCS 资产页或设备类别 → AI 生成／修改：在当前表单打开浮窗，支持放大／恢复。读取真实资产和合同后，搜索并读完通用规则、本领域规范和匹配案例，再保存并验证草稿；发布由用户操作。
- MuK AI → 宝蓝业务知识：五类会话分别使用对应共享 Task。设备 /1 由 blue_wcs_protocol 提供；ERP／条码目前不开放可执行合同。

五个业务工具为 `blue_read_code_asset`、`blue_search_code_knowledge`、`blue_read_code_knowledge`、`blue_submit_code_draft`、`blue_validate_code_draft`。只读知识会话不提供资产写入工具，业务会话也不能改用其他服务商发送既有历史。

用户、公司、hook、合同、草稿摘要和正式基础版本固定到会话；真实云端身份、知识批准／版本／摘要在提交前复核。知识不足、漂移或权限变化时失败，不回退日常 Task、旧 Skill、本地示例或其他领域。

默认输出预算为 16384；不同自定义值保留。代码回复被截断时明确报错，不执行不完整工具调用。正式库存与设备业务按本地固定代码执行，不因模型断网停止。

部署步骤与完整验收见[原生 Wiki 与五类 Task 接入](../docs/guides/ai.md)。知识来源在[docs/wiki](https://gitee.com/jch100322/bluewms-wiki/blob/master/wiki/README.md)，独立云端只读通道的代码及部署见[cloud/README](https://gitee.com/jch100322/bluewms-wiki/blob/master/cloud/README.md)。旧代码会话保留历史，从资产页新开；跨机器拉取后仍需按实际变更升级数据库。
