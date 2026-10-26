# Docker 开发与维护

本项目在 Docker 运行 Odoo 20 与 PostgreSQL。实际镜像／架构及核查日期见[部署锁](deployment-lock.json)，当前模块能力见[开发计划](../docs/planning/bluewms20-development-plan.md)。该锁中的历史测试数字不代表本轮重新测试。

## 配置与持久数据

| 内容 | 容器位置／说明 |
|---|---|
| 仓库根目录的 addon | 挂载至 `/mnt/extra-addons`，每模块一个直接子目录 |
| 私有 `odoo.conf` | 只读挂载至 `/etc/odoo/odoo.conf` |
| `bluewms20-odoo-data` | `/var/lib/odoo`，包括 filestore 和会话 |
| `bluewms20-postgres-data` | PostgreSQL 持久数据 |

默认服务端口为 Odoo `localhost:8070`、PostgreSQL `localhost:5436`，开发库名 `bluewms20`。新机器设置 `BLUEWMS_RUNTIME_DIR` 指向自己的私有目录，准备独立密码与配置；不要复制另一台机器的登录信息或把备份提交到 Git。首次安装示例见[首次配置](#首次配置)。

Compose 从私有目录读取 `odoo.conf` 和 `db-password`。相邻官方 `odoo20` 参考源码不自动替代镜像内的运行代码；也不挂载旧 19 的 addons。

## 首次配置

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

参考示例使用 `scripts/validate_ai_wiki.py`，网关检查使用 `python3 -m unittest discover -s docs/cloud/tests`；业务模块按改动运行对应测试。不要在主库执行库存或真实设备测试夹具。当前已完成的验证与限制见[原生 Wiki 交付](../docs/guides/ai.md)及[WCS 设计](../docs/guides/wcs.md)。

完整 Wiki 校验现含设备 /1，测试库须安装 `blue_stock_putaway`、`blue_wcs_extension` 和 `blue_wcs_protocol`。设备接口首次安装、人工参数、位置回写及测试范围见[设备交付](../docs/guides/equipment.md)。

第三方安装来源与原许可见[MuK 安装记录](../docs/third-party/README.md)。
