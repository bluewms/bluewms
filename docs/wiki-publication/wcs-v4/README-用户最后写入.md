# WCS /4 Wiki离线发布资料包

> 后续开发交接见 [WCS /4交接](../../migrations/wcs-v4-handoff.md)。当前仍强制Skill bridge，用户拟后续改为Memory Hub原生Wiki检索；该替换尚未实现或验证。本文只记录现有链路的候选发布步骤，不表示必须现在发布Skill。

状态: 本地已准备, **没有写入云端Wiki或Skill**, 由用户最后操作。不要把本包的候选正文当成已经在云端批准。既有上架知识实际只读验证为bluewms-policy-authoring版本4, 三个批准资源; Wiki真实ID/当前页清单未通过现有只读Skill bridge查询, 没有猜造新的Wiki ID或版本。

## 目录与唯一来源

使用已有项目Wiki **BlueWMS20 Project Knowledge and Approved Policy Examples**, 在平台的WIKI入口下组织, 不新建同名孤立知识库, 不移动或删除其他用户/项目资产:

```text
WIKI
└── BlueWMS20 Project Knowledge and Approved Policy Examples (已有)
    ├── basics/                       通用规则、工具步骤
    ├── domains/putaway/              上架规范与原三个案例, 保留
    ├── domains/wcs/
    │   ├── specification.md          WCS生成规范
    │   ├── configuration-guide.md    全部配置/字段归属/条件/数量/位置边界
    │   ├── wcs-creation-v4-contract.json  本地合同导出核对附件
    │   └── examples/                10个独立例子, 每页准确代码+完整试算
    ├── domains/erp/                  原planned资料, 不改为可执行
    ├── domains/equipment/            原planned资料
    └── domains/barcode/              原planned资料
```

wiki/是按此结构准备的发布来源; 既有匹配页面优先更新并保留历史版本。putaway页面只是供对照, 不要求重复上传或覆盖已批准资料。工程部署/Git/账号密钥/运维日志不放入生成Wiki。docs/knowledge与旧outputs里的大文档标为历史快照, 不再维护另一份运行知识。

skill/不是另一套权威知识库, 是沿用上架现有 **Wiki批准正文 -> 版本化Skill只读分发镜像 -> Odoo工具** 的兼容包。Odoo不会扫描本地wiki目录, 也没有知识写入工具。

## 用户写入顺序

1. 在现有项目Wiki中核对同名页面/目录, 保存服务端原版本或导出备份; 按wiki/目录更新通用规则与WCS规范、配置说明、10个例子。保留上架与无关资产。先作为草稿检查正文, 例子中的ID均是合成标识。
2. 对照manifest.json和各页准确代码/试算, 用户审阅后按既有平台流程批准/锁定新Wiki版本。记录平台实际返回的 **wiki_id和Wiki版本**。
3. 在已有Skill **bluewms-policy-authoring** 发布一个新版本, 不新建同名Skill、不删除旧版本。更新主文SKILL.md及共享01-project-and-governance.md, 新增06-wcs-creation-contract.md与07-approved-wcs-examples.md。03/04沿用服务端已批准版本的原文, 应逐字保留; 本公开资料包不分发实际云端读取快照。02/05等其他既有资源也保留, 不因为本包没有附上就删除。
4. 新版本metadata合并skill/metadata-after-user-approval.json, 保留原purpose/approved等字段。**将wiki_source.wiki_id和wiki_source.version的null填成第2步平台实际值**, 不填示例/猜测ID。approved_contracts保留上架/1、/2并加入WCS/4。用户确认完成后将该新版本设为active且approved=true。正文开头的bluewms-knowledge标记必须保留。
5. 保持现有项目团队/Agent可见性和绑定, 不新增权限或更换业务Key。保留上架三个运行路径, 旧会话可固定原版本; 新会话读取新版本。不得把上架正文改名伪装为WCS。
6. 在Odoo新建“WCS增强接口 /4”资产或从已有/4资产打开新浮窗, 先发送一条只读请求: “只调用blue_read_code_asset并说明hook、合同、Wiki来源版本及资源路径, 不提交或发布任何草稿。”
7. 确认工具返回approved=true、hook_code=wcs_creation、contract=wcs_creation/4、wiki_source为第2步实际值, 资源是01/06/07, 不是03/04。再进行生成/修改、验证和人工发布。主库不要以真实仓储任务做知识联调。

不要求修改代码, 不要求把云端ID写入Odoo字段: 客户端按唯一Skill名称查可见资源, 从批准metadata读取真实Wiki引用。若改Skill名称、资源路径或合同, 需另做受控客户端升级, 不能任意改名后期待兼容。

## 失败行为与回滚

未上传WCS正文、未批准、合同/头标不符、Wiki引用未填、旧本地引用、超时/超量会明确报错, 不使用本地示例或上架正文。无AI基础生成和既有已发布策略仍离线可执行。

若新云端版本有误, 将Skill head切回原批准版本, Wiki恢复原页面版本; 不删除旧资源或业务策略。恢复旧Skill版本后WCS草稿知识读取会明确缺失, 上架既有固定版本继续可用。已经生成/发布的本地代码不会被知识回滚改写。

## 字节限制与验收

上架和WCS各自按hook读取三个固定资源, 总bundle上限32768 UTF-8 JSON字节。manifest记录本包上架约12.5KB、WCS约18.2KB, 留有元数据余量。完整25条试算在Wiki各例子页, 初始运行分发是同源精确代码与条件摘要, 没有把117KB综合历史文稿硬塞进32KB接口。

填写upload-receipt.json里的真实新版本/URL/摘要后, 可按验证说明只读核对。这里只准备材料, 未执行任何云端创建/修改/移动/删除/批准。
