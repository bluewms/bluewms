# 开发校验与集成测试工具

这些脚本不由 Odoo 启动加载, 不是运行依赖, Git archive 发行包已排除 docs/ 和 scripts/. 开发、升级验证时按需要使用; 不要整目录执行.

| 脚本 | 用途 | 执行环境 |
|---|---|---|
| [check_docs.py](check_docs.py) | 检查当前文档链接 | `python3 scripts/check_docs.py`, 不连接数据库 |
| [test_barcode_capture.mjs](test_barcode_capture.mjs) | PDA/扫码枪键盘采集单元测试 | `node --test scripts/test_barcode_capture.mjs`, 不连接数据库 |
| [test_putaway_concurrency.py](test_putaway_concurrency.py) | 两个事务争用最后一个整托容量位置 | Odoo shell, 仅 `bluewms20_stock_test` |
| [test_wcs_v4_concurrency.py](test_wcs_v4_concurrency.py) | WCS /4 并发建单、幂等与同货 repeat | Odoo shell, 仅一次性 `*_test` 库 |
| [test_wcs_v4_dispatch.py](test_wcs_v4_dispatch.py) | /4 顺序发送、完成事件与库存一次记账 | 同一隔离库, 先执行上一个脚本; 使用模拟设备 |
| [validate_barcode_concurrency.py](validate_barcode_concurrency.py) | 同一扫码事件并发重试不重计数 | Odoo shell 执行文件后调用 `run(env)`, 仅 `*_test` |
| [validate_inventory_concurrency.py](validate_inventory_concurrency.py) | 盘库范围竞争和一次库存调整 | Odoo shell, 仅 `*_test` |
| [validate_erp_dispatch.py](validate_erp_dispatch.py) | ERP 持久发送、崩溃恢复和接收幂等 | Odoo shell, 仅 `*_test`, 模拟 ERP 请求 |

数据库脚本会创建并可能保留测试单据、库存及测试用户, 有的会完成模拟作业. 必须使用隔离测试库和匹配的 dbfilter; 详细启动方式见[Docker 指南](../docker/README.md). 它们不能作为生产业务操作工具, 通过一次也不代表现场设备已验收.

普通模块回归在各 addon 的 `tests/` 中. 独立事务/并发和模拟发送需要额外进程/提交边界, 因此保留这些脚本, 不用旧测试快照替代可重新执行的检查.

知识上传包构建、Wiki 案例/跨仓校验和网关测试统一在[私有配套项目](https://gitee.com/jch100322/bluewms-wiki)的 `scripts/` 与 `cloud/tests/` 中执行. 旧包装入口和已被 /4 覆盖的 WCS /3 脚本已移除, 历史内容可从 Git 查阅.
