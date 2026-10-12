# 来源与修改

本模块由宝蓝维护, 将旧 stock_no_negative 和 stock_location_lockdown 的库存保护设计适配到 Odoo 20, 保留 AGPL-3.0-or-later 及原贡献者归属。

旧源码版权头包含 Akretion / Alexis de Lattre、ForgeFlow / Jordi Ballester。相关旧模块还列出 Serpent Consulting Services、Tecnativa / Pedro M. Baeza、Spacefoot / Quentin Delcourte、Vishnu Vanneri 等贡献者。本模块不将这些来源声明为宝蓝独立原创。

源代码基线为本地 BlueWMS19 提交 7d77ae713b81ddef4de856361ac14ea99fedf967。2026-10-12 更新包含 Odoo 20 的 is_storable/uom_id 判断、始终启用的后端保护、可取消的冻结预留、父级规则、产品例外权限和行为测试。

核查的 OCA stock-logistics-workflow 20.0 提交 fb153396db425e3b20056bee37cf9f583f98f304 与 stock-logistics-warehouse 20.0 提交 7f8f41be39458a953574517560c406beba0784f7 尚无这两个模块目录。本次为本地兼容迁移, 不宣称是 OCA 官方 20 成品。

新模块独立于 blue_stock_base, 库存规则模块按 AGPL-3 交付, 其他模块保留各自原许可。本轮仅执行清单 1、2, 同批次及同作业单上架没有实现或安装。
