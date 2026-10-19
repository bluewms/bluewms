# WES 专用模块退役

更新：2026-10-19。`blue_wcs_wes` 及基础模块内的 `/api/into-container/back`、`/api/out-container/back` 专用回调已移除。厂家协议维护在[设备 Wiki](../wiki/domains/equipment/reference/wes-vzf.md)，新增对接使用 `blue_wcs_protocol`。本次不增加自动取 Token 或逐明细聚合能力。

类别凭据统一显示 `App Key / Token (appId)` 和 `App Secret (appSecret)`。字段映射不等于自动完成认证；当前运行合同的限制见 Wiki 参考。实际凭据不迁入文稿或业务参数。

## 已安装实例的处理顺序

1. 在仍包含旧模块的提交上核对安装状态、依赖模块、WES 类别／设备及其全部历史任务。存在 WES 数据或其他模块依赖时先制定专门迁移方案，不能直接卸载或更改为其他适配器。
2. 停止业务写入，备份数据库和 filestore，并检查归档可读及内容；保存库存、任务、人工连接参数和代码资产基线。在独立 `*_test` 库演练卸载、升级及对应回归。
3. 确认没有 WES 类别、设备、任务和已安装的依赖模块后，通过 Odoo 模块卸载流程卸载 `blue_wcs_wes`。不要直接删除模块状态或字段元数据。
4. 再切换到移除 WES 源码的提交，升级 `blue_wcs_base` 和已安装的 `blue_wcs_extension`，重新加载服务。其他设备模块按本次实际变更与安装清单升级。
5. 核对 WES 已卸载、旧专用字段／视图已清理、旧回调路由不再提供，统一类别接口、正式资产和库存／任务基线保持一致。

旧模块源码可从 Git 提交 `f6c6d462e606e683e38f72cd8d003913891b4495` 找回。不能先删除源码再尝试卸载。

## 本机处理

主库 `bluewms20` 在卸载前有 1 个设备、2 个类别，全部使用 `protocol`；WCS 任务数为 0，没有模块依赖 WES。已在克隆的隔离库演练卸载，并通过同一 Odoo 卸载流程处理主库。数据库、filestore 及基线记录保存在私有运行配置目录的 `backups/wes-retirement-20261019/`，不提交到仓库。

隔离库验证：WCS 基础与设备协议 48 项测试、WCS 扩展 92 项测试均为 0 失败、0 错误；Wiki 15 个案例共 42 条试算通过，合同附件与内部链接一致。主库升级后核对库存明细及代码资产摘要；旧专用字段和视图已清理，两个旧回调 POST 返回 404。模拟与 HTTP 回归不等于真实 WES 现场验收。

本地 Wiki 修改需要按[知识发布流程](../architecture/ai-generation-knowledge-maintenance.md)另行发布，删除源码或升级 Odoo 不会自动更新云端知识。
