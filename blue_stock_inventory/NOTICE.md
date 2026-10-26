# 模块说明与保留声明

本模块由宁波宝蓝物流科技有限公司维护, 为 Odoo 20 实现独立人工盘库, 使用当前原生库存调整接口处理数量、并发、权限及追溯. 保留 stock.inventory / stock.inventory.line 等业务技术名, 不表示整套旧盘库模块源码直接搬入.

models/res_company.py 与 models/res_config_settings.py 中的自动完成配置字段仍保留 ForgeFlow S.L. 的版权及 LGPL-3.0-or-later 声明. 当前模块 manifest、LICENSE 和具体文件内的声明保持现状.

旧设置视图、营销素材和客户数据库不包含在本模块中. 当前功能以源码和测试为准, 不再以旧版逐文件摘要台账描述本实现.
