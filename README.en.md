# BlueWMS

[简体中文](README.md) | [English](README.en.md)

**A modular warehouse management system built on Odoo 20 Community Edition, with AI-driven self-service customization.**

BlueWMS carries forward an established warehouse management project, migrating and upgrading its warehouse workflows, inventory management and automation integration experience. It combines the Odoo platform with cloud AI capabilities for manual, automated and hybrid warehouse operations.

This overview describes the WMS product and its intended capabilities after migration. The first production release following migration is planned to use the **`V2.0.0`** tag.

## Connected warehouse operations

BlueWMS connects warehouse workflows, barcode operations, inventory policies and equipment execution into an end-to-end process.

| Area | Product capabilities |
|---|---|
| Receiving and putaway | Receiving, lot and package management, receipt confirmation, location recommendations and putaway execution |
| Shipping and transfers | Stock reservations, picking, shipping, internal transfers and whole-pallet movements |
| Inventory and counting | Multiple warehouses and companies, stock visibility, inventory counts and adjustments, and lot traceability |
| Locations and carriers | Warehouse zones and locations, capacity management, pallets, nested packages and empty carriers |
| Barcodes and handhelds | Barcode and PDA workflows for receiving, putaway, picking, transfers and inventory counts |
| Inventory policies | Putaway filtering and ranking, receipt and lot consolidation, intact pallets and stock mixing constraints |
| Inventory controls | Non-negative stock, location freezing, inbound restrictions, capacity limits and permission-based exceptions |
| WCS and automation | Equipment task generation, queued dispatch, execution callbacks, task dependencies, two-leg relays and exception reconciliation |
| ERP and external systems | Master data and business document mapping, interface exchange, status feedback and project integrations |

Manual operations and equipment tasks share inventory rules and business records, linking quantities, lots, locations and execution status. Modules can be selected for each operation, allowing a manual warehouse to grow into coordinated automation.

## AI-driven self-service customization

Users describe their requirements in natural language. AI uses cloud knowledge, approved examples and project context to generate, modify and validate business enhancement code autonomously. Users can customize workflows from business pages without maintaining a separate customer branch for every rule adjustment.

Customization covers five business entry points:

- **Putaway policies**: adjust candidate locations, ranking, receipt consolidation and lot consolidation.
- **ERP interfaces**: adjust business field mappings, data transformations and document handling rules.
- **WCS generation policies**: adjust task creation conditions, equipment selection, endpoints and task dependencies.
- **Equipment interfaces**: adjust protocol mappings and business handling within the supplied equipment adapters.
- **Barcode policies**: adjust scanning sequences, validation requirements and workflow steps.

For example, a user can request “Keep goods from the same receipt together and preserve whole pallets” or “Start the second device only after the first leg is complete.” AI reads the relevant interface specification and existing configuration, generates code for the scenario and revises the draft using validation feedback.

The customization workflow is: **describe the requirement → read knowledge and existing configuration → generate or revise a draft → run trials and validation → user review and publication → local business execution**.

The current development version supports the putaway AI draft workflow: read approved cloud examples and the installed local contract, generate a draft, run validation, and let the user publish it. The AI button opens a larger floating chat on the existing business page, with enlarge and restore controls. The ERP, WCS, equipment and barcode AI entry points are being developed against their own contracts and validation requirements.

Code and configuration are managed as database assets, with version history, change review, execution tracing and rollback. A change to one entry point preserves other configurations; coordinated changes check their relationships. Generated code operates within exposed interfaces, user permissions and system inventory rules. New models, fields and frontend components are delivered through regular modules.

## Cloud knowledge, local execution

- **Cloud customization services**: models, knowledge, Skills and project memory provide context for code generation. Users connect through their own API keys and Agents.
- **Locally managed production assets**: the customer instance stores business data, published code versions, configuration and execution records. Drafts take effect after validation and user publication.
- **Warehouse execution independent of generation services**: published rules run locally, and routine inventory operations do not require a model call for each action. Cloud connections support AI customization and knowledge services.
- **Modular business boundaries**: inventory, barcodes, WCS, ERP, AI and the product interface are combined through separate modules. Third-party components retain their original attribution.

## Deployment and use

BlueWMS is delivered as Odoo addons for Odoo 20 Community Edition and PostgreSQL, with Docker deployment support. Modules reside in top-level subdirectories of this repository and are installed by Odoo according to their dependencies.

```sh
git clone https://github.com/bluewms/bluewms.git
cd bluewms
```

Before starting, prepare a private `odoo.conf`, database password and persistent storage, and set `BLUEWMS_RUNTIME_DIR` to the private configuration directory. Setup steps follow below; see the [Docker deployment guide](docker/README.md) and [deployment version manifest](docker/deployment-lock.json) for image versions, maintenance commands and backup procedures.

Core warehouse operations use the selected business modules. To enable AI customization, configure the cloud service, user API key and Agent separately. Business configuration and database assets follow their own backup and recovery procedures; Git manages module source code and documentation.

### Docker configuration

```sh
export BLUEWMS_RUNTIME_DIR="$HOME/.config/bluewms20"
mkdir -p "$BLUEWMS_RUNTIME_DIR"
chmod 700 "$BLUEWMS_RUNTIME_DIR"
```

Create a `db-password` file in that directory containing one line with a strong, unique database password. Create `odoo.conf` and replace the database management password below with your own strong, unique password:

```ini
[options]
admin_passwd = REPLACE_WITH_YOUR_OWN_STRONG_DATABASE_MANAGEMENT_PASSWORD
db_host = db
db_port = 5432
db_user = odoo
db_name = bluewms20
dbfilter = ^bluewms20$
list_db = True
addons_path = /usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons
data_dir = /var/lib/odoo
```

The container entrypoint reads the database password from the secret. Restrict configuration file permissions, prepare the local `odoo:20` and `postgres:16.0` images according to the deployment manifest, and start the services:

```sh
chmod 600 "$BLUEWMS_RUNTIME_DIR/odoo.conf" "$BLUEWMS_RUNTIME_DIR/db-password"
docker compose -f docker/compose.yaml up -d
docker compose -f docker/compose.yaml ps
```

Open the [local Odoo database manager](http://localhost:8070/web/database/manager). For a new deployment, create the `bluewms20` database and your own login credentials, then install the business modules you need. For an existing instance, restore matching database and filestore backups, and back up before upgrading.

## Releases and versioning

This project migrates and upgrades an established product. After migration, **`V2.0.0`** is planned as the first production release tag for the new product line.

Subsequent product tags follow `Vmajor.minor.patch`, such as `V2.1.0` and `V2.0.1`, to distinguish capability additions from compatible fixes. Product release tags are managed separately from Odoo addon versions in the `20.0.x.x.x` format.

Production releases are published through [GitHub Releases](https://github.com/bluewms/bluewms/releases), with release notes, installation and upgrade instructions, and applicable deployment requirements.

## Documentation and contributions

- [Documentation index](docs/README.md): business guides, architecture and engineering documentation.
- [Odoo AI code-generation knowledge](docs/wiki/README.md): generation rules, interface specifications and examples for the assistant inside Odoo.
- [Putaway AI floating chat](docs/migrations/putaway-ai-floating-chat-20.md): usage and validation of the chat that preserves the business page.
- [Git collaboration guide](docs/git-sync.md): source synchronization and branch workflows.
- [Issues](https://github.com/bluewms/bluewms/issues): report problems with reproduction steps, expected behavior and sanitized logs.
- [Pull requests](https://github.com/bluewms/bluewms/pulls): contribute code, integrations, examples and documentation.

Submit changes from a task branch through a pull request and squash merge into `main`. Describe the purpose, impact and validation of each change, and preserve third-party sources and copyright notices. Keep real passwords, API keys, customer business data, database backups and private attachments out of the source repository.

## Licenses and attribution

This repository contains **AGPL-3 and LGPL-3 modules**. Each module's `__manifest__.py`, `LICENSE`, `NOTICE.md` and copyright headers define its applicable terms and attribution. Migration or renaming does not change the original code's license or contributor attribution.

See the inventory rules [attribution notice](blue_stock_rules/NOTICE.md), the MuK [upstream documentation](docs/third-party/MuK-upstream-README.md) and [license text](docs/third-party/MuK-LICENSE). Odoo and other dependencies remain subject to their own licenses.

## Maintenance and contact

Maintained by **宁波宝蓝物流科技有限公司 (Ningbo Baolan Logistics Technology Co., Ltd.)**.

Use GitHub Issues and pull requests for project discussions. Business inquiries: [bluewms.com](https://www.bluewms.com) · [blue.lang@outlook.com](mailto:blue.lang@outlook.com).
