# Docker 开发与维护

本项目在 Docker 运行 Odoo 20 与 PostgreSQL。实际镜像／架构及核查日期见[部署锁](deployment-lock.json)，当前模块能力见[开发计划](../docs/planning/bluewms20-development-plan.md)。该锁中的历史测试数字不代表本轮重新测试。

## 配置与持久数据

| 内容 | 容器位置／说明 |
|---|---|
| 仓库根目录的 addon | 挂载至 `/mnt/extra-addons`，每模块一个直接子目录 |
| 私有 `odoo.conf` | 只读挂载至 `/etc/odoo/odoo.conf` |
| `bluewms20-odoo-data` | `/var/lib/odoo`，包括 filestore 和会话 |
| `bluewms20-postgres-data` | PostgreSQL 持久数据 |

默认服务端口为 Odoo `localhost:8070`、PostgreSQL `localhost:5436`，开发库名 `bluewms20`。新机器设置 `BLUEWMS_RUNTIME_DIR` 指向自己的私有目录，准备独立密码与配置；不要复制另一台机器的登录信息或把备份提交到 Git。首次安装示例见[仓库首页](../README.md#docker-配置)。

Compose 从私有目录读取 `odoo.conf` 和 `db-password`。相邻官方 `odoo20` 参考源码不自动替代镜像内的运行代码；也不挂载旧 19 的 addons。

## 常用操作

从项目根目录执行：

```sh
docker compose -f docker/compose.yaml up -d
docker compose -f docker/compose.yaml ps
docker compose -f docker/compose.yaml logs --tail=100 odoo
docker compose -f docker/compose.yaml restart odoo
```

Python 源码变更后重启加载；字段、数据、视图或迁移变化需要相应模块升级。普通停止／重启保留数据卷，替换代码目录或移动主目录后应重建服务并核对实际挂载。

## 备份与模块升级

升级前停止 Odoo 写入，备份同一时点数据库和 filestore，实际检查归档可读及内容。保存客户草稿、正式版本／发布、人工参数与库存／在途任务基线。数据库凭据及备份只留私有目录；备份生成成功不等于完整恢复演练已完成。

```sh
docker compose -f docker/compose.yaml stop odoo
docker compose -f docker/compose.yaml -f docker/compose.test.yaml run --rm --no-deps odoo odoo -c /etc/odoo/odoo.conf -d 本机数据库名 -u 本次需要升级的模块 --stop-after-init --no-http --max-cron-threads=0
docker compose -f docker/compose.yaml up -d odoo
```

升级后核对服务健康和业务基线。原生 Wiki／WCS 接入涉及的模块和跨机器步骤见[Git 同步](../docs/git-sync.md)；不要自动发布策略、改绑旧作业或恢复已取消的设备任务。

## 隔离验证

在独立 `*_test` 数据库运行测试，复制其需要的附件，并使 `--db-filter` 与测试库完全匹配，避免 HTTP 测试选到主库。`compose.test.yaml` 只关闭一次性测试容器的健康探测，日常服务保留健康检查。

参考示例使用 `scripts/validate_ai_wiki.py`，网关检查使用 `python3 -m unittest discover -s cloud/tests`；业务模块按改动运行对应测试。不要在主库执行库存或真实设备测试夹具。当前已完成的验证与限制见[原生 Wiki 交付](../docs/migrations/native-wiki-runtime-20.md)及[WCS 设计](../docs/design/wcs-v4-orchestration.md)。

`blue_dev_environment` 仅用于开发目录标识，没有业务逻辑；正式模块存在后按需保留。第三方安装来源与原许可见[MuK 安装记录](../docs/third-party/muk-ai-install-2026-10-12.md)。
