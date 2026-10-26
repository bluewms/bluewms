# 上架策略 AI 生成规范

hook：`putaway_policy`。状态：已实现并有验证证据。更新：2026-10-17。适用接口：`putaway_policy/1`、`putaway_policy/2`；以本地读取工具返回的版本和 `contract_schema` 为准。

## 生成目标

生成原生上架策略之后的增强代码：在系统已经批准的候选位置中增加限制或排序。仓库、作业类型和适用库区由原生规则决定，增强场景不重复设置这三个范围；原生规则通过“增强策略”字段选择场景。

三个标准案例分别维护在 [示例目录](examples/README.md)，不在本规范中复制代码。

## 系统约束与输入

系统先处理原生规则范围和优先级、存储类别、重量、产品混放、容量、冻结／禁止入库及公司权限。包裹／托盘按外层物理单元去重，已上架和待上架均计入数量；整托盘不能被补充代码拆分。散件在系统允许时可以按容量拆分。

输入只有纯 JSON `request` 和 `candidates`。常用字段如下，完整字典由当前本地合同提供：

| 位置 | 字段 | 语义 |
|---|---|---|
| request | `unit`、`product_ids`、`picking_id` | 整托或散件、产品集合与当前作业单 |
| request | `batch_name`、`has_single_batch_name`、`has_unknown_batch` | 整个分配单元的批次号情况 |
| candidate | `location_id`、`system_priority` | 已准入的位置与原生优先级 |
| candidate | `same_lot`、`same_picking`、`empty` | 同产品同批次、同单相关位置及空位 |
| candidate | `batch_name_matches`、`batch_names`、`has_unknown_batch` | 位置内批次号匹配与未知情况 |
| candidate | `package_capacity`、`occupied_packages`、`packages_after` | 系统托盘容量及占用 |
| candidate | `max_quantity`、`fits_all` | 当前系统可分配数量及能否全部容纳 |

跨产品比较批次号文本，不比较产品专属的 lot ID。`same_picking` 是当前实现按已用／待上架位置形成的偏好，不承诺全单全局最优或库位独占。

## 代码和输出

受限语法支持局部赋值、`for candidate in candidates`、if/elif/else、条件表达式、字典已有键读取、比较／布尔及有界算术。唯一函数调用是 `result.append({...})`。不允许 `.get()`、sort/sorted、len、导入、ORM、网络、文件、函数定义、while 或任意 Python 执行。

输出变量为 `result`，每项严格包含 `location_id`、有限数值 `score` 和文本 `reason`；位置 ID 必须来自候选且唯一，允许只返回子集。分数越小越优先。解释器按 score／位置 ID 排序，真实上架最终先按原生优先级，再按补充分数／位置 ID；测试顺序不代表可以越过系统优先级。

空结果表示本条增强规则没有批准位置；原生流程可能继续尝试其他规则，未绑定策略的回退规则不会自动继承此限制。若业务要求所有可用路径都遵守同批次号等限制，配置时必须检查相关原生规则和回退路径，不能只凭一个代码示例认定为全局约束。

## 资源和测试

代码最多 32768 字符、2000 个 AST 节点、30000 执行步骤；候选最多 200 个，输入 JSON 上限 262144 字符。分数绝对值最多 100000，原因最多 512 字符；其他边界以实际合同为准。

试算为 1–20 条 JSON 数组，每项恰含 `name`、`input`、`expected_order`。`input` 至少包含该段代码实际读取的字段；标准示例的最小试算不是运行时完整字段字典。试算通过后还需检查真实单据预览和业务约束。

## 发布与版本

先读取资产和批准知识，再提交并验证；用户审核发布。单据按“作业单＋原生规则”固定首次选中的策略／正式版本，含当时无策略的情况。发布新版本不改变旧绑定；回滚不撤销已经完成的库存移动。

实际能力以当前工具返回的本地合同为准。知识只能说明现有字段和规则，不能新增能力或放宽校验；发生冲突时停止使用不匹配的示例，明确说明需要确认的接口版本。

完整核对附件: [合同 /1](putaway-policy-v1-contract.json)、[合同 /2](putaway-policy-v2-contract.json). 本实例返回的 contract_schema 始终优先.
