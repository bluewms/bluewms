# 项目目录迁移：2026-10-12

项目主目录已从 OneDrive 下迁移至 `/Users/jianglang/odoo`。

| 项目／服务 | 本机新目录 | Docker 目录／访问入口 |
|---|---|---|
| BlueWMS20 项目 | `/Users/jianglang/odoo` | Codex 项目主目录 |
| Odoo 20 自定义模块 | `/Users/jianglang/odoo/bluewms` | `/mnt/extra-addons`，http://localhost:8070 |
| Odoo 19 配置 | `/Users/jianglang/odoo/odoo19/doc/config` | `/etc/odoo` |
| Odoo 19 自定义模块 | `/Users/jianglang/odoo/odoo19/addons/bluewms19` | `/mnt/extra-addons` |
| Odoo 19 OLS 模块 | `/Users/jianglang/odoo/odoo19/addons/OLS` | `/mnt/ols-addons` |
| Odoo 19 rent 模块 | `/Users/jianglang/odoo/odoo19/addons/rent` | `/mnt/rent-addons` |

Odoo 20 的 Compose 使用相对源码路径 `../`；从新目录重建 Odoo 服务后，挂载解析至新的 `bluewms` 目录，不需要把仓库绑定到本机绝对路径。

日常在 `/Users/jianglang/odoo/bluewms` 执行：

```sh
docker compose -f docker/compose.yaml up -d
docker compose -f docker/compose.yaml restart odoo
docker compose -f docker/compose.yaml ps
```

Odoo 20 已运行且健康，登录页面返回 HTTP 200；已核验容器内自定义模块可读。开发库 45 条库存记录的商品、库位、批次、包裹、数量及预留数量与迁移前一致。保留 `bluewms20-postgres-data` 和 `bluewms20-odoo-data` 数据卷，数据库和附件目录未迁移、未删除。

Odoo 19 原来通过直接创建容器运行，并不是 `odoo19企业/Docker/docker-compose.yml` 中的企业环境。按实际容器设置重建 `odoo19`，保留原镜像、环境、网络连接、8079 端口和 `odoo19` 数据卷；`db19` 未修改。19 版原先处于停机状态，迁移后继续保持停机。需要启用时，先启动 `db19`，再启动 `odoo19`。

为便于回退，原 19 容器保留为 `odoo19-before-relocation-20261012`，已禁止自动启动，避免和新容器竞争端口；不要同时运行这两个容器。

Codex 当前 `BlueWMS20` 项目已核验关联 `/Users/jianglang/odoo`，项目身份与历史对话保留。旧 `odoo19` 项目的后端根目录也已更新，但当前侧栏仍缓存旧路径，运行中的应用会覆盖直接修改的旧偏好；如需继续使用该旧侧栏项目，在项目菜单的“编辑项目”中将目录改为 `/Users/jianglang/odoo/odoo19`。CodeBuddy 的项目记忆、计划及 BlueWMS20 文档已更新为新路径。四个已安装的 Odoo skills 使用独立副本，目录移动不会使其失效。BlueWMS Git 远程保持 `https://github.com/bluewms/bluewms.git`。

数据库备份、原容器设置和修改前的配置保存在私有目录 `~/.config/bluewms20/backups/path-relocation-20261012/`。本轮没有提交或推送 GitHub。
