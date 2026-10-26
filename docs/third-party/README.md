# 第三方依赖

MuK 模块来自 [官方 Odoo 20 分支](https://github.com/muk-it/odoo-modules/tree/20.0)，保留原名称、作者及 LGPL-3 许可。原始上游说明见 [MuK README](MuK-upstream-README.md)，许可全文见 [MuK-LICENSE](MuK-LICENSE)。

[Web 来源锁](muk-web-lock.json) 和 [AI 来源锁](muk-ai-lock.json) 保存引入提交、逐文件摘要和本地翻译补丁；版本以实际模块 manifest 为准。中文翻译和计价单位显示补丁不改变模型价格或费用计算。

第三方源码与库存/AI/品牌业务扩展分开维护；品牌及客户行为使用独立 `blue_*` 模块。安装、测试和运行当前步骤见 [Docker 指南](../../docker/README.md) 与 [验证指南](../testing/README.md)。历史安装过程从 Git 查阅，不在这里重复维护阶段日志。

## 旧模块来源证据

以下记录用于核对来源、许可与原文件摘要, 保留原始提交和内容, 不代表当前版本已重新验收:

- [库存基础来源](provenance/blue-stock-source-lock.json)
- [盘库模块来源](provenance/stock-inventory-source-lock.json)
- [库存规则来源](provenance/stock-rules-source-lock.json)

阶段性测试数字和开发进度从 Git 历史查阅, 不再维护独立 validation 目录.
