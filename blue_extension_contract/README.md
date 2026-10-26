# 受限执行合同

为纯 JSON 增强策略提供受限 AST 解释器、机器可读字段／语法／输出及资源边界。`_describe(contract)` 返回当前安装版本的准确合同，不提供 ORM、导入、网络、文件或任意 Python 调用。

上架 v1／v2 保持兼容；WCS 由对应扩展注册合同，新生成使用 /4 的 lines/tasks，旧 /1–/3 历史保留。规范和示例不能给解释器增加能力，正式代码在本地执行。

业务使用见[上架说明](../docs/guides/putaway.md)和[WCS 设计](../docs/guides/wcs.md)，知识读取见[原生 Wiki 接入](../docs/guides/ai.md)。
