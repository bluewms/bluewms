# MuK AI／Skills／MCP 20.0 安装与验证记录

日期：2026-10-12。范围：用户指定的 `muk_ai`、`muk_ai_skills`、`muk_mcp`。

## 官方来源与版本

三个模块均在 [MuK 官方开源仓库](https://github.com/muk-it/odoo-modules/tree/20.0) 的 `20.0` 分支存在，采用 LGPL-3，锁定提交 `754f7a221d550f642d59ca332b025f0cdf55d955`。使用官方 20 源码，不复制旧 `odoo19/addons/rent` 的实现，不修改上游核心。

| 模块 | 版本 | 许可证 | 本地开发库状态 |
|---|---|---|---|
| `muk_ai` | `20.0.1.25.2` | LGPL-3 | 已安装 |
| `muk_ai_skills` | `20.0.1.4.8` | LGPL-3 | 已安装 |
| `muk_mcp` | `20.0.4.2.1` | LGPL-3 | 已安装 |

模块均置于 `bluewms` 的直接子目录，Docker 挂载至 `/mnt/extra-addons`，与前批 MuK Web 模块同一 Git 工作区管理。依赖中的 `muk_web_utils` 已于前批安装；官方 `attachment_indexation` 自动补齐，开发库版本为 `20.0.2.1`。

逐文件 SHA-256、依赖与来源保存在 `muk-ai-lock.json`，全部核对与官方源码一致。上游许可保存在同目录 `MuK-LICENSE`，各模块原始版权和许可文件保留。未引入嵌套 `.git`。

## 实际安装与验证

- 运行环境：Docker `odoo:20`，Odoo `20.0-20260926`、Python `3.12.3`，数据库镜像 `postgres:16.0`。
- 首先在独立新库 `bluewms20_ai_test` 安装并测试，使用无演示数据配置。上游测试选择 `/muk_ai,/muk_ai_skills,/muk_mcp,-hoot,-/muk_mcp:TestPlaygroundTour`，覆盖 **309 项后端／HTTP 测试，0 失败、0 错误，退出码 0**。
- 测试覆盖模型／provider 解析、流式事件、会话与工具流程、审批和访问限制、技能共享、MCP 鉴权／工具／资源等。测试使用模拟或 mock provider，不构成真实模型服务联调。
- 安装到开发库 `bluewms20` 前停止 Odoo，备份数据库与 filestore；安装 `muk_ai_skills`，自动安装另两个模块与必要依赖，进程退出码 0。SQL 核对三个模块均为 `installed`；安装后恢复 Odoo，容器健康检查通过。
- 在独立测试库成功编译 `web.assets_web`、`web.assets_web_dark`、`web.assets_backend_lazy`、`muk_ai.assets_markdown`，CSS 错误列表为空，进程退出码 0；这不等于浏览器实际运行验收。
- 实际开发服务 `/web/login` 返回 200；未带凭据的 `POST /api/mcp` 返回 401。开发库已配置模型 Key 的 provider 数量为 0，MCP Key 数量为 0。

## 使用状态与边界

本次只安装官方基础能力，未填模型厂商 Key、未创建 MCP Key、未调用付费模型、未连接 Tencent 或宝蓝云端网关。AI 会话仍需配置合法 provider 和模型后进行真实联调。

官方本次 provider 注册为 OpenAI、Anthropic、Google；旧 19 工程中的 DeepSeek 自定义实现未随安装迁移，如需要，应通过独立 provider 扩展实现。宝蓝五类业务协议、场景／代码资产、生成验证发布和恢复仍按正式开发计划实施。

Docker 镜像无 Chromium，故排除 HOOT 和 MCP Playground 浏览器 tour；AI 弹窗、技能面板及 Playground 的桌面／移动端实际交互尚未验收。测试期间有 5 处 `Database or registry unusable` 警告及测试游标堆栈，原始日志保留；测试汇总没有失败或错误，开发实例启动日志未发现 ERROR。不能据此宣称整份日志无警告。

## 备份与交付材料

仓库外备份／日志目录：`~/.config/bluewms20/backups/muk-ai-20261012-095839/`，含 `bluewms20.dump`、`filestore.tar.gz`、`install.log`、`tests.log`、`assets.log`。没有执行整库恢复演练。测试数据库保留用于后续验证，与开发库分开。

本地源码、版本锁和报告已准备好；本次未提交或推送 GitHub。旧 19 模块与数据库未修改。

## 2026-10-13 中文补充

AI、Skills和MCP的中文翻译已应用到开发库, 共1,290条; POT同步更新, 计价单位补充语言相关显示. 本地补丁已单独写入来源锁, 原官方版本和许可保留. 范围与验收见 [中文翻译记录](muk-ai-zh-2026-10-13.md).
