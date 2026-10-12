# BlueWMS20 本机 Docker 开发环境

- Odoo：本机 `odoo:20` 镜像。
- 数据库：`postgres:16.0`，独立容器与数据卷。
- 访问地址：<http://localhost:8070>。
- 数据库名称：`bluewms20`。
- 界面语言：简体中文，管理员时区：Asia/Shanghai。
- PostgreSQL：`localhost:5436`，业务账号 `odoo`。
- 凭据：`/Users/jianglang/.config/bluewms20/access.md`，未放入 Git。

## 目录与持久化

| 本机／Docker 卷 | 容器位置 | 用途 |
|---|---|---|
| 本项目根目录 `bluewms` | `/mnt/extra-addons` | 开发模块，每个模块直接放在根目录的子目录中 |
| 私有运行配置 `~/.config/bluewms20/odoo.conf` | `/etc/odoo/odoo.conf` | 从旧配置复制并适配 Odoo 20；只读挂载 |
| `bluewms20-odoo-data` | `/var/lib/odoo` | filestore、sessions 等数据 |
| `bluewms20-postgres-data` | `/var/lib/postgresql/data` | PostgreSQL 持久数据 |

原配置来源：`/Users/jianglang/odoo/odoo19/doc/config/odoo.conf`。

原文件保持原样。运行副本调整了数据库连接、模块路径、独立库名、演示数据和 Odoo 20 参数；不挂载旧 19 的 OLS／rent 模块。

管理主密码沿用原值，运行副本采用哈希保存。Odoo 登录密码为独立生成的密码，见上述私有凭据文件。

`deployment-lock.json` 记录安装时的镜像标识、架构、目录和已完成验证。初始化环境已建立。2026-10-12 首批 7 个 MuK Web 模块及 3 个必要依赖已安装到开发库；同日 `muk_ai`、`muk_ai_skills`、`muk_mcp` 也已安装，309 项后端／HTTP 测试及前端资源编译通过；真实模型配置与浏览器交互待验证。WMS 与客户模块仍在后续阶段安装。AI 安装详情见 [安装记录](../docs/third-party/muk-ai-install-2026-10-12.md)。来源、版本锁、实际验证和限制见 [首批迁移记录](../docs/third-party/muk-web-migration-2026-10-12.md)。

## 常用操作

在项目根目录执行：

```sh
docker compose -f docker/compose.yaml up -d
docker compose -f docker/compose.yaml ps
docker compose -f docker/compose.yaml logs --tail=100 odoo
docker compose -f docker/compose.yaml restart odoo
docker compose -f docker/compose.yaml stop
```

新模块放入项目根目录，例如 `blue_stock/__manifest__.py`。Python 修改后重启 Odoo，模块结构或数据变化时还需执行对应模块升级。

`blue_dev_environment` 是无业务逻辑的开发标识模块。Odoo 20 要求 addons 目录至少含一个有效模块，否则会忽略空目录；正式模块增加后可以按需移除此标识模块。

```sh
docker compose -f docker/compose.yaml stop odoo
docker compose -f docker/compose.yaml run --rm --no-deps odoo -c /etc/odoo/odoo.conf -d bluewms20 -u 模块名 --stop-after-init --no-http --max-cron-threads=0
docker compose -f docker/compose.yaml start odoo
```

执行模块升级前按改动需要安排维护窗口。数据库与 filestore 均需备份；普通停止／重启保留数据卷，删除数据卷会删除持久数据。

配置文件或凭据修改后，在项目根目录重新运行 `up -d` 或重启对应服务。Compose 使用本机已有镜像；镜像更新应先拉取、核对版本，再重建服务。

可以设置 `BLUEWMS_RUNTIME_DIR` 指向另一台机器上的私有配置目录。代码提交包括 Compose 与说明，不包括运行配置和密码。

## 2026-10-12 库存基础首批迁移

`blue_stock_base` 与 `blue_web_theme` 已安装到开发库；库存基础与产品主菜单分离。16 项功能测试、模块升级、界面卸载／重装和独立库页面检查通过。详细范围和边界见 [迁移记录](../docs/migrations/blue-stock-20.md)。一次性测试使用 `compose.test.yaml` 禁用该测试容器的健康探测，日常开发服务沿用原健康检查。

## 2026-10-12 库存规则

`blue_stock_rules` 已安装，默认非负库存保护及库位冻结／禁止入库生效。43 项最终联合测试及规则模块卸载／重装通过。来源、例外、精度和边界见 [库存规则交付](../docs/migrations/stock-rules-20.md)。同批次／同单上架尚未执行。

## 2026-10-12 项目目录迁移

本机项目主目录为 `/Users/jianglang/odoo`，自定义模块目录为 `/Users/jianglang/odoo/bluewms`。Compose 的相对模块挂载已随容器重建生效。运行数据卷和私有配置目录保留。详情见 [目录迁移记录](../docs/environment-path-relocation-2026-10-12.md)。
