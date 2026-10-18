# WCS基础创建与AI配置: 暂停状态及验证记录

> 历史/3草案与暂停记录保留。2026-10-18后续业务澄清已通过/4实施并部署; 当前以 docs/design/wcs-v4-validation.md 和 docs/knowledge/wcs-ai-creation-v4-zh.md 为准。

2026-10-18。状态: **本地实现草案已保留, 业务语义待继续确认, 未部署**。用户补充要求先完全理解原代码表达的业务含义, 本轮暂停后不得把技术测试通过等同于业务批准。

## 已完成的技术工作

- 本地实现无AI逐行路径、wcs_creation/3两阶段策略、人工设备/任务类型边界、可选无容器路径、AI创建配置菜单和机器可读合同。
- 保留旧模板、正式版本、计划及报文的兼容设计, 新增/3模板和迁移说明; 没有在主库执行迁移。
- 中文知识文档、JSON合同和五组精确示例已生成, 属于待语义确认的技术草案, 不能直接视为已批准云端知识。

## 测试证据

1. 基于既有隔离测试库克隆 bluewms20_wcs_basic_v3_test, 执行升级和WCS专项测试。最初40项通过; 扩大HTTP测试后更正独立端口配置, 86项通过, 后续含发送前确认/冻结检查的87项通过。
2. 独立并发脚本: 两事务同时规划, 结果plans=1/tasks=2/quantity=10, retries=[1,0]。出现的一次serialization failure是预期事务重试, 未重复创建。
3. 独立发送恢复: 第一段与第二段均completed, 库存单据done。此脚本使用模拟设备。
4. 文档校验: 5组/21用例以实际wcs_creation/3解释器全部通过; 文档代码、用例与模块XML模板一致, JSON合同与运行返回一致。环境没有jsonschema包, 未宣称第三方JSON Schema验证器检查通过。
5. 扩大联合回归曾受持久并发夹具的人工开关影响, 因而另建全新bluewms20_wcs_clean_v3_test, 从空库安装相关模块并运行库存/规则/上架/WCS/WES/AI客户端测试。最终日志: **0 failed, 0 error(s) of 212 tests** (2026-10-18 02:54:35 UTC)。涵盖主路径、剩余量/新行补齐、在途载具不影响其他行、无AI试算、人工授权、旧合同、发布固定、HTTP回调和WES。

全新库最终命令:

```sh
docker exec bluewms20-odoo /entrypoint.sh odoo -d bluewms20_wcs_clean_v3_test -i blue_wcs_extension,blue_wcs_wes,blue_ai_client,blue_stock_putaway --without-demo=all --test-enable --test-tags /blue_wcs_extension,/blue_wcs_base,/blue_wcs_wes,/blue_ai_client,/blue_stock_base,/blue_stock_rules,/blue_stock_putaway --stop-after-init --http-port=8079 --http-interface=127.0.0.1 --db-filter='^bluewms20_wcs_clean_v3_test$' --max-cron-threads=0
```

测试日志摘要已在本会话工具输出中核对。旧容器内/tmp测试原始日志随后在恢复服务容器时移除, 不宣称项目保留了其原始日志。宿主机/tmp保留并发、发送和知识校验日志。未测试真实设备联网搬运、云端模型实际加载知识全文, 未进行主库业务测试。

## 主开发环境状态

更新流程仅停止了Odoo, 还没有数据库备份、模块升级或迁移命令执行; 随即收到用户暂停指令。为使用户能继续使用旧环境, 用Git HEAD的独立只读源码快照恢复服务, 工作目录新成果没有重置或撤销。

- 主库bluewms20: blue_wcs_base/blue_wcs_extension仍20.0.1.1.0, blue_ai_client仍20.0.1.0.0; 新wcs_secondary_task_type列不存在。
- WCS计划=0, 任务=0; 原人工开关与绑定未改动。
- Odoo容器健康, http://localhost:8070/web/login 返回200。
- 当前服务通过私有compose覆盖文件 `~/.config/bluewms20/wcs-pause-runtime.yaml` 将/mnt/extra-addons指向 `~/.config/bluewms20/runtime-wcs-before-v3-20261018` 的Git HEAD快照。不是新实现部署。
- 后续获准恢复实施前, 应先确认业务语义, 再按项目部署流程备份/迁移, 最后切回正常项目源码挂载。不能只重启并直接加载尚未迁移的工作目录代码。

## 当前实现的关键假设, 等待业务澄清

- 无AI: 每条正数量、就绪移动行一张直达任务, 使用实际行起终点和人工设备/任务类型; 旧四项固定设置不生效。
- 数量: 入库以picked确认的实际数量; 非入库以有效预留为基础, AI可增加confirmed要求但不能放宽入库底线。
- 无容器: 不静默跳过; 模拟设备可用, JSON需人工确认散件能力, HIK/WES仍要求实际载具。
- 整载具多明细: 基础逐行会重复物理搬运, 当前草案明确报错, 需容器分组策略或分开实际载具。这个判断尤其需要用户继续确认原代码的业务表达。
- 已有任务: 按非取消计划逐行扣除覆盖量, 支持新行/不同载具和无载具残余量补齐; 同载具在途等待, 同单已完成载具新增未覆盖货物则报错要求核对; 不做整单有一张就全部跳过。
- 版本: 已开始单据保持首次固定正式版本/无AI路径; 旧固定单据已有任务可继续完成, 不自动用/3重解释其历史。

没有提交、推送、上传云端、发布AI策略或创建主库测试作业。后续实现和部署均暂停。
