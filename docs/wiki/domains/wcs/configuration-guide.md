# WCS /4 配置说明与业务边界

知识版本: 2026-10-18 / `wcs_creation/4`。适用 Odoo20 与 blue_wcs_extension 20.0.1.4.0 / blue_wcs_base 20.0.1.3.0。本文以本地运行合同与业务测试为准, 按Wiki目录分篇发布。文中ID为合成用例标识, 不对应现场记录; 真实策略必须使用本地输入。本文无密钥、连接地址或私有身份。**知识上传不代表配置已发布或真实设备已验收。**

## 1. 核心业务模型

**当前单据全部有效基础行 → AI逐行选择/等待/数量依据 → 容器或同路线组合/物理位置映射 → 建立第一张任务定义并可追加同数据任务 → 按依赖下发 → 最后一次库存验证。**

“先生成再加同样任务”发生在内存中的任务定义编排阶段, 不先向设备发送再改历史。一张计划可含两张甚至多张相同货物数据、相同设备、相同起终点的goods任务。每张任务有独立任务号、序号、报文和完成回调。第一张未完成时第二张为waiting; 仅取货/点位通知不放行同数据后续任务。默认示例使用end依赖, /4后续goods程序要求上一goods完成。空载具配合仍可明确配置take/point/point_or_take事件。

这与重复点击、重复定时扫描或并发重新创建整组任务不同。前者是明确授权的计划内多程序, 合法; 后者仍按已覆盖数量及物理载具锁阻止。计划只保存一份货物明细及数量, 不因两张任务覆盖/预留/记账两次。所有程序完成后才允许库存单据验证一次。

云端只生成草稿及测试。运行时使用本地已发布代码, 无需每单在线请求模型。云端无直接发布、设备控制、ORM、网络、文件或shell权限。

## 2. 无AI路径和人工权限

不绑定任何AI配置时: 人工启用WCS并明确选择WCS入库类型(in/out)、设备类别、设备和任务类型后, 每条正数量且实际可执行的移动行一张直达goods任务。物理起点=行原位置, 终点=行目的位置, 主设备/任务类型严格使用人工选择。不要求AI服务、发布草稿、默认单双模式或旧业务过滤条件。自动触发须人工开启自动创建开关, 手动执行可独立使用。

基础行来源为当前单据全部正数量移动行, 不在AI前按picked、容器、旧生成条件筛出一个小集合。AI看到每行的数量、覆盖、确认、库存/预留、冻结、商品/批次、载具和位置。数量为0/负值的行不属于有效搬运量; 最多200条有效行, 仍受输入体积上限约束。

入库实际数量必须确认(picked); 非入库以有效库存和预留即可搬运, 不强制picked。AI可为非入库选择更严格的confirmed依据, 或通过行/载具/整单条件等待。所有路径都保留assigned、可库存跟踪、批次、公司、冻结、实际库存/预留、整载具实际货物完整、防并发重复创建等固定校验。

| 配置 | 权限 |
|---|---|
| WCS总启用 blue_wcs_enabled | 人工, AI不可启停 |
| WCS入库类型 wcs_type, 设备类别 equipment_category_id, 主设备 equipment_id, task_type | 人工明确选择; AI不可替换或猜唯一设备 |
| 附加设备 wcs_secondary_equipment_id / wcs_secondary_task_type | 人工明确授权; 同公司设备全集不等于授权 |
| 标准交接位置 wcs_intermediate_location_id | 人工配置的可解释交接点 |
| 自动创建并执行 auto_create_wcs_request_execute | 人工开关 + 策略条件 |
| 完成后自动验证 is_auto_validate | 人工开关, AI不能改写; 全步骤完成、数量匹配、覆盖与库存检查后才验证 |
| 验证前必须存在WCS作业 is_wcs_required_for_validate | 人工开关, AI不能放宽; 即便策略排除全部行也不能满足“必须有作业” |
| 逐行生成条件、数量依据/数量、分组、物理位置来源、单/双/多任务 | AI本地策略, 受系统底线约束 |
| 设备散件、库区映射、同数据多任务能力 | 人工确认设备能力, 不能由AI开启 |

旧 wcs_generate_condition / wcs_request_mode / blue_wcs_ready_mode / is_create_wcs_by_container 仅为旧合同兼容数据。无AI及/4不使用这些字段作提前过滤; /1-/2兼容路径仍按原设置构造旧候选, 保持明确历史语义。

## 3. /4两阶段合同, 不只是旧Selection搬到策略

同一份受限代码根据request.phase分支执行。

### lines阶段

输入 `{request,candidates}`。candidates是全部有效行, 还没有按AI业务条件过滤或创建任务。每行必须返回且只返回一次决策:

```json
{"line_id":101,"action":"create","quantity_basis":"reserved","quantity":10,"group_key":"line:101","source_ref":"line_source","destination_ref":"line_destination","reason":"有效预留货物直接搬运"}
```

- action: create / wait / exclude。wait=本次不创建, 条件变化后重试; exclude=该行无需WCS, 库存仍按原业务处理。两者都必须有原因, quantity=0。不得靠遗漏行表达过滤。
- quantity_basis: confirmed / reserved。入库create只能confirmed; 非入库reserved无需picked, confirmed额外要求本行picked。
- quantity: 本次WCS量, 使用行uom_id, 不能超过available_quantity。无容器可选择较小有效量并在以后补齐剩余量; 整个物理载具不可只选部分货物量。
- group_key: 相同键合并一个物理计划。可使用输入line_key、carrier_key、route_key, 或有界自定义键。不能把不同物理载具合并一张搬运计划。无容器、同路线可合并不同商品/批次并保留完整明细; 相同载具组合必须覆盖其全部实际货物。
- source_ref / destination_ref: 决定第一goods任务的物理位置来源, 不是改写库存位置。组合内需一致的映射来源; 行位置多值时不能假选第一行, 可显式映射到包含所有实际位置的单据库区。

### tasks阶段

固定服务在行决策后先分组、复核数量和安全条件。对每个就绪组, 输入request.lines(完整行字典)、decisions、positions、position_details、equipment及base_task。candidates包含该组第一张基础goods定义。输出0到4张任务。result=[]表示整组条件等待, 不创建、不固定版本。

完整任务对象:

```json
{"equipment_id":1,"location_res_id":10,"location_dest_id":20,"source_ref":"line_source","destination_ref":"line_destination","role":"goods","task_type":"TRANSFER","movement":"primary","dependency_step":0,"dependency_event":"end","dependency_point":"","reason":"基础搬运程序"}
```

movement: primary=首个goods程序; repeat=与前一个goods相同的货物数据、设备、任务类型及物理位置, 独立身份的后续程序; relay=从前一个goods终点接续搬运; empty=空载具配合。非空列表必须有goods。

第一goods必须使用人工主设备和行阶段决定的映射。后续goods必须明确repeat或relay, dependency_step指向上一goods序号, event=end。repeat允许完全相同起终点, 不作为重复创建错误。relay要求起点连接前段终点。示例默认完整串行; 不支持同货多goods无依赖并行。

role: goods / empty_supply / empty_return。空载具步骤不附带商品明细, movement=empty, 不扩大库存数量, 也不表示已实现空载具库存池搜索或自动分配。可以安排在第一goods前面或后面; 若首goods依赖供空, 可配置明确点位/取货事件。end事件仍作为依赖释放兜底。

dependency_step=0表示无前置, 其他值只能是更早的数组步骤(从1编号); event为end/take/point/point_or_take, 非end依赖必须填写点位。失败、unknown或仅点位/取货不会自动完成货物程序, unknown须可信完成回调或人工核对。未发送失败不能伪造完成回调。

## 4. 数量、条件范围、容器与满载

下列概念独立, 不可互相代替:

| 概念/输入 | 精确含义 |
|---|---|
| candidate.picked | 这一行的实际数量确认 |
| candidate.carrier_all_picked | 本单据同最外层载具全部正数量行都已确认 |
| request.all_confirmed | 本单据全部正数量行都已确认, 即使某行无需WCS仍计入 |
| 容器达到搬运阈值 | 策略显式标准, 例如有完整重量基础数据且合计重量达到8; 并非天然等于all_picked |
| 整载具实际货物完整 | 系统安全约束: 不得把未计划货物随载具一起移动; 与是否装满无关 |

现有输入包括同载具同UoM数量(carrier_same_uom / carrier_quantity)、基于产品基础单位换算的carrier_weight/volume及完整性标志、原生包装类型package_max_weight。重量/体积取产品基础数据乘转换后的商品基础数量; 基础数据任一缺失(<=0)时complete=false。carrier_quantity在混单位时为false, 不盲目相加。package_max_weight是已配置的原生“最大运输重量”, 不是最小满载标准; 未配置为false。

已支持明确阈值表达式, 附录给出8重量单位标准, 对缺数据或不足阈值逐行wait。现场要明确所用系统重量单位及阈值, 不照抄8作统一满载值。允许未满载的容器可使用不加阈值的容器示例, 仍执行全部实际货物完整性校验。项目当前无统一“装箱完成/满载”业务标记, 不宣称已自动识别装满; 新标准可扩展行输入构造方法_wcs4_input并升级合同, 不需要引入陌生外部代码。

非取消计划持续覆盖原行数量, 含待发送/失败/unknown/已完成。追加相同任务不追加plan.line, 只增加task。重扫只处理未覆盖量; 不因整单已存在一个任务而跳过其他独立行/载具。载具在途等待, 同单已搬运载具又出现未覆盖货物则要求核对; 无容器可补差额。正常用户不能改写已固定计划货物, 取消整组未发送任务才释放覆盖并允许新修订。

同一物理载具多行必须组合完整搬运; 无AI逐行在该物理冲突场景给出明确错误, 不静默漏行, 不重复搬整载具。AI过滤后若留下未计划的同载具货物, 等待并说明原因, 不用exclude突破载具完整性。发送前再次核对载具货物/数量/预留/冻结; 规划后新增货物也不能悄悄带走。

## 5. 设备物理位置映射与库存记账位置

| 引用 | 物理位置来自 |
|---|---|
| line_source / line_destination | 组内唯一行原位置/目的位置; 多值时返回false, 要求显式映射 |
| picking_source / picking_destination | 单据原位置/目的位置 |
| source_parent / destination_parent | 行位置上级, 需唯一 |
| handoff | 人工配置交接位置 |

position_details提供位置名称和站点编码, 不包含凭据。所有任务端点必须与声明来源一致, 不接受任意ID。快照保存映射来源、物理端点及原库存商品/数量/位置指纹。首goods物理起点范围须包含原库存源, 最后goods物理终点范围须包含原库存目的; 中间可经handoff连续接力。因此支持单据库区而不是强制唯一行细点, 同时不允许无依据映射到不相关仓区。

库存只按原行位置最终验证, 不在创建/发送/回调时擅自改写数量或位置。库区任务可回报声明范围本身, 或组内唯一且已计划的准确目的站点; 设备回报其他分配细点将暂停核对, 不自动接受并写回库存。多行不同实际目的细点的库区回调仅支持声明范围确认, 逐item新库位分配的自动回写属于未来扩展。

simulation支持库区模拟。HIK使用ZONE类型表达范围; JSON需人工启用supports_location_scope并现场确认网关语义。WES当前报文仅按既有库存端点执行, 不宣称已支持本次任意物理范围映射。

## 6. 适配能力及失败处理

- 无容器: simulation支持; JSON须人工开启supports_loose_goods; HIK/WES当前需要实际载具。不会静默跳过无容器行。
- 同数据多任务: simulation可完整测试; 真实设备须人工确认supports_repeated_goods。独立任务号对HIK/JSON/WES具有不同外部业务含义, 需现场验收后启用, 不能把同数据程序误用成外部仓储系统重复出入库单。本文没有声称已完成真实设备测试。
- 标准接力额外设备必须人工选择并填写授权任务类型, 不把同公司全部设备交给AI。
- 真实设备需要地图点/条码及原通信/回调认证配置; 凭据不进入策略上下文。更改已固定设备协议或取消其能力会阻止发送。
- 预览逐行显示创建/等待/无需WCS及原因、组数量、设备、物理点位和依赖; 不创建任务、不固定版本。条件等待重试不会生成空计划。
- 非法输出、越权设备/类型、冻结、公司错误、库存不足、错误位置映射等中止事务, 不留半组任务; 自动扫描会记录暂停原因。
- 明确exclude的WCS豁免需固定策略及原行指纹一致, 包含确认状态。改数量/货物/位置后原豁免失效; 与已计划载具共享的新增货物不能借排除豁免。
- 等待行仍是未覆盖WCS量, 其他步骤完成后也不能用排除豁免验证。人工“必须有WCS”开关继续有效, 已有步骤必须全部完成。自动验证还要求原生需求量与实际量匹配。

## 7. 真实语法与生成流程

受限解释器接受JSON数据, 不编译或eval Python。允许单变量赋值、JSON字面量、已有字典字符串键读取、if/elif/else、条件表达式、and/or/not、比较(in/not in)、有界数字加减乘除。唯一循环是`for candidate in candidates`, 不嵌套; 唯一调用是`result.append({...})`。可先把`request["base_task"]`赋给first, 再用明确字段字典定义second; 不需要列表索引或复制函数。

禁止import/def/class/lambda/while/try/推导式/字典展开/f-string、ORM/SQL/网络/文件、属性读取、get/len/dict/str/range等调用、list索引和输入字典修改。request/candidates/candidate不可重新赋值。不同phase有不同字段, 必须分支后再读取。没有因本轮需求开放任意Python或新依赖。

限制: 代码32768字符, 2000 AST节点, 30000解释步骤; 输入有限JSON且最多262144字符; 文本输出最多512字符; 最多200基础行、每计划最多4步骤。复杂200行大分组也须满足输入体积上限。每资产2至20个{name,input,expected_result}精确试算, 必须同时覆盖lines/tasks; 验证成功不等于现场业务验收。

流程: 新建“AI创建配置”并选择唯一基础运行定义“WCS增强接口 /4” → 说明逐行选择、数量与容器标准、位置来源和任务语义 → 从资产页打开MuK AI → blue_read_code_asset({})读取精确草稿/摘要/正式基础/完整contract_schema(兼容contract_specification别名) → blue_submit_code_draft携带draft_hash保存 → blue_validate_code_draft本地验证并修复 → 人工真实作业试算 → 人工发布并绑定 → 人工选择是否启用自动创建/自动验证。

AI工具没有发布工具, 云端不能执行设备动作。WCS按hook读取批准云端01/06/07正文并固定Skill与Wiki来源版本; 尚未由用户上传或批准时明确报错, 不回退本地示例或上架正文。MuK主持工具循环, 云端Wiki/Skill可供参考但不能授予不存在的本地权限。新上架与WCS /4会话已按hook路由Task; 上架已接入批准Skill只读桥接, WCS客户端只读接入已就绪, 对应云端正文仍待用户写入和批准; 人工上传本文后仍需确认模型确实读取正文。发布和回滚只影响后续未固定业务; 已固定单据继续原正式版本或无AI路径。旧/1-/3解释器/模板/草稿/版本/发布/任务及报文保留, 不自动转合同、不自动发布。/2绑定可继续受人工设备授权约束的旧编排; 完整新能力新建/4配置后人工试算改绑。已固定旧单据不被/4重新解释。

## 8. 可复现业务验收案例

1. 无AI, 两个独立就绪行 → 两个直达任务, 保持各自行起终点及人工设备类型。重扫不增加; 新增独立行只补新增量。自动开关关闭不自动建, 开启后按同路径执行。
2. 同数据双任务 → 同一plan两task, 相同items/设备/起终点, 不同任务号。第一张take/point不释放第二张; 第一张end后第二张可发送; 两张end后库存只从原源到原目记一次, 计划数量10不会变20。并发双点击仍一plan两task。
3. 一行人工搬运exclude、一行已picked create、另一行未picked wait → 三行均有解释。只建create行; wait仍阻止未覆盖WCS验证; 确认wait行后补齐, exclude行按原库存作业正常验证。
4. 载具多货物/批次组合 → 一份完整plan.line列表, 不按任务张数重复数量; 若同载具一行被过滤, 不能把它顺带搬走。
5. 重量缺失 → 明确等待基础数据; 完整但不足显式阈值 → 等待装载; 达到阈值 → 可创建。与是否全部picked、是否实际货物全纳入分别核验。
6. 行目的为细点, 单据目的为包含它的库区 → 物理任务可用库区, 记录来源, 库存明细不变; 回报未计划细点拒绝, 回报唯一已计划细点可完成。
7. 无容器JSON未声明能力 → 具体报错; 人工确认能力后可创建items任务。HIK/WES无载具仍报错, 不假称散件支持。

[独立示例页面](examples/README.md)包含由实际解释器执行的10组代码与25个精确合成用例；测试数据仅在测试目录加载，生产不安装示例正文。输入Schema描述完整生产字段，合成试算允许省略未使用输入键。不要将合成ID用于现场。




知识状态: verified; 尚未由用户写入/批准云端。本文是Wiki发布来源, 生产Odoo不读取本地文档。
