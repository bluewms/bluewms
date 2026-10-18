# WCS /4 跨电脑开发交接

更新：2026-10-18。本轮交付包含WCS /4业务实现、AI草稿入口与示例退役。云端知识没有写入；公开仓库里的Wiki/Skill文件都是候选材料。此前各部署记录的“未提交、未推送”描述对应当时阶段，GitHub最终状态以本次PR为准。

## 已实现及验证

无AI时，每条有效就绪移动行按本行库存起终点生成直达任务。WCS /4在全部有效行上决定create/wait/exclude、数量依据、容器组合和行／单据物理点位映射，再编排最多四张设备任务。同计划repeat程序可使用相同货物、设备和起终点，每张有独立身份，后张等待前张end，计划数量与库存只记一次。

人工设备、任务类型、自动创建／自动验证开关保持人工控制。库存／预留、公司、冻结、整载具完整性、覆盖量与幂等检查仍由本地服务执行。旧 /1-/3解释器、客户草稿、正式版本、固定计划与报文保留，不自动升级合同、发布或改绑。

WCS与上架使用相同浮窗；实际浏览器已验证打开、放大、恢复、关闭重开且保留配置页面。最终联合回归260项，0失败、0错误；Wiki中10组代码、25个用例与实际 /4解释器一致；独立双事务并发只生成1计划、2任务、数量10，持久调度后库存只增加10。真实设备联网搬运及Memory Hub自动Wiki检索不在已通过验收范围。

本机部署升级前后完整业务指纹一致：45条库存、5代码版本、3发布、零计划／任务，客户草稿、人工设置与绑定保持不变。服务健康、登录页HTTP 200。这些是该验证环境的证据，不代表另一台电脑已经升级。数据库、附件、运行日志、截图、私有配置和读取云端正文的快照不进入公开Git。

| 模块 | 已部署版本 |
|---|---|
| blue_wcs_extension | 20.0.1.4.0 |
| blue_wcs_base | 20.0.1.3.0 |
| blue_ai_client | 20.0.1.3.0 |
| blue_extension_contract | 20.0.1.4.1 |
| blue_config_asset | 20.0.1.1.0 |
| blue_stock_putaway | 20.0.1.4.0 |

## 当前知识读取链路与下一步

**当前上架和WCS仍强制使用Skill bridge，尚未替换为Memory Hub原生Wiki检索。**

`blue_read_code_asset`在`blue_ai_client/mcp/code_asset.py`调用`providers/knowledge.py`：按固定名称bluewms-policy-authoring搜索，取得当前身份可见、active且approved的版本／manifest，然后读取Skill文件正文。上架固定读取01/03/04，WCS固定读取01/06/07。WCS额外检查合同批准标记和真实Wiki来源ID／版本，引用固定到本地草稿与版本，旧本地引用会话必须重新打开。它不是直接Wiki搜索，也没有自动同步Wiki正文。

用户下一步拟由另一台电脑改用Memory Hub原生Wiki检索，消除额外Skill副本链路。本次仅交付现状，不预先改掉这一层。平台具备独立Knowledge/Wiki能力，但尚未验证部署中的Odoo会话是否实际自动检索并注入了正确项目、权限、版本及正文；不能声称“只上传Wiki即自动生效”。后续修改应同步调整读取工具、会话提示／引用记录及相应测试，并保留资产绑定、草稿冲突、合同／公司权限与人工发布保护。

现有云端只读验收仅证明上架批准Skill v4可读；WCS尚无批准正文时明确报错，不改草稿、不回退本地或上架示例。已有正式策略与无AI基础路径仍在本地离线运行。云端没有知识创建、更新、移动、删除、批准或发布操作。

## 另一台电脑拉取与升级

先检查该电脑的未提交修改并按正常Git流程保存，再拉取：

```sh
git status --short
git switch main
git pull --ff-only origin main
```

若使用已有数据库，先停止Odoo写入，备份数据库和filestore，并保存客户策略、人工参数、在途任务／计划和库存基线。使用该电脑自己的私有配置与Compose环境文件；配置、密码、数据库和filestore不随Git拉取。环境准备见[Docker说明](../../docker/README.md)。

模块字段、数据和迁移有变化时执行升级，不能只拉代码后重启。以下占位符替换为本机值，不复制另一台电脑的私有路径或账号：

```sh
docker compose --env-file <COMPOSE_ENV_FILE> -f docker/compose.yaml stop odoo
docker compose --env-file <COMPOSE_ENV_FILE> -f docker/compose.yaml -f docker/compose.test.yaml run --rm --no-deps odoo odoo -d <DATABASE> -u blue_extension_contract,blue_config_asset,blue_stock_putaway,blue_wcs_base,blue_wcs_extension,blue_wcs_wes,blue_ai_client --stop-after-init --no-http --max-cron-threads=0
docker compose --env-file <COMPOSE_ENV_FILE> -f docker/compose.yaml up -d odoo
```

升级后比对库存、客户草稿／版本／发布、人工开关和任务指纹，确认服务健康。迁移归档18个出厂WCS定义，只清除摘要匹配的出厂代码／测试／需求；管理员改写内容保留。生产只安装无示例正文的基础运行定义，回归夹具在`blue_wcs_extension/tests/data/`。不要自动恢复旧绑定、发布AI策略或创建主库测试搬运任务。

另开隔离测试库运行各模块测试。联合回归与持久并发夹具使用不同隔离库，防止夹具的WCS必须完成开关干扰普通库存测试。独立脚本为`scripts/test_wcs_v4_concurrency.py`、`scripts/test_wcs_v4_dispatch.py`和`scripts/validate_wcs_wiki_package.py`，只允许`*_test`数据库。

## 人工参数、设备边界与Wiki候选包

现场必须人工填写WCS方向、设备类别、主设备、任务类型；附加设备／类型和交接点也是显式授权。自动创建／验证保持人工选择。不从自由文字猜设备、站点、满载标准或库存落点。

simulation支持散件；JSON散件、库区、真实设备同数据多程序须人工确认能力。HIK／WES仍需载具，WES物理位置只支持既定库存端点。满载阈值与行／载具／整单picked分开；任意新细点回报、空载具库存池自动搜索等能力未实现。真实现场须另做协议和设备验收。

维护来源为`docs/wiki/`。`docs/wiki-publication/wcs-v4/`是现有Skill bridge方案的离线候选发布材料，**未上云**；若后续改用原生Wiki检索，应先更新这份方案说明，不能同时保留两套相互矛盾的发布指引。实际云端03/04快照不随公开包分发，服务端原上架及02/05等既有资源保持原样。当前metadata与upload-receipt中的真实Wiki ID、版本、URL仍为null，不能填猜测值或把候选approved标记当作已批准。

旧`docs/knowledge/`综合文稿只留作历史审计，不再作为生产知识源。详细业务设计见[WCS /4编排](../design/wcs-v4-orchestration.md)，本机阶段验证见[本地交付记录](wcs-cloud-local-20.md)。
