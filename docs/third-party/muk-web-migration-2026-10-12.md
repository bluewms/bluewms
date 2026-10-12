# MuK Web 20.0 首批迁移记录

日期：2026-10-12。范围：用户指定的 7 个 `muk_web_*` 模块及其必要依赖。

## 来源与处理方式

7 个模块均在 [MuK 官方开源仓库](https://github.com/muk-it/odoo-modules/tree/20.0) 的 `20.0` 分支存在，清单许可证均为 LGPL-3，因此采用官方 Odoo 20 版本，无需自行重写。来源锁定提交：`754f7a221d550f642d59ca332b025f0cdf55d955`。

模块直接放在 `bluewms` 根目录的子目录，Docker 挂载至 `/mnt/extra-addons`。未带入上游 `.git`，未修改第三方源码。版本、依赖和逐文件 SHA-256 见 `muk-web-lock.json`；上游仓库许可和 README 分别保存在 `MuK-LICENSE`、`MuK-upstream-README.md`。

## 模块清单

| 模块 | 官方版本 | 范围 | 本机开发库状态 |
|---|---|---|---|
| `muk_web_appsbar` | `20.0.1.2.7` | 指定模块 | 已安装 |
| `muk_web_chatter` | `20.0.1.5.11` | 指定模块 | 已安装 |
| `muk_web_colors` | `20.0.1.0.25` | 指定模块 | 已安装 |
| `muk_web_dialog` | `20.0.1.0.20` | 指定模块 | 已安装 |
| `muk_web_group` | `20.0.1.0.15` | 指定模块 | 已安装 |
| `muk_web_refresh` | `20.0.1.1.19` | 指定模块 | 已安装 |
| `muk_web_theme` | `20.0.1.5.7` | 指定模块 | 已安装 |
| `muk_web_utils` | `20.0.1.2.19` | 主题必要依赖 | 已安装 |
| `muk_web_list_column` | `20.0.1.0.11` | 主题必要依赖 | 已安装 |
| `muk_web_list_mode` | `20.0.1.1.3` | 主题必要依赖 | 已安装 |

新版 `muk_web_theme` 增加对 `muk_web_utils`、`muk_web_list_column`、`muk_web_list_mode` 的依赖，故一并引入；`base_automation` 等官方依赖由 Odoo 安装流程处理。本轮不安装 MuK AI 或额外设备模块。

旧 19 的 `muk_web_theme/__manifest__.py` 包含 BlueWMS 名称、作者、网站等定制。新版本保留 MuK 原始归属；品牌或行为差异后续通过独立 `blue_*` 模块扩展，不将这些定制直接覆盖到官方源码。

## 实际环境与验证

- Docker 镜像：`odoo:20`，运行版本 `20.0-20260926`、Python `3.12.3`；数据库镜像 `postgres:16.0`。
- 实际开发库：`bluewms20`；安装 `muk_web_theme` 并自动安装全部依赖，安装进程退出码 0；SQL 核对上述 10 个模块均为 `installed`。
- 安装前停止开发 Odoo 服务，完成数据库与 filestore 备份；完成后恢复服务，容器健康检查通过。
- 独立测试库：`bluewms20_muk_test`，使用无演示数据新库进行安装，并执行这 10 个模块的上游测试，明确排除 `hoot` 浏览器测试；结果为 **34 项测试，0 失败、0 错误，退出码 0**。覆盖用户偏好、会话上下文、颜色设置、主题初始化、消息、刷新服务器动作及工具方法。
- 独立测试库中的 `web.assets_backend`、`web.assets_web`、`web.assets_web_dark` 的 CSS／JavaScript 均成功生成，CSS 错误列表为空，编译进程退出码 0。首次在开发库做额外编译时遇到并发更新冲突，改到隔离测试库后通过；没有为此修改官方代码。
- 登录页在本机浏览器可加载；尚未完成登录后的完整桌面／移动端操作验收。

## 限制与日志

测试结果输出后、测试服务关闭阶段出现 `cursor already closed` 和相关 HTTP 请求异常，保留原始日志供后续定位，不能将退出码 0 描述为整份日志没有异常。现有 Docker 镜像缺少 Chromium，因此 **未运行 HOOT 浏览器交互测试**，折叠、弹窗、侧栏、列表交互及移动端仍需专项验证。

安装日志提示现有镜像缺少 `markdown2`，影响邮件 Markdown 渲染；本轮未临时修改容器依赖。若项目需要该功能，应通过可重建镜像增加依赖。

备份及原始安装／测试日志位于仓库外：`~/.config/bluewms20/backups/muk-web-20261012-094901/`，包含 `bluewms20.dump`、`filestore.tar.gz`、`install.log`、`tests.log` 和 `assets.log`。恢复整库前停止作业，按环境说明一并恢复对应数据库及 filestore；本轮没有执行恢复演练。

模块、许可、版本锁和本报告已在本地 Git 工作区准备好；本轮未提交或推送 GitHub。旧 19 工程和官方 Odoo 核心未修改。
