# BlueWMS

[简体中文](README.md) | [English](README.en.md)

**基于 Odoo 20 社区版的模块化仓库管理系统，连接人工仓、PDA 作业、ERP 和自动化设备。**

基础业务模块及五类 AI 扩展入口已实现。按实际场景选择模块部署，客户 ERP、设备协议和实机 PDA 另做适配与验收；正式产品版本以 GitHub Release 为准。

## 核心能力

| 业务 | 能力 |
|---|---|
| 库存与库位 | 多公司/仓库、批次/包裹/货主、容量位置、非负库存、冻结与禁止入库 |
| 上架 | 原生规则准入后筛选/排序，同单、同批次号、整托完整性与容量约束 |
| 盘库 | 独立盘库单、账存快照、实盘确认、差异与原生记账，支持 ERP/条码桥接 |
| PDA 条码 | 四入口查询、单据/批次分组分页、数量键盘、完整 QR、追踪补扫、装箱/验证/欠单 |
| ERP | 入库、出库、内部调拨接收映射，完成/盘点差异事件、持久发送与幂等核对 |
| WCS 与设备 | 行决定与多步骤编排、repeat/relay、类别级 HTTP/JSON 协议、受控回调及库存一次记账 |

各领域独立安装，通过桥接组合。库存基础不反向依赖 AI、WCS 或条码；业务数据、人工配置和已发布策略保存在本地实例。

## AI 自助配置

从业务页面描述需求，助手读取绑定资产、真实合同和云端批准知识，生成代码与本次测试。流程为：

**描述需求 → 读取资产/知识 → 生成草稿 → 试算与验证 → 人工审核发布 → 本地执行**

| 入口 | 当前合同 | 可配置内容 |
|---|---|---|
| 上架 `putaway_policy` | `/1`、`/2` | 合规候选位置过滤和排序 |
| WCS `wcs_creation` | `/4` | create/wait/exclude、数量、组合、位置来源及任务依赖 |
| ERP `erp_mapping` | `/1` | 单据字段映射、完成/盘点报文和响应判断 |
| 设备 `device_protocol` | `/1` | request/response/callback 纯数据转换 |
| 条码 `barcode_policy` | `/1` | QR 字段解析、唯一候选选择及已授权后续动作 |

代码在合同允许的纯数据范围内运行。公司权限、库存、数量、设备授权、连接和状态机由固定模块检查。AI 保存和验证草稿，用户发布；新模型、字段或前端组件通过正式模块开发。

发布后的业务规则在本地执行，普通仓库操作无需逐次调用模型。云端负责生成时的模型与知识服务，不能放宽本地系统约束。各实例须完成相应模块安装、用户连接和知识批准后才能生成。

## 快速开始

```sh
git clone https://github.com/bluewms/bluewms.git
cd bluewms
```

准备私有配置、数据库密码和持久卷，设置 `BLUEWMS_RUNTIME_DIR`，再按 [Docker 首次配置](docker/README.md#首次配置) 启动。默认 Odoo 为 `http://localhost:8070`，PostgreSQL 为 `localhost:5436`；配置不要提交到 Git。

模块直接位于仓库一级目录，按依赖选择安装。精确版本与职责见 [模块架构](docs/module-architecture.md)，实际运行镜像见 [部署锁](docker/deployment-lock.json)。升级前备份数据库与 filestore，核对人工参数、代码资产、库存及在途任务。

## 使用与维护

- [文档入口](docs/README.md)：业务使用指南、开发、测试和运维。
- [AI 使用](docs/guides/ai.md)：五类入口、资产、Task、验证与人工发布。
- [AI 生成知识库](docs/wiki/README.md)：规范、完整合同与准确案例的唯一维护来源。
- [知识发布状态](docs/wiki-publication/README.md)：实际云端版本与读回结果；Git 合并不自动发布知识。
- [安装与升级](docs/operations/upgrades.md) · [Git 协作](docs/git-sync.md) · [验证指南](docs/testing/README.md)。

正式 Odoo 发行包排除整个 `docs/`，云端配套代码单独部署。项目历史通过 Git 查阅，不在当前使用文档中累积阶段日志。模块版本与产品 Release 分别管理。

## 贡献与许可证

通过 [Issues](https://github.com/bluewms/bluewms/issues) 提交问题，使用 PR 和 squash 合并到 main。说明用途、影响范围与验证方式；密码、Key、客户数据和备份不进入源码仓库。

仓库包含 AGPL-3 与 LGPL-3 模块，许可和归属以各模块 manifest、LICENSE 及原版权声明为准。第三方依赖保留原许可，见 [依赖说明](docs/third-party/README.md)。

由宁波宝蓝物流科技有限公司维护。[bluewms.com](https://www.bluewms.com) · [blue.lang@outlook.com](mailto:blue.lang@outlook.com)。
