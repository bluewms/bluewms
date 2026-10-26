# 多台开发机的 Git 同步

源码仓库为 `https://github.com/bluewms/bluewms.git`。模块、Docker 定义、工程文档和知识来源通过 Git 同步；相邻 `odoo20` 官方参考源码属于独立仓库。

## 日常开发与合并

先检查当前分支和未提交修改，再拉取；不要在另一台机器的未保存改动上强制覆盖。

```sh
git status
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c feature/本次任务名称
```

完成必要验证后只提交本次文件，推送任务分支并发起 PR。`main` 的保护规则已启用，通过 PR 及 squash 合并，不直推或强推 main。已有任务分支继续使用原分支，先确认其他机器是否也在修改它。

```sh
git diff
git add 本次修改的文件或目录
git commit -m "说明具体变化"
git push -u origin 当前分支名
```

收到合并后，在另一台机器检查本地改动、切回 main 并 `git pull --ff-only origin main`。有分歧时先比较、提交或单独备份本地工作，不以重置或删未跟踪文件代替合并。U 盘旧副本若没有本机修改，可在空目录克隆并核对后替换代码目录，原副本保留备份。

## 拉取源码之后

Python 修改需要重新加载服务；模型字段、XML 数据或迁移变化需要升级模块。先按[Docker 说明](../docker/README.md)备份数据库与 filestore，再按实际安装清单升级。

原生 Wiki／WCS /4 接入涉及以下模块，已有实例应先在隔离库验证：

本次已移除 WES 专用模块。已安装 `blue_wcs_wes` 的机器先按[退役步骤](operations/upgrades.md)在旧源码上完成核对和卸载，再切换新提交及升级；有 WES 数据的实例须先制定专门迁移方案。

```sh
docker compose -f docker/compose.yaml stop odoo
docker compose -f docker/compose.yaml -f docker/compose.test.yaml run --rm --no-deps odoo odoo -c /etc/odoo/odoo.conf -d 本机数据库名 -u blue_extension_contract,blue_config_asset,blue_stock_putaway,blue_wcs_base,blue_wcs_extension,blue_ai_client --stop-after-init --no-http --max-cron-threads=0
docker compose -f docker/compose.yaml up -d odoo
```

只选择本实例已安装或本次明确需要的模块。升级后核对人工参数、客户草稿／版本／发布、库存及在途任务；不自动恢复旧绑定或发布策略。旧 AI 代码会话从资产页重新打开，普通聊天仍使用日常任务。各机器使用自己的 `BLUEWMS_RUNTIME_DIR`、登录用户、业务 Key 与 Agent。

设备协议 /1 还需首次显式安装 `blue_wcs_protocol`，并升级已安装的 `blue_ai_client`、`blue_wcs_base` 及 `blue_wcs_extension`；仅拉源码不会创建字段或开放类别接口。完整命令、人工参数与限制见[设备接口交付](guides/equipment.md)。通用／设备 Wiki 更新后，从业务页面新开 AI 会话取得当前知识版本。

## Git 不同步什么

- 业务数据库、库存／单据、数据库中编辑及发布的策略资产。
- Docker 卷、filestore、登录信息、API Key 和私有运行配置。
- Codex／CodeBuddy 登录及安装到用户目录的 Skill 副本。
- 云端 Wiki 的实际发布、批准、Task、Agent 或 ACL 变更。

数据与附件使用配套备份，配置资产按已实现的导出／恢复流程处理。**拉取 Git 不会自动更新云端知识**；维护来源与发布流程见[知识维护](https://gitee.com/jch100322/bluewms-wiki/blob/master/docs/operations/knowledge-publication.md)，新用户云端身份见[Tencent 配置](https://gitee.com/jch100322/bluewms-wiki/blob/master/docs/operations/cloud.md)。

开发规则与计划统一维护在本仓库 `docs/planning/`。仓库外旧 `bluewms20-doc` 不由此仓库同步，也不作为新状态的第二维护来源。

## 腾讯知识配套仓库

独立知识、云端网关、发布记录和运维资料已迁移到私有 Gitee bluewms-wiki, 并列检出在 ../bluewms-wiki. 仅该项目 wiki/ 是上传正文; 运行 Odoo 不要求检出它. 做知识/合同配套开发时同时检出, 在知识项目执行链接、跨仓契约、网关及案例校验. 知识校验和构建只在配套仓库执行, Odoo 仓库不再保留旧路径包装脚本.
