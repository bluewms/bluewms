> 历史 /3 暂停草案，保留审计。当前 /4 知识维护与用户发布入口见 [离线Wiki包](../wiki-publication/wcs-v4/README-用户最后写入.md)，不使用本文上传或运行。

# BlueWMS20 WCS AI创建配置知识 (可独立上传)

> 历史/3草案与暂停记录保留。2026-10-18后续业务澄清已通过/4实施并部署; 当前以 docs/design/wcs-v4-validation.md 和 docs/knowledge/wcs-ai-creation-v4-zh.md 为准。

> 状态: 待业务语义确认的本地实现草案。已在隔离库技术验证, 未部署到开发主库, 未经业务批准, 不应直接作为已批准云端知识发布。用户正在继续解释原代码的业务含义; 后续实现及部署已暂停。

知识版本: 2026-10-18 / wcs_creation/3。适用 Odoo 20, blue_wcs_extension 20.0.1.2.0 及配套 blue_wcs_base。本文来自本地最终合同、模板及自动化业务验证。示例中的数字均为合成测试标识, 不对应任何现场记录; 生成真实草稿时必须使用本地上下文中的标识, 不得照抄示例 ID。本文不含连接地址、密钥或私有身份。

## 1. 云端与本地的职责

云端只生成或修改当前绑定资产的草稿代码、需求和测试, 不直接创建库存/WCS作业, 不连接设备, 不发布。运行时执行本地已发布策略, 不要求每张作业在线调用模型。设备通信、凭据、库存约束、任务锁和固定报文属于固定模块。

MuK 主持工具循环: AI 页面绑定目标资产 -> blue_read_code_asset({}) -> blue_submit_code_draft -> blue_validate_code_draft -> 人工审阅/真实作业试算 -> 人工发布。读取工具会返回精确草稿、测试、需求、摘要、当前正式版本和 contract_specification。提交需携带读取时 draft_hash, 服务端同时检查用户/公司/会话/资产及基础版本; 草稿变化后重新读取或重新打开会话。验证返回 valid/published=false; 验证成功不等于发布或现场验收。

云端 Wiki/Skill 可作为生成参考, 不能扩大本地合同。当前受限 Odoo 会话没有通用 shell、文件、任意 URL 或设备工具; 云端知识只读桥接和按 hook 自动选择任务尚未实现。可人工上传本文, 但上传、团队可读、绑定和模型实际读取正文须分别确认。云端知识不替代本地精确代码和测试。与项目云端知识基线约定一致: 知识在云端发布, 合同/草稿/测试/正式版本/单据执行记录在本地维护。

## 2. 字段归属与无 AI 基础创建

| 项目 | 决策者 | 约束 |
|---|---|---|
| WCS总启用 blue_wcs_enabled | 人工 | AI不能启停 |
| WCS入库类型 wcs_type (in/out, 显示名沿用原字段) | 人工 | WES方向取此人工选择; operation仍为原生incoming/outgoing/internal |
| 设备类别 equipment_category_id、设备 equipment_id | 人工 | 主设备必须明确选定、启用、同公司且符合类别; 不自动猜唯一设备 |
| 任务类型 task_type | 人工 | 主设备所有输出任务必须保持此值, 不从设备默认模板替换 |
| 附加设备 wcs_secondary_equipment_id、附加任务类型 wcs_secondary_task_type | 人工授权 | 只有显式选择且填入类型的附加设备可进入AI范围; 同公司设备列表不是授权 |
| 接力交接位置 wcs_intermediate_location_id | 人工提供标准接力模板的交接点 | AI自定义编排还可用输入允许位置, 须满足连续接力/冻结等检查 |
| WCS生成条件 | AI配置的 condition 和 tasks 条件 | 返回空列表表示等待; 系统底线不能放宽 |
| WCS作业模式/张数/编排 | AI配置的 mode 和 tasks 输出 | 每单元最多4张, 必须含货物任务 |
| 创建数量依据 | AI配置 quantity_basis | 入库必须confirmed; 非入库confirmed或reserved, 均不能超过有效货物/预留 |
| 按容器生成 | AI配置 group_by_container | 合并同一最外层载具的明细, 不拆整载具 |
| 自动创建WCS作业并执行 auto_create_wcs_request_execute | 人工开关 + AI条件 | 未开启时自动创建调度器不创建; 手工“执行WCS”仍可使用 |
| WCS完成后自动验证 is_auto_validate | 人工 | AI不能打开或关闭; 所有步骤完成、需求数量匹配和计划覆盖后才验证 |
| 验证前必须存在WCS作业 is_wcs_required_for_validate | 人工 | AI不能绕过; 已有未完成任务始终阻止库存验证 |

不绑定任何 AI 配置即可使用基础路径: 每条正数量且就绪的移动行一张 goods 直达任务, 起点=line.location_id, 终点=line.location_dest_id, 设备/任务类型严格使用人工选择。无需AI、发布配置、旧生成条件、默认单双模式或业务过滤。入库数量必须实际确认(picked), 非入库使用有效库存和预留。原四项固定字段 wcs_generate_condition、wcs_request_mode、blue_wcs_ready_mode、is_create_wcs_by_container 仅保留旧数据兼容, 不决定 /3 或无AI新计划, 不再展示为创建选项。

单据须已确认且未完成/取消, 数量为正, 明细assigned、可库存跟踪、批次完整、公司正确、起终点未冻结。系统不把“全部行”理解为允许无效数量、无预留、跨公司、重复或已完成单据再次搬运。

无容器行不再被静默跳过: simulation支持; JSON网关须管理员确认并启用设备 supports_loose_goods; 现行HIK/WES协议要求实际载具, 不宣称散件能力。真实设备还需站点条码或AGV地图点、通信及回调认证等现有配置。

同一整载具含多条货物行时, 按行重复下发会搬同一载具多次, 与整载具底线冲突。系统明确报错, 应使用AI容器分组或人工把货物放到不同实际载具。此场景尚不支持“同载具每行独立物理搬运”, 不能靠AI代码放宽。无容器行或不同载具的多行基础创建均支持。

## 3. 实际执行顺序和两阶段合同

1. 权限、人工总开关和单据状态检查, 对创建单据加事务锁。
2. 解析已有单据固定版本或绑定的已发布 /3 配置; 无绑定使用基础设置。
3. 同一份受限代码先以 request.phase="configure" 执行, candidates=[]; result必须是四字段设置对象。
4. 按 group_by_container 分组。没有容器的行即使开启分组仍独立成单元。入库看result_package_id, 其他看package_id, 实际载具取最外层包裹。
5. 根据 quantity_basis 检查确认、预留、库存、批次、冻结、整载具和未覆盖数量。载具在途则等待; 其他独立单元继续。
6. 为每个就绪单元生成实际request和默认tasks候选, 同一代码以phase="tasks"执行, result必须为任务数组。
7. 校验人工授权、起终点、依赖和协议能力。首次真正有任务时固定版本, 原子保存计划、明细数量、任务步骤和准确报文。
8. 独立调度器下发; 回调推进依赖。发送前再次检查库存、确认、冻结、设备协议和散件能力。未知结果保持锁和覆盖, 必须按原任务号核对, 不自动重发新任务。

configure输出精确结构:

```json
{"condition":"ready","mode":"single","quantity_basis":"reserved","group_by_container":false}
```

condition为ready或all_confirmed; mode为single/relay/double_in/double_out; quantity_basis为confirmed/reserved; group_by_container必须布尔。不得增加开关、设备或数量字段。入库reserved会被拒绝。

mode提供可直接沿用的候选:

| mode | 候选任务 |
|---|---|
| single | 人工主设备, 实际源位置 -> 实际目的位置 |
| relay | 主设备: 源 -> 人工交接点; 人工附加设备: 交接点 -> 实际目的, 后段等待第一段end |
| double_in | 主设备搬货到目的位置上级(无上级则目的位置); 主设备从实际目的位置回空至源, 依赖第一段point_or_take, 依赖点为源站点 |
| double_out | 主设备从目的位置供空至源位置上级(无上级则源); 主设备源 -> 目的搬货, 依赖供空point_or_take, 依赖点为目的站点 |

AI可通过输出任务列表调整条件/张数/编排, 不限于照抄候选。但第一段goods必须使用人工主设备和实际源, 最后一段goods须落在允许最终目的范围(single/relay/double_out仅实际目的; double_in还允许目的上级)。所有任务起终点不同且都在allowed_location_ids中。不能修改货物最终库存目的位置。空载具任务只描述空载具动作, 没有额外载具自动搜索/分配能力; 不得宣称已建立空载具库存池。

任务输出每项精确字段:

```json
{"equipment_id":1,"location_res_id":10,"location_dest_id":20,"role":"goods","task_type":"TRANSFER","dependency_step":0,"dependency_event":"end","dependency_point":"","reason":"实际源到目的"}
```

标识和dependency_step必须整数(不接受布尔);五个文本字段最长512字符。role为goods/empty_supply/empty_return; event为end/take/point/point_or_take。步骤按数组从1编号; dependency_step=0表示无前置, 否则只能指向更早步骤。非end依赖必须有非空dependency_point, 点位必须匹配回调, end会兜底释放。货物接力必须连续, 每段依赖上一goods步骤, goods-to-goods只能end释放; 不允许同货独立重复搬运。空任务列表[]表示业务等待, 不报错、不固定版本; 非空却不含goods被拒绝。最多4步, 不能靠多段重复计算库存数量。

## 4. 数量、覆盖、幂等和失败

quantities是本次各移动行尚未覆盖的数量, 键为行ID字符串, 单位为该行uom_id。非取消计划的数量持续覆盖, 包含pending/unknown/failed/completed; 只有整计划确认未发送并取消才释放覆盖。确认过的原明细不能任意改数量/货物/位置, 须先取消未发送计划或按设备结果核对。新增未覆盖行或不同实际载具可在原单据继续补齐, 不因已有一张任务就整单跳过。无载具按行锁定/覆盖, 同一行残余量只创建差额; 真实载具在途等待, 同单已完成搬运的载具若又出现未覆盖货物则报错要求核对, 不再次搬运。数量小于已固定量会报错。

整载具分组包含多货物/批次, 所有行须有一致的实际起终点。非入库必须覆盖最外层载具全部正库存内容; 有未计划货物、未预留或不完整数量将拒绝。完成所有任务不会逐段写库存, 最终仍由Odoo验证一次。WES回调须所有item完成才完成任务; 现行海康签名、报文固定、回调认证继续使用原适配。

等待示例: 实际数量未确认、明细未分配、批次未确认、已覆盖、载具在途、AI条件未满足。真实作业试算显示等待原因; 手动按钮打开该单据任务列表, 可通过试算核查未生成原因。错误示例: 无人工必选项、旧合同、绑定未发布、冻结、跨公司、库存/预留不足、整载具不完整、越权设备/任务类型、不连续接力、未知点位、设备散件能力不足。错误中止本次事务, 不留下半张计划。自动创建遇到业务错误会在单据记录暂停原因。

## 5. 受限代码语法

这是本地JSON策略解释器, 不是Python服务器脚本。允许单变量赋值、JSON字面量、现有字典字符串键读取、if/elif/else、条件表达式、and/or/not、比较(包括in/not in)、有界数字加减乘除。唯一循环为for candidate in candidates, 不可嵌套; 唯一调用为result.append(task)。输入request/candidates/candidate不可赋值, 不可修改字典, 返回对象必须字段精确。

禁止import、def、lambda、class、while、try、推导式、解包、f-string、list索引、属性访问、get/sort/len/dict/str/range等调用、ORM、网络、文件、SQL及凭据访问。不要使用candidate.get(...), 应读合同保证存在的键。configure与tasks字段不同, 必须先判断phase再读取任务字段。

代码最多32768字符、2000个AST节点、30000解释步骤; 输入JSON最多262144字符、有限数值; 源代码数字常量绝对值不超过1e9, 算术结果不超过1e12。最多200条正数量移动行, 每物理单元最多4个任务。试算JSON为2至20个{name,input,expected_result}对象, 必须覆盖configure和tasks阶段, expected_result与执行结果精确相等。

## 6. 生成、修改、试算、发布和兼容

- 在“WCS / AI创建配置”新建资产, 选择名称含AI的 /3 示例。旧/1、/2资产保留, 不修改其模板合同来伪装升级。
- 人工先选择操作类型、设备、设备任务类型和需要的附加设备授权; 真实接力模板还需交接位置。
- 从资产页打开AI生成/修改, 读取最新合同、草稿、测试、需求和摘要。明确缺少现场授权时应请求业务信息, 不假设同公司设备均可用。
- 生成两阶段代码和同时覆盖设置、创建、等待、拒绝边界的测试; 通过提交工具保存草稿, 通过本地验证工具修复错误, 不声称已发布。
- 库存经理用“真实作业试算”选择测试单, 查看实际起终点、数量、任务数和依赖。试算可选择草稿, 不写任务、计划、设备或固定版本; 不选配置可用于查看基础/已绑定执行行为。
- 人工审阅并发布后绑定操作类型; 自动执行与自动验证仍单独由人工开启。建议先模拟设备, 再按现场流程验收适配设备。
- 首次实际创建固定正式版本, 后续修改草稿/发布/回滚不会修改已有计划和准确报文。基础单据首次创建也固定为无AI路径, 后续绑定不追溯更换。
- /1、/2解释器、旧正式快照和固定计划保留; 新计划只接受/3。升级新增模板和迁移说明, 不自动发布、不自动改绑、不调整人工开关。旧绑定可新建/3配置后改绑, 或取消绑定使用基础路径; 已固定旧单据不能靠改绑重解释, 其既有任务仍能发送/回调/核对/完成及库存验证。

## 7. 基础路径可核验案例 (无需任何草稿)

1. 人工启用WCS并选主设备类别、主设备、入出方向和task_type=TRANSFER; 不绑定配置。入库两条无容器明细, 数量10/3, 都assigned且picked, 源S1/S2、目的D1/D2。模拟设备点击执行WCS -> 两计划两任务, S1->D1与S2->D2, 数量10/3, 主设备/TRANSFER。再点仍两任务。旧四项任意值均不改变该行为。
2. 同上先创建一行, 第一任务在途; 增加另一条独立无容器或新载具明细数量4 -> 只新增该行一任务。原任务和快照不变。入库未picked行等待, 确认后可补齐。
3. 自动创建开关关闭, 调度扫描 -> 零任务; 人工开启后扫描 -> 按同一基础路径创建, 仍不自动打开is_auto_validate。
4. 同一整载具两货物行, 无AI -> 明确冲突, 零任务; 改绑容器分组策略并验证 -> 一物理计划含两行货物, 一次搬运。
5. 真实HIK/WES无包裹行 -> 明确不支持, 不静默跳过; 经现场确认支持散件的JSON网关启用supports_loose_goods, 有地图点/条码 -> 可创建含items的逐行报文。

以下附录是精确合同及五组可执行合成样例, 与模块 /3 示例保持一致。每组测试包含配置/入库底线/创建/等待; all_confirmed另含未全部确认。它们验证受限解释器与模板, 库存/设备/权限仍须真实业务测试。

## 附录 A. 完整机器可读字段/结构与限制

configure和tasks输入字段如下; 生产输入完整返回这些字段, 合成试算可省略代码未使用字段。JSON Schema位于input.properties, request_phases另给可读字段说明。任务候选和输出使用同一完整task结构。

```json
{
  "contract": "wcs_creation/3",
  "hook_code": "wcs_creation",
  "execution": "local bounded interpreter; cloud generates drafts only; no publish or device tool",
  "input": {
    "type": "object",
    "required": [
      "request",
      "candidates"
    ],
    "additionalProperties": false,
    "request_phases": {
      "configure": {
        "phase": "configure",
        "picking_id": "integer",
        "state": "string",
        "company_id": "integer",
        "operation": "incoming|outgoing|internal",
        "wcs_type": "in|out (manual)",
        "all_confirmed": "boolean"
      },
      "tasks": {
        "phase": "tasks",
        "settings": "configure result",
        "picking_id": "integer",
        "state": "string",
        "company_id": "integer",
        "operation": "string",
        "wcs_type": "in|out (manual)",
        "confirmed": "boolean",
        "all_confirmed": "boolean",
        "default_condition_met": "boolean",
        "ready": "boolean",
        "source_id": "integer",
        "destination_id": "integer",
        "source_parent_id": "integer",
        "destination_parent_id": "integer",
        "equipment_id": "integer (manual primary)",
        "task_type": "string (manual primary)",
        "secondary_equipment_id": "integer|false (manual)",
        "secondary_task_type": "string",
        "intermediate_location_id": "integer|false",
        "mode": "settings.mode",
        "allowed_location_ids": "integer[]",
        "allowed_equipment_ids": "integer[] (explicit selections only)",
        "allowed_goods_destinations": "integer[]",
        "locations": "object keyed by string ID: {name:string,parent_id:integer|false,point:string}",
        "equipment": "object keyed by string ID: {name:string,category_id:integer|false,task_type:string}",
        "quantities": "object keyed by move line ID string: positive uncovered quantity in line UoM"
      }
    },
    "candidates": "configure: []; tasks: 1-2 full task objects built from chosen mode",
    "properties": {
      "request": {
        "oneOf": [
          {
            "type": "object",
            "properties": {
              "phase": {
                "const": "configure"
              },
              "state": {
                "type": "string"
              },
              "operation": {
                "type": "string"
              },
              "wcs_type": {
                "type": "string"
              },
              "picking_id": {
                "type": "integer"
              },
              "company_id": {
                "type": "integer"
              },
              "all_confirmed": {
                "type": "boolean"
              }
            },
            "required": [
              "phase",
              "state",
              "operation",
              "wcs_type",
              "picking_id",
              "company_id",
              "all_confirmed"
            ],
            "additionalProperties": false
          },
          {
            "type": "object",
            "properties": {
              "phase": {
                "const": "tasks"
              },
              "state": {
                "type": "string"
              },
              "operation": {
                "type": "string"
              },
              "wcs_type": {
                "type": "string"
              },
              "picking_id": {
                "type": "integer"
              },
              "company_id": {
                "type": "integer"
              },
              "all_confirmed": {
                "type": "boolean"
              },
              "settings": {
                "type": "object",
                "additionalProperties": false,
                "required": [
                  "condition",
                  "mode",
                  "quantity_basis",
                  "group_by_container"
                ],
                "properties": {
                  "condition": {
                    "enum": [
                      "ready",
                      "all_confirmed"
                    ]
                  },
                  "mode": {
                    "enum": [
                      "single",
                      "relay",
                      "double_in",
                      "double_out"
                    ]
                  },
                  "quantity_basis": {
                    "enum": [
                      "confirmed",
                      "reserved"
                    ]
                  },
                  "group_by_container": {
                    "type": "boolean"
                  }
                }
              },
              "source_id": {
                "type": "integer"
              },
              "destination_id": {
                "type": "integer"
              },
              "source_parent_id": {
                "type": "integer"
              },
              "destination_parent_id": {
                "type": "integer"
              },
              "equipment_id": {
                "type": "integer"
              },
              "secondary_equipment_id": {
                "oneOf": [
                  {
                    "type": "integer"
                  },
                  {
                    "const": false
                  }
                ]
              },
              "intermediate_location_id": {
                "oneOf": [
                  {
                    "type": "integer"
                  },
                  {
                    "const": false
                  }
                ]
              },
              "confirmed": {
                "type": "boolean"
              },
              "default_condition_met": {
                "type": "boolean"
              },
              "ready": {
                "type": "boolean"
              },
              "task_type": {
                "type": "string"
              },
              "secondary_task_type": {
                "type": "string"
              },
              "mode": {
                "type": "string"
              },
              "allowed_location_ids": {
                "type": "array",
                "items": {
                  "type": "integer"
                }
              },
              "allowed_equipment_ids": {
                "type": "array",
                "items": {
                  "type": "integer"
                }
              },
              "allowed_goods_destinations": {
                "type": "array",
                "items": {
                  "type": "integer"
                }
              },
              "locations": {
                "type": "object",
                "additionalProperties": {
                  "type": "object",
                  "required": [
                    "name",
                    "parent_id",
                    "point"
                  ],
                  "additionalProperties": false,
                  "properties": {
                    "name": {
                      "type": "string"
                    },
                    "parent_id": {
                      "oneOf": [
                        {
                          "type": "integer"
                        },
                        {
                          "const": false
                        }
                      ]
                    },
                    "point": {
                      "type": "string"
                    }
                  }
                }
              },
              "equipment": {
                "type": "object",
                "additionalProperties": {
                  "type": "object",
                  "required": [
                    "name",
                    "category_id",
                    "task_type"
                  ],
                  "additionalProperties": false,
                  "properties": {
                    "name": {
                      "type": "string"
                    },
                    "category_id": {
                      "oneOf": [
                        {
                          "type": "integer"
                        },
                        {
                          "const": false
                        }
                      ]
                    },
                    "task_type": {
                      "type": "string"
                    }
                  }
                }
              },
              "quantities": {
                "type": "object",
                "additionalProperties": {
                  "type": "number",
                  "minimum": 0
                }
              }
            },
            "required": [
              "phase",
              "state",
              "operation",
              "wcs_type",
              "picking_id",
              "company_id",
              "all_confirmed",
              "settings",
              "source_id",
              "destination_id",
              "source_parent_id",
              "destination_parent_id",
              "equipment_id",
              "secondary_equipment_id",
              "intermediate_location_id",
              "confirmed",
              "default_condition_met",
              "ready",
              "task_type",
              "secondary_task_type",
              "mode",
              "allowed_location_ids",
              "allowed_equipment_ids",
              "allowed_goods_destinations",
              "locations",
              "equipment",
              "quantities"
            ],
            "additionalProperties": false
          }
        ]
      },
      "candidates": {
        "type": "array",
        "maxItems": 4,
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": [
            "equipment_id",
            "location_res_id",
            "location_dest_id",
            "role",
            "task_type",
            "dependency_step",
            "dependency_event",
            "dependency_point",
            "reason"
          ],
          "properties": {
            "equipment_id": {
              "type": "integer"
            },
            "location_res_id": {
              "type": "integer"
            },
            "location_dest_id": {
              "type": "integer"
            },
            "role": {
              "enum": [
                "goods",
                "empty_supply",
                "empty_return"
              ]
            },
            "task_type": {
              "type": "string",
              "maxLength": 512
            },
            "dependency_step": {
              "type": "integer",
              "minimum": 0
            },
            "dependency_event": {
              "enum": [
                "end",
                "take",
                "point",
                "point_or_take"
              ]
            },
            "dependency_point": {
              "type": "string",
              "maxLength": 512
            },
            "reason": {
              "type": "string",
              "maxLength": 512
            }
          }
        },
        "description": "Empty in configure; generated task defaults in tasks."
      }
    }
  },
  "configure_output": {
    "type": "object",
    "additionalProperties": false,
    "required": [
      "condition",
      "mode",
      "quantity_basis",
      "group_by_container"
    ],
    "properties": {
      "condition": {
        "enum": [
          "ready",
          "all_confirmed"
        ]
      },
      "mode": {
        "enum": [
          "single",
          "relay",
          "double_in",
          "double_out"
        ]
      },
      "quantity_basis": {
        "enum": [
          "confirmed",
          "reserved"
        ]
      },
      "group_by_container": {
        "type": "boolean"
      }
    }
  },
  "tasks_output": {
    "type": "array",
    "maxItems": 4,
    "items": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "equipment_id",
        "location_res_id",
        "location_dest_id",
        "role",
        "task_type",
        "dependency_step",
        "dependency_event",
        "dependency_point",
        "reason"
      ],
      "properties": {
        "equipment_id": {
          "type": "integer"
        },
        "location_res_id": {
          "type": "integer"
        },
        "location_dest_id": {
          "type": "integer"
        },
        "role": {
          "enum": [
            "goods",
            "empty_supply",
            "empty_return"
          ]
        },
        "task_type": {
          "type": "string",
          "maxLength": 512
        },
        "dependency_step": {
          "type": "integer",
          "minimum": 0
        },
        "dependency_event": {
          "enum": [
            "end",
            "take",
            "point",
            "point_or_take"
          ]
        },
        "dependency_point": {
          "type": "string",
          "maxLength": 512
        },
        "reason": {
          "type": "string",
          "maxLength": 512
        }
      }
    }
  },
  "syntax": {
    "allowed": [
      "single variable assignment",
      "JSON literals",
      "existing dictionary string-key subscripts",
      "if/elif/else",
      "conditional expression",
      "for candidate in candidates",
      "result.append(task)",
      "and/or/not",
      "comparisons including in/not in",
      "bounded numeric + - * /"
    ],
    "forbidden": [
      "imports",
      "functions",
      "ORM",
      "network",
      "filesystem",
      "attributes except result.append",
      "get/sort/len/dict/str and all other calls",
      "list indexing",
      "comprehensions",
      "nested loops",
      "while",
      "try",
      "dictionary mutation",
      "dictionary expansion"
    ],
    "limits": {
      "code_characters": 32768,
      "AST_nodes": 2000,
      "steps": 30000,
      "input_bytes_convention": "JSON text <=262144 characters",
      "text_characters": 512
    }
  },
  "invariants": [
    "inbound quantity_basis=confirmed",
    "all selected stock lines assigned, storable and lots complete",
    "outbound valid stock and reservation",
    "no frozen or cross-company locations",
    "whole carrier completeness",
    "noncancelled plans cover quantities; busy carrier waits; completed carrier cannot move again on same picking",
    "first goods starts at actual source and manual primary equipment; final approved destination",
    "goods relay continuous with end dependency; explicit earlier dependency steps only",
    "equipment restricted to primary/secondary; task_type equals manual authorization",
    "no AI control of WCS/automatic creation/automatic validation/required-task switches",
    "no package: simulation or explicitly capable JSON gateway only; HIK/WES require carrier"
  ],
  "trials": {
    "schema": "{name:string,input:{request:object,candidates:array},expected_result:object|array}",
    "count": "2..20; include configure and tasks phases"
  }
}
```

## 附录 B.1 AI逐行直达

```python
if request["phase"] == "configure":
    result = {"condition": "ready", "mode": "single", "quantity_basis": "confirmed" if request["operation"] == "incoming" else "reserved", "group_by_container": False}
else:
    result = []
    for candidate in candidates:
        if request["ready"] and request["default_condition_met"]:
            result.append(candidate)
```

可直接放入本地“试算样例 JSON”的精确用例:

```json
[
  {
    "name": "策略先于分组",
    "input": {
      "request": {
        "phase": "configure",
        "operation": "internal"
      },
      "candidates": []
    },
    "expected_result": {
      "condition": "ready",
      "mode": "single",
      "quantity_basis": "reserved",
      "group_by_container": false
    }
  },
  {
    "name": "入库实际确认",
    "input": {
      "request": {
        "phase": "configure",
        "operation": "incoming"
      },
      "candidates": []
    },
    "expected_result": {
      "condition": "ready",
      "mode": "single",
      "quantity_basis": "confirmed",
      "group_by_container": false
    }
  },
  {
    "name": "创建编排",
    "input": {
      "request": {
        "phase": "tasks",
        "settings": {
          "condition": "ready",
          "mode": "single",
          "quantity_basis": "reserved",
          "group_by_container": false
        },
        "operation": "internal",
        "wcs_type": "out",
        "ready": true,
        "all_confirmed": true,
        "source_id": 10,
        "destination_id": 20,
        "source_parent_id": 15,
        "destination_parent_id": 25,
        "equipment_id": 1,
        "task_type": "TRANSFER",
        "secondary_equipment_id": 2,
        "secondary_task_type": "LEG2",
        "intermediate_location_id": 15,
        "allowed_location_ids": [
          10,
          15,
          20,
          25
        ],
        "allowed_equipment_ids": [
          1,
          2
        ],
        "allowed_goods_destinations": [
          20
        ],
        "equipment": {
          "1": {
            "name": "Primary",
            "category_id": 1,
            "task_type": "TRANSFER"
          },
          "2": {
            "name": "Secondary",
            "category_id": 2,
            "task_type": "LEG2"
          }
        },
        "default_condition_met": true
      },
      "candidates": [
        {
          "equipment_id": 1,
          "location_res_id": 10,
          "location_dest_id": 20,
          "role": "goods",
          "task_type": "TRANSFER",
          "dependency_step": 0,
          "dependency_event": "end",
          "dependency_point": "",
          "reason": "基础逐行直达作业"
        }
      ]
    },
    "expected_result": [
      {
        "equipment_id": 1,
        "location_res_id": 10,
        "location_dest_id": 20,
        "role": "goods",
        "task_type": "TRANSFER",
        "dependency_step": 0,
        "dependency_event": "end",
        "dependency_point": "",
        "reason": "基础逐行直达作业"
      }
    ]
  },
  {
    "name": "等待",
    "input": {
      "request": {
        "phase": "tasks",
        "settings": {
          "condition": "ready",
          "mode": "single",
          "quantity_basis": "reserved",
          "group_by_container": false
        },
        "operation": "internal",
        "wcs_type": "out",
        "ready": false,
        "all_confirmed": true,
        "source_id": 10,
        "destination_id": 20,
        "source_parent_id": 15,
        "destination_parent_id": 25,
        "equipment_id": 1,
        "task_type": "TRANSFER",
        "secondary_equipment_id": 2,
        "secondary_task_type": "LEG2",
        "intermediate_location_id": 15,
        "allowed_location_ids": [
          10,
          15,
          20,
          25
        ],
        "allowed_equipment_ids": [
          1,
          2
        ],
        "allowed_goods_destinations": [
          20
        ],
        "equipment": {
          "1": {
            "name": "Primary",
            "category_id": 1,
            "task_type": "TRANSFER"
          },
          "2": {
            "name": "Secondary",
            "category_id": 2,
            "task_type": "LEG2"
          }
        },
        "default_condition_met": true
      },
      "candidates": [
        {
          "equipment_id": 1,
          "location_res_id": 10,
          "location_dest_id": 20,
          "role": "goods",
          "task_type": "TRANSFER",
          "dependency_step": 0,
          "dependency_event": "end",
          "dependency_point": "",
          "reason": "基础逐行直达作业"
        }
      ]
    },
    "expected_result": []
  }
]
```

## 附录 B.2 AI全部确认后创建

```python
if request["phase"] == "configure":
    result = {"condition": "all_confirmed", "mode": "single", "quantity_basis": "confirmed" if request["operation"] == "incoming" else "reserved", "group_by_container": False}
else:
    result = []
    for candidate in candidates:
        if request["ready"] and request["default_condition_met"]:
            result.append(candidate)
```

可直接放入本地“试算样例 JSON”的精确用例:

```json
[
  {
    "name": "策略先于分组",
    "input": {
      "request": {
        "phase": "configure",
        "operation": "internal"
      },
      "candidates": []
    },
    "expected_result": {
      "condition": "all_confirmed",
      "mode": "single",
      "quantity_basis": "reserved",
      "group_by_container": false
    }
  },
  {
    "name": "入库实际确认",
    "input": {
      "request": {
        "phase": "configure",
        "operation": "incoming"
      },
      "candidates": []
    },
    "expected_result": {
      "condition": "all_confirmed",
      "mode": "single",
      "quantity_basis": "confirmed",
      "group_by_container": false
    }
  },
  {
    "name": "创建编排",
    "input": {
      "request": {
        "phase": "tasks",
        "settings": {
          "condition": "all_confirmed",
          "mode": "single",
          "quantity_basis": "reserved",
          "group_by_container": false
        },
        "operation": "internal",
        "wcs_type": "out",
        "ready": true,
        "all_confirmed": true,
        "source_id": 10,
        "destination_id": 20,
        "source_parent_id": 15,
        "destination_parent_id": 25,
        "equipment_id": 1,
        "task_type": "TRANSFER",
        "secondary_equipment_id": 2,
        "secondary_task_type": "LEG2",
        "intermediate_location_id": 15,
        "allowed_location_ids": [
          10,
          15,
          20,
          25
        ],
        "allowed_equipment_ids": [
          1,
          2
        ],
        "allowed_goods_destinations": [
          20
        ],
        "equipment": {
          "1": {
            "name": "Primary",
            "category_id": 1,
            "task_type": "TRANSFER"
          },
          "2": {
            "name": "Secondary",
            "category_id": 2,
            "task_type": "LEG2"
          }
        },
        "default_condition_met": true
      },
      "candidates": [
        {
          "equipment_id": 1,
          "location_res_id": 10,
          "location_dest_id": 20,
          "role": "goods",
          "task_type": "TRANSFER",
          "dependency_step": 0,
          "dependency_event": "end",
          "dependency_point": "",
          "reason": "基础逐行直达作业"
        }
      ]
    },
    "expected_result": [
      {
        "equipment_id": 1,
        "location_res_id": 10,
        "location_dest_id": 20,
        "role": "goods",
        "task_type": "TRANSFER",
        "dependency_step": 0,
        "dependency_event": "end",
        "dependency_point": "",
        "reason": "基础逐行直达作业"
      }
    ]
  },
  {
    "name": "等待",
    "input": {
      "request": {
        "phase": "tasks",
        "settings": {
          "condition": "all_confirmed",
          "mode": "single",
          "quantity_basis": "reserved",
          "group_by_container": false
        },
        "operation": "internal",
        "wcs_type": "out",
        "ready": false,
        "all_confirmed": true,
        "source_id": 10,
        "destination_id": 20,
        "source_parent_id": 15,
        "destination_parent_id": 25,
        "equipment_id": 1,
        "task_type": "TRANSFER",
        "secondary_equipment_id": 2,
        "secondary_task_type": "LEG2",
        "intermediate_location_id": 15,
        "allowed_location_ids": [
          10,
          15,
          20,
          25
        ],
        "allowed_equipment_ids": [
          1,
          2
        ],
        "allowed_goods_destinations": [
          20
        ],
        "equipment": {
          "1": {
            "name": "Primary",
            "category_id": 1,
            "task_type": "TRANSFER"
          },
          "2": {
            "name": "Secondary",
            "category_id": 2,
            "task_type": "LEG2"
          }
        },
        "default_condition_met": true
      },
      "candidates": [
        {
          "equipment_id": 1,
          "location_res_id": 10,
          "location_dest_id": 20,
          "role": "goods",
          "task_type": "TRANSFER",
          "dependency_step": 0,
          "dependency_event": "end",
          "dependency_point": "",
          "reason": "基础逐行直达作业"
        }
      ]
    },
    "expected_result": []
  },
  {
    "name": "部分未确认",
    "input": {
      "request": {
        "phase": "tasks",
        "settings": {
          "condition": "all_confirmed",
          "mode": "single",
          "quantity_basis": "reserved",
          "group_by_container": false
        },
        "operation": "internal",
        "wcs_type": "out",
        "ready": true,
        "all_confirmed": false,
        "source_id": 10,
        "destination_id": 20,
        "source_parent_id": 15,
        "destination_parent_id": 25,
        "equipment_id": 1,
        "task_type": "TRANSFER",
        "secondary_equipment_id": 2,
        "secondary_task_type": "LEG2",
        "intermediate_location_id": 15,
        "allowed_location_ids": [
          10,
          15,
          20,
          25
        ],
        "allowed_equipment_ids": [
          1,
          2
        ],
        "allowed_goods_destinations": [
          20
        ],
        "equipment": {
          "1": {
            "name": "Primary",
            "category_id": 1,
            "task_type": "TRANSFER"
          },
          "2": {
            "name": "Secondary",
            "category_id": 2,
            "task_type": "LEG2"
          }
        },
        "default_condition_met": false
      },
      "candidates": [
        {
          "equipment_id": 1,
          "location_res_id": 10,
          "location_dest_id": 20,
          "role": "goods",
          "task_type": "TRANSFER",
          "dependency_step": 0,
          "dependency_event": "end",
          "dependency_point": "",
          "reason": "基础逐行直达作业"
        }
      ]
    },
    "expected_result": []
  }
]
```

## 附录 B.3 AI同货两段接力

```python
if request["phase"] == "configure":
    result = {"condition": "ready", "mode": "relay", "quantity_basis": "confirmed" if request["operation"] == "incoming" else "reserved", "group_by_container": True}
else:
    result = []
    for candidate in candidates:
        if request["ready"] and request["default_condition_met"]:
            result.append(candidate)
```

可直接放入本地“试算样例 JSON”的精确用例:

```json
[
  {
    "name": "策略先于分组",
    "input": {
      "request": {
        "phase": "configure",
        "operation": "internal"
      },
      "candidates": []
    },
    "expected_result": {
      "condition": "ready",
      "mode": "relay",
      "quantity_basis": "reserved",
      "group_by_container": true
    }
  },
  {
    "name": "入库实际确认",
    "input": {
      "request": {
        "phase": "configure",
        "operation": "incoming"
      },
      "candidates": []
    },
    "expected_result": {
      "condition": "ready",
      "mode": "relay",
      "quantity_basis": "confirmed",
      "group_by_container": true
    }
  },
  {
    "name": "创建编排",
    "input": {
      "request": {
        "phase": "tasks",
        "settings": {
          "condition": "ready",
          "mode": "relay",
          "quantity_basis": "reserved",
          "group_by_container": true
        },
        "operation": "internal",
        "wcs_type": "out",
        "ready": true,
        "all_confirmed": true,
        "source_id": 10,
        "destination_id": 20,
        "source_parent_id": 15,
        "destination_parent_id": 25,
        "equipment_id": 1,
        "task_type": "TRANSFER",
        "secondary_equipment_id": 2,
        "secondary_task_type": "LEG2",
        "intermediate_location_id": 15,
        "allowed_location_ids": [
          10,
          15,
          20,
          25
        ],
        "allowed_equipment_ids": [
          1,
          2
        ],
        "allowed_goods_destinations": [
          20
        ],
        "equipment": {
          "1": {
            "name": "Primary",
            "category_id": 1,
            "task_type": "TRANSFER"
          },
          "2": {
            "name": "Secondary",
            "category_id": 2,
            "task_type": "LEG2"
          }
        },
        "default_condition_met": true
      },
      "candidates": [
        {
          "equipment_id": 1,
          "location_res_id": 10,
          "location_dest_id": 15,
          "role": "goods",
          "task_type": "TRANSFER",
          "dependency_step": 0,
          "dependency_event": "end",
          "dependency_point": "",
          "reason": "基础逐行直达作业"
        },
        {
          "equipment_id": 2,
          "location_res_id": 15,
          "location_dest_id": 20,
          "role": "goods",
          "task_type": "LEG2",
          "dependency_step": 1,
          "dependency_event": "end",
          "dependency_point": "",
          "reason": "基础逐行直达作业"
        }
      ]
    },
    "expected_result": [
      {
        "equipment_id": 1,
        "location_res_id": 10,
        "location_dest_id": 15,
        "role": "goods",
        "task_type": "TRANSFER",
        "dependency_step": 0,
        "dependency_event": "end",
        "dependency_point": "",
        "reason": "基础逐行直达作业"
      },
      {
        "equipment_id": 2,
        "location_res_id": 15,
        "location_dest_id": 20,
        "role": "goods",
        "task_type": "LEG2",
        "dependency_step": 1,
        "dependency_event": "end",
        "dependency_point": "",
        "reason": "基础逐行直达作业"
      }
    ]
  },
  {
    "name": "等待",
    "input": {
      "request": {
        "phase": "tasks",
        "settings": {
          "condition": "ready",
          "mode": "relay",
          "quantity_basis": "reserved",
          "group_by_container": true
        },
        "operation": "internal",
        "wcs_type": "out",
        "ready": false,
        "all_confirmed": true,
        "source_id": 10,
        "destination_id": 20,
        "source_parent_id": 15,
        "destination_parent_id": 25,
        "equipment_id": 1,
        "task_type": "TRANSFER",
        "secondary_equipment_id": 2,
        "secondary_task_type": "LEG2",
        "intermediate_location_id": 15,
        "allowed_location_ids": [
          10,
          15,
          20,
          25
        ],
        "allowed_equipment_ids": [
          1,
          2
        ],
        "allowed_goods_destinations": [
          20
        ],
        "equipment": {
          "1": {
            "name": "Primary",
            "category_id": 1,
            "task_type": "TRANSFER"
          },
          "2": {
            "name": "Secondary",
            "category_id": 2,
            "task_type": "LEG2"
          }
        },
        "default_condition_met": true
      },
      "candidates": [
        {
          "equipment_id": 1,
          "location_res_id": 10,
          "location_dest_id": 15,
          "role": "goods",
          "task_type": "TRANSFER",
          "dependency_step": 0,
          "dependency_event": "end",
          "dependency_point": "",
          "reason": "基础逐行直达作业"
        },
        {
          "equipment_id": 2,
          "location_res_id": 15,
          "location_dest_id": 20,
          "role": "goods",
          "task_type": "LEG2",
          "dependency_step": 1,
          "dependency_event": "end",
          "dependency_point": "",
          "reason": "基础逐行直达作业"
        }
      ]
    },
    "expected_result": []
  }
]
```

## 附录 B.4 AI按容器直达

```python
if request["phase"] == "configure":
    result = {"condition": "ready", "mode": "single", "quantity_basis": "confirmed" if request["operation"] == "incoming" else "reserved", "group_by_container": True}
else:
    result = []
    for candidate in candidates:
        if request["ready"] and request["default_condition_met"]:
            result.append(candidate)
```

可直接放入本地“试算样例 JSON”的精确用例:

```json
[
  {
    "name": "策略先于分组",
    "input": {
      "request": {
        "phase": "configure",
        "operation": "internal"
      },
      "candidates": []
    },
    "expected_result": {
      "condition": "ready",
      "mode": "single",
      "quantity_basis": "reserved",
      "group_by_container": true
    }
  },
  {
    "name": "入库实际确认",
    "input": {
      "request": {
        "phase": "configure",
        "operation": "incoming"
      },
      "candidates": []
    },
    "expected_result": {
      "condition": "ready",
      "mode": "single",
      "quantity_basis": "confirmed",
      "group_by_container": true
    }
  },
  {
    "name": "创建编排",
    "input": {
      "request": {
        "phase": "tasks",
        "settings": {
          "condition": "ready",
          "mode": "single",
          "quantity_basis": "reserved",
          "group_by_container": true
        },
        "operation": "internal",
        "wcs_type": "out",
        "ready": true,
        "all_confirmed": true,
        "source_id": 10,
        "destination_id": 20,
        "source_parent_id": 15,
        "destination_parent_id": 25,
        "equipment_id": 1,
        "task_type": "TRANSFER",
        "secondary_equipment_id": 2,
        "secondary_task_type": "LEG2",
        "intermediate_location_id": 15,
        "allowed_location_ids": [
          10,
          15,
          20,
          25
        ],
        "allowed_equipment_ids": [
          1,
          2
        ],
        "allowed_goods_destinations": [
          20
        ],
        "equipment": {
          "1": {
            "name": "Primary",
            "category_id": 1,
            "task_type": "TRANSFER"
          },
          "2": {
            "name": "Secondary",
            "category_id": 2,
            "task_type": "LEG2"
          }
        },
        "default_condition_met": true
      },
      "candidates": [
        {
          "equipment_id": 1,
          "location_res_id": 10,
          "location_dest_id": 20,
          "role": "goods",
          "task_type": "TRANSFER",
          "dependency_step": 0,
          "dependency_event": "end",
          "dependency_point": "",
          "reason": "基础逐行直达作业"
        }
      ]
    },
    "expected_result": [
      {
        "equipment_id": 1,
        "location_res_id": 10,
        "location_dest_id": 20,
        "role": "goods",
        "task_type": "TRANSFER",
        "dependency_step": 0,
        "dependency_event": "end",
        "dependency_point": "",
        "reason": "基础逐行直达作业"
      }
    ]
  },
  {
    "name": "等待",
    "input": {
      "request": {
        "phase": "tasks",
        "settings": {
          "condition": "ready",
          "mode": "single",
          "quantity_basis": "reserved",
          "group_by_container": true
        },
        "operation": "internal",
        "wcs_type": "out",
        "ready": false,
        "all_confirmed": true,
        "source_id": 10,
        "destination_id": 20,
        "source_parent_id": 15,
        "destination_parent_id": 25,
        "equipment_id": 1,
        "task_type": "TRANSFER",
        "secondary_equipment_id": 2,
        "secondary_task_type": "LEG2",
        "intermediate_location_id": 15,
        "allowed_location_ids": [
          10,
          15,
          20,
          25
        ],
        "allowed_equipment_ids": [
          1,
          2
        ],
        "allowed_goods_destinations": [
          20
        ],
        "equipment": {
          "1": {
            "name": "Primary",
            "category_id": 1,
            "task_type": "TRANSFER"
          },
          "2": {
            "name": "Secondary",
            "category_id": 2,
            "task_type": "LEG2"
          }
        },
        "default_condition_met": true
      },
      "candidates": [
        {
          "equipment_id": 1,
          "location_res_id": 10,
          "location_dest_id": 20,
          "role": "goods",
          "task_type": "TRANSFER",
          "dependency_step": 0,
          "dependency_event": "end",
          "dependency_point": "",
          "reason": "基础逐行直达作业"
        }
      ]
    },
    "expected_result": []
  }
]
```

## 附录 B.5 AI空载具配合

```python
if request["phase"] == "configure":
    result = {"condition": "ready", "mode": "double_in", "quantity_basis": "confirmed" if request["operation"] == "incoming" else "reserved", "group_by_container": True}
else:
    result = []
    for candidate in candidates:
        if request["ready"] and request["default_condition_met"]:
            result.append(candidate)
```

可直接放入本地“试算样例 JSON”的精确用例:

```json
[
  {
    "name": "策略先于分组",
    "input": {
      "request": {
        "phase": "configure",
        "operation": "internal"
      },
      "candidates": []
    },
    "expected_result": {
      "condition": "ready",
      "mode": "double_in",
      "quantity_basis": "reserved",
      "group_by_container": true
    }
  },
  {
    "name": "入库实际确认",
    "input": {
      "request": {
        "phase": "configure",
        "operation": "incoming"
      },
      "candidates": []
    },
    "expected_result": {
      "condition": "ready",
      "mode": "double_in",
      "quantity_basis": "confirmed",
      "group_by_container": true
    }
  },
  {
    "name": "创建编排",
    "input": {
      "request": {
        "phase": "tasks",
        "settings": {
          "condition": "ready",
          "mode": "double_in",
          "quantity_basis": "reserved",
          "group_by_container": true
        },
        "operation": "internal",
        "wcs_type": "out",
        "ready": true,
        "all_confirmed": true,
        "source_id": 10,
        "destination_id": 20,
        "source_parent_id": 15,
        "destination_parent_id": 25,
        "equipment_id": 1,
        "task_type": "TRANSFER",
        "secondary_equipment_id": 2,
        "secondary_task_type": "LEG2",
        "intermediate_location_id": 15,
        "allowed_location_ids": [
          10,
          15,
          20,
          25
        ],
        "allowed_equipment_ids": [
          1,
          2
        ],
        "allowed_goods_destinations": [
          20,
          25
        ],
        "equipment": {
          "1": {
            "name": "Primary",
            "category_id": 1,
            "task_type": "TRANSFER"
          },
          "2": {
            "name": "Secondary",
            "category_id": 2,
            "task_type": "LEG2"
          }
        },
        "default_condition_met": true
      },
      "candidates": [
        {
          "equipment_id": 1,
          "location_res_id": 10,
          "location_dest_id": 25,
          "role": "goods",
          "task_type": "TRANSFER",
          "dependency_step": 0,
          "dependency_event": "end",
          "dependency_point": "",
          "reason": "基础逐行直达作业"
        },
        {
          "equipment_id": 1,
          "location_res_id": 20,
          "location_dest_id": 10,
          "role": "empty_return",
          "task_type": "TRANSFER",
          "dependency_step": 1,
          "dependency_event": "point_or_take",
          "dependency_point": "A",
          "reason": "基础逐行直达作业"
        }
      ]
    },
    "expected_result": [
      {
        "equipment_id": 1,
        "location_res_id": 10,
        "location_dest_id": 25,
        "role": "goods",
        "task_type": "TRANSFER",
        "dependency_step": 0,
        "dependency_event": "end",
        "dependency_point": "",
        "reason": "基础逐行直达作业"
      },
      {
        "equipment_id": 1,
        "location_res_id": 20,
        "location_dest_id": 10,
        "role": "empty_return",
        "task_type": "TRANSFER",
        "dependency_step": 1,
        "dependency_event": "point_or_take",
        "dependency_point": "A",
        "reason": "基础逐行直达作业"
      }
    ]
  },
  {
    "name": "等待",
    "input": {
      "request": {
        "phase": "tasks",
        "settings": {
          "condition": "ready",
          "mode": "double_in",
          "quantity_basis": "reserved",
          "group_by_container": true
        },
        "operation": "internal",
        "wcs_type": "out",
        "ready": false,
        "all_confirmed": true,
        "source_id": 10,
        "destination_id": 20,
        "source_parent_id": 15,
        "destination_parent_id": 25,
        "equipment_id": 1,
        "task_type": "TRANSFER",
        "secondary_equipment_id": 2,
        "secondary_task_type": "LEG2",
        "intermediate_location_id": 15,
        "allowed_location_ids": [
          10,
          15,
          20,
          25
        ],
        "allowed_equipment_ids": [
          1,
          2
        ],
        "allowed_goods_destinations": [
          20,
          25
        ],
        "equipment": {
          "1": {
            "name": "Primary",
            "category_id": 1,
            "task_type": "TRANSFER"
          },
          "2": {
            "name": "Secondary",
            "category_id": 2,
            "task_type": "LEG2"
          }
        },
        "default_condition_met": true
      },
      "candidates": [
        {
          "equipment_id": 1,
          "location_res_id": 10,
          "location_dest_id": 25,
          "role": "goods",
          "task_type": "TRANSFER",
          "dependency_step": 0,
          "dependency_event": "end",
          "dependency_point": "",
          "reason": "基础逐行直达作业"
        },
        {
          "equipment_id": 1,
          "location_res_id": 20,
          "location_dest_id": 10,
          "role": "empty_return",
          "task_type": "TRANSFER",
          "dependency_step": 1,
          "dependency_event": "point_or_take",
          "dependency_point": "A",
          "reason": "基础逐行直达作业"
        }
      ]
    },
    "expected_result": []
  }
]
```

## 验证证据与限制

模板与本文附录来自同一份已执行用例. 隔离数据库中覆盖无AI逐行/自动开关/幂等补齐、库存预留/冻结/多货整载具、策略设置先执行、人工设备与任务类型不可改写、接力依赖、版本固定及旧合同隔离、真实试算只读、AI草稿工具、HIK签名和回调、WES多item完成. 并发重复创建只保留一个计划/两段接力和一次数量覆盖; 调度发送与回调最终完成一次库存验证. 真实设备联网、现场搬运和云端模型实际读取本文不在本次验证范围内; 不得把模拟/HTTP桩测试宣称为设备验收.
