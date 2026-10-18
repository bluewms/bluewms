# BlueWMS

[简体中文](README.md) | [English](README.en.md)

**基于 Odoo 20 社区版，支持 AI 自主定制的模块化仓库管理系统。**

BlueWMS 由原有成熟仓储项目迁移、升级而来，承接其仓库业务流程、库存管理和自动化设备集成经验，结合 Odoo 平台与云端 AI 能力，面向人工仓、自动化仓及混合作业场景。

本说明介绍迁移完成后的 WMS 产品形态与能力范围。迁移完成后的首个正式版本计划使用 **`V2.0.0`** 标签。

## 仓库业务一体化

BlueWMS 将仓库业务、条码作业、库存策略和设备执行连接为完整流程。

| 业务领域 | 产品能力 |
|---|---|
| 入库与上架 | 收货、批次与包裹管理、入库确认、库位推荐及上架执行 |
| 出库与移库 | 库存预留、拣货、出库、内部调拨与整托搬运 |
| 库存与盘点 | 多仓库与多公司管理、库存查询、盘点调整及批次追溯 |
| 库位与载具 | 库区与库位、容量管理、托盘与嵌套包裹、空载具管理 |
| 条码与手持终端 | 通过条码与 PDA 完成收货、上架、拣货、移库和盘点 |
| 库存策略 | 上架筛选与排序、同单集中、同批次集中、整托不拆分与混放约束 |
| 库存控制 | 非负库存、库位冻结、禁止入库、容量约束及按权限配置的例外 |
| WCS 与自动化 | 设备任务生成、队列下发、执行回执、任务依赖、双段接力与异常核对 |
| ERP 与外部系统 | 主数据与业务单据映射、接口交换、状态反馈及项目集成 |

人工操作与设备任务共用库存规则和业务记录，使数量、批次、位置及执行状态能够关联追踪。系统按场景选择模块，支持从人工仓扩展到设备协同作业。

## AI 自主定制

BlueWMS 支持用户通过自然语言提出需求，由 AI 结合云端知识、批准示例和项目上下文，自主生成、修改并验证业务增强代码。用户可以在业务页面完成定制，无需为每次规则调整重新维护一套客户分支。

定制覆盖五类业务入口：

- **上架策略**：调整候选库位、排序、同单或同批次集中规则。
- **ERP 接口**：调整业务字段映射、数据转换与单据处理规则。
- **WCS 生成策略**：在人工授权范围内调整行决定、数量／组合、物理位置与任务依赖。
- **设备连接接口**：在已提供的设备适配能力内调整协议映射与业务处理。
- **条码扫描策略**：调整扫描顺序、校验要求与业务步骤。

例如，用户可以提出“同一入库单优先集中存放，整托不拆分”，或“第一段搬运完成后再启动第二台设备”。AI 读取对应入口的接口规范和已有配置，生成针对该场景的代码，并根据验证结果修正草稿。

定制流程为：**描述需求 → 读取知识与现有配置 → AI 生成或修改草稿 → 试算与验证 → 用户审阅发布 → 本地业务执行**。

当前开发版已完成上架与 WCS /4 的 AI 草稿闭环：通过原生 Wiki 搜索并读取批准规范和案例，结合本地真实合同生成、保存并验证草稿，再由用户发布。五类入口分别绑定对应云端 Task，普通聊天使用日常任务。“AI 生成／修改”在原业务页面打开可放大／恢复的浮窗。ERP、设备和条码目前支持各自知识沟通，可执行合同仍待实现。

代码和配置作为数据库资产管理，支持版本记录、差异审阅、执行追踪及回滚。单点调整保留其他入口的配置；跨入口定制检查关联关系。AI 生成代码受已开放的接口、用户权限与系统库存规则约束，新增模型、字段或前端组件通过正式模块交付。

## 云端知识，本地运行

- **云端提供定制能力**：模型、知识、Skill 与项目记忆为 AI 生成代码提供上下文；用户通过自己的 API Key 和 Agent 连接服务。
- **本地管理正式资产**：客户实例保存业务数据、正式代码版本、配置和执行记录；草稿通过验证并经用户发布后生效。
- **仓库运行独立于生成服务**：已发布规则在本地执行，常规库存作业不需要逐次请求模型；云端连接用于 AI 定制与知识服务。
- **按业务边界扩展**：库存基础、条码、WCS、ERP、AI 与产品界面通过独立模块组合，第三方组件保留原有归属。

## 部署与使用

BlueWMS 以 Odoo addon 模块交付，使用 Odoo 20 社区版与 PostgreSQL，支持 Docker 部署。模块位于仓库根目录的一级子目录，由 Odoo 按依赖安装。

```sh
git clone https://github.com/bluewms/bluewms.git
cd bluewms
```

启动前准备独立的 `odoo.conf`、数据库密码和持久化存储，并设置 `BLUEWMS_RUNTIME_DIR` 指向私有配置目录。部署步骤见下文；镜像版本、维护命令及备份恢复见 [Docker 部署说明](docker/README.md) 和 [部署版本清单](docker/deployment-lock.json)。

基础仓库业务按所选业务模块运行；启用 AI 自主定制时，另行配置云端服务、用户 API Key 与 Agent。业务配置和数据库资产使用对应的备份与恢复流程，Git 用于管理模块源码和文档。

### Docker 配置

```sh
export BLUEWMS_RUNTIME_DIR="$HOME/.config/bluewms20"
mkdir -p "$BLUEWMS_RUNTIME_DIR"
chmod 700 "$BLUEWMS_RUNTIME_DIR"
```

在该目录创建 `db-password` 文件，写入一行独立的数据库强密码；创建 `odoo.conf`，将下面的数据库管理密码替换为自己的独立强密码：

```ini
[options]
admin_passwd = REPLACE_WITH_YOUR_OWN_STRONG_DATABASE_MANAGEMENT_PASSWORD
db_host = db
db_port = 5432
db_user = odoo
db_name = bluewms20
dbfilter = ^bluewms20$
list_db = True
addons_path = /usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons
data_dir = /var/lib/odoo
```

容器入口从 secret 读取数据库密码。限制配置文件权限，按部署版本清单准备本地 `odoo:20` 和 `postgres:16.0` 镜像后启动：

```sh
chmod 600 "$BLUEWMS_RUNTIME_DIR/odoo.conf" "$BLUEWMS_RUNTIME_DIR/db-password"
docker compose -f docker/compose.yaml up -d
docker compose -f docker/compose.yaml ps
```

访问 [本机 Odoo](http://localhost:8070/web/database/manager)，首次部署创建 `bluewms20` 数据库及自己的登录账号，再按需要安装业务模块。已有实例应恢复配套数据库与 filestore，升级前备份。

## 版本发布

本项目从原成熟项目迁移升级，迁移完成后以 **`V2.0.0`** 作为新产品线的首个正式发布标签。

后续产品标签沿用 `V主版本.次版本.修订版本` 格式，例如 `V2.1.0`、`V2.0.1`，分别表达产品能力演进和兼容修正。产品发布标签与 Odoo addon 的 `20.0.x.x.x` 模块版本分别管理。

正式发布通过 [GitHub Releases](https://github.com/bluewms/bluewms/releases) 提供版本说明、安装与升级指引及适用的部署要求。

正式 Odoo 发行包不包含 `docs/`；文档、知识维护来源及 `docs/cloud/` 云端配套服务仍保留在开发 Git 仓库。根目录 `.gitattributes` 已为 `git archive` 设置排除规则；其他打包方式也须排除该目录，并保留各模块的许可证与来源声明。

## 文档与贡献

- [文档目录](docs/README.md)：业务说明、架构与工程文档入口。
- [Odoo AI 代码生成知识库](docs/wiki/README.md)：面向 Odoo 内 AI 助手的生成规则、五类接口规范和示例。
- [上架增强说明](docs/migrations/putaway-policy-20.md)：原生规则、托盘、增强策略与聊天浮窗。
- [原生 Wiki 与五类 Task](docs/migrations/native-wiki-runtime-20.md)：当前生成流程、入口与真实验收。
- [Git 协作说明](docs/git-sync.md)：源码同步与分支协作。
- [问题与建议](https://github.com/bluewms/bluewms/issues)：提交复现步骤、预期行为及脱敏日志。
- [Pull Requests](https://github.com/bluewms/bluewms/pulls)：贡献代码、接口适配、示例与文档。

修改通过任务分支发起 PR，并通过 squash 合并进入 `main`。提交改动时说明用途、影响范围和验证方式，保留第三方来源与版权信息。真实密码、API Key、客户业务数据、数据库备份及私有附件不纳入源码仓库。

## 许可证与来源

本仓库包含 **AGPL-3 与 LGPL-3 模块**，具体许可和归属以各模块的 `__manifest__.py`、`LICENSE`、`NOTICE.md` 及版权头为准。迁移与改名不改变原有代码的许可和贡献者归属。

库存规则的相关来源见 [归属说明](blue_stock_rules/NOTICE.md)；MuK 组件的来源见 [上游说明](docs/third-party/MuK-upstream-README.md) 和 [许可证文本](docs/third-party/MuK-LICENSE)。Odoo 及其他依赖遵循各自许可证。

## 维护与联系

由 **宁波宝蓝物流科技有限公司**维护。

项目交流请使用 GitHub Issues／Pull Requests。业务联系：[bluewms.com](https://www.bluewms.com) · [blue.lang@outlook.com](mailto:blue.lang@outlook.com)。
