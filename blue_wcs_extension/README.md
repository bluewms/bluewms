# WCS 创建与 /4 增强

不绑定 AI 配置时，每条正数量就绪行按原起终点和人工设备／任务类型创建基础 goods 任务。自动创建、自动验证及验证前必须有 WCS 仍由人工控制。

`wcs_creation/4` 在 lines 阶段对全部有效行返回 create／wait／exclude、数量、组合和位置来源，固定服务复核后在 tasks 阶段编排最多四步。支持同数据 repeat、连续接力 relay 和空载具配合；后续 goods 等上一 goods end，计划货物及库存只记一次。

载具实际货物完整性、库存／预留、公司／冻结、数量覆盖和人工授权由固定服务校验；行／载具／整单确认不等于满载，最大重量不能当最小装载阈值。物理点位映射不擅自改写库存位置。

AI 与上架共用浮窗，但使用独立 **WCS生成策略** Task 和原生 WCS Wiki。读取真实资产／合同、标准搜索及全文后才可提交和验证草稿；不经过旧 Skill，不回退本地或上架案例。AI 没有发布或设备执行权限。

生产接口定义不保存示例正文，客户草稿、不可变版本及 /1–/3 历史保留，不自动转版、发布或改绑。真实设备的散件、库区和同数据多程序能力须现场确认，模拟与 HTTP 桩不代表真机验收。

- [使用及迁移边界](../docs/migrations/wcs-20.md)
- [编排设计与验收不变量](../docs/design/wcs-v4-orchestration.md)
- [当前 AI 接入与验证](../docs/migrations/native-wiki-runtime-20.md)
- [真实合同核对附件](../docs/wiki/domains/wcs/wcs-creation-v4-contract.json)
- [十组准确案例](../docs/wiki/domains/wcs/examples/README.md)
