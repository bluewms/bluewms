# BlueWMS

[简体中文](README.md) | [English](README.en.md)

BlueWMS is a modular warehouse extension project built on **Odoo 20 Community Edition**, covering inventory operations, editable putaway policies, and planned integrations with automated warehouse equipment.

This repository contains BlueWMS modules developed or migrated by the project, third-party modules with their original attribution preserved, Docker development configuration, and development documentation. Use Issues to discuss requirements and report problems, and Pull Requests to contribute improvements.

**Project status: active development and migration.** Inventory safeguards and the workflow for editable putaway policies are implemented. WCS, a standalone barcode module, and cloud AI connections are planned. The source code and delivery records define the actual feature scope.

## Current features

- **Inventory foundation**: extensions for storage locations, capacity positions, packages, and related inventory operations.
- **Inventory safeguards**: non-negative stock controls, location freezing, and inbound stock restrictions, including permissions and exception handling.
- **Editable putaway enhancements**: select an enhancement scenario in Odoo's native putaway rules; manually edit drafts, validate them with trial runs, and publish them. Execution auditing, version pinning, and rollback are supported.
- **System settings take precedence**: native rules, storage categories, capacity limits, and stock mixing constraints are checked first. Enhancement code then filters or ranks candidates within those constraints. Whole pallets can be kept intact, and restrictions on the same lot number across different products are supported.
- **UI and AI components**: includes MuK Web, AI, Skills, and MCP modules. Actual model services require separate configuration and validation.

Putaway enhancement code processes plain data through a restricted interpreter rather than exposing unrestricted Python execution. Saving a draft does not publish it automatically. Scenarios, released code versions, and execution records are stored in the Odoo database.

![Enhancement policy fields in a native putaway rule](docs/migrations/images/putaway-rule-binding.png)

*Screenshot from an isolated test database. See [Native putaway rules and enhancement policies](docs/migrations/putaway-rule-binding-20.md) for usage instructions.*

## Modules

All modules reside in subdirectories directly under the repository root and are mounted at `/mnt/extra-addons` in the container.

| Module | Responsibility | Declared license |
|---|---|---|
| `blue_stock_base` | Core inventory extensions | LGPL-3 |
| `blue_stock_rules` | Non-negative stock, location freezing, and inbound restrictions | AGPL-3 |
| `blue_extension_contract` | Policy interface contracts and restricted interpreter | LGPL-3 |
| `blue_config_asset` | Drafts, trial runs, immutable versions, releases, and rollback assets | LGPL-3 |
| `blue_stock_putaway` | Native rule binding and putaway enhancement execution | AGPL-3 |
| `blue_web_theme` | Product, package, and location navigation and inventory UI layout | LGPL-3 |
| `blue_dev_environment` | Development addons directory marker | AGPL-3 |
| `muk_web_*` | Third-party UI components and themes | LGPL-3 |
| `muk_ai`, `muk_ai_skills`, `muk_mcp` | Third-party AI, skills, and MCP integration | LGPL-3 |

Modules prefixed with `blue_*` are maintained by BlueWMS; migrated modules retain attribution to their original contributors. Other prefixes identify third-party modules. MuK modules retain their original names, copyright headers, and licenses. See the [Third-party migration record](docs/third-party/muk-web-migration-2026-10-12.md) and [MuK AI installation record](docs/third-party/muk-ai-install-2026-10-12.md) for sources and versions.

## Quick start

### Requirements

- Docker and Docker Compose.
- Odoo 20 and PostgreSQL 16.0. See the [Deployment record](docker/deployment-lock.json) for the validated baseline and image digests.
- The module source code in this repository. The Docker image supplies Odoo itself; you do not need to copy the official Odoo source into this repository.

The recorded development environment validation used macOS on Apple silicon. Check dependencies and validate actual behavior on other platforms or image architectures.

### 1. Get the source code and images

```sh
git clone https://github.com/bluewms/bluewms.git
cd bluewms
docker pull odoo:20.0-20260926
docker tag odoo:20.0-20260926 odoo:20
docker pull postgres:16.0
```

The dated Odoo tag above matches the current development baseline. Validate image updates in an isolated environment before upgrading the development database. Compose uses locally available images with `pull_policy: never`. See the [Official Odoo Docker image documentation](https://hub.docker.com/_/odoo) for image information.

### 2. Prepare private configuration

```sh
export BLUEWMS_RUNTIME_DIR="$HOME/.config/bluewms20"
mkdir -p "$BLUEWMS_RUNTIME_DIR"
chmod 700 "$BLUEWMS_RUNTIME_DIR"
```

Create two files in this directory:

- `db-password`: a single line containing a strong, unique database password. Compose provides it to PostgreSQL and Odoo as a secret.
- `odoo.conf`: use the minimal configuration below and replace `admin_passwd` with your own strong, unique database management password. Set the Odoo user login password separately when creating the database for the first time.

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

The container entrypoint reads `db_password` from the secret, so this minimal configuration does not store it again. Restrict access to the private files:

```sh
chmod 600 "$BLUEWMS_RUNTIME_DIR/odoo.conf" "$BLUEWMS_RUNTIME_DIR/db-password"
```

This configuration is intended for local development. The repository does not provide shared administrator accounts, default login passwords, or a public business database.

### 3. Start the services and install modules

```sh
docker compose -f docker/compose.yaml up -d
docker compose -f docker/compose.yaml ps
```

Open [Local Odoo](http://localhost:8070). On first use, create a database named `bluewms20` and set your own login credentials. If the entry page reports that the database has not been created, open the [Database manager](http://localhost:8070/web/database/manager).

After logging in, open Apps and install modules such as `blue_stock_base`, `blue_stock_rules`, and `blue_stock_putaway` as needed. Odoo installs dependencies automatically. Remove the default “Apps” filter when searching by technical module name if necessary. Select MuK modules as needed; AI features also require model provider configuration.

If you already have a development database, restore the matching database and filestore backups while retaining the original database name. Do not overwrite it by initializing a new database. The `bluewms20-postgres-data` and `bluewms20-odoo-data` volumes persist the database and attachments, respectively.

See the [Docker development guide](docker/README.md) and [Git synchronization guide](docs/git-sync.md) for upgrades, backups, and working across multiple computers. Keep `BLUEWMS_RUNTIME_DIR` set for subsequent starts, or pass the current user's directory through a private `--env-file`.

## Development and validation

Develop features on separate task branches. Commits should describe the problem, change scope, and validation results. When module structure or data changes, update the relevant module version and run a module upgrade. Restart Odoo after Python changes.

The delivery records dated October 12, 2026 include:

- **120 combined inventory and policy tests**, including **77 putaway tests**. A concurrency test using independent transactions verified that only one operation can successfully allocate the last available pallet position.
- **309 backend/HTTP tests** for the MuK AI modules, plus frontend asset compilation validation. Actual model conversations and cloud business connections still require configuration and validation.

These are recorded development baseline results. See the [Putaway delivery record](docs/migrations/putaway-rule-binding-20.md), [Inventory rules record](docs/migrations/stock-rules-20.md), and [MuK AI record](docs/third-party/muk-ai-install-2026-10-12.md) for test scope, boundaries, source summaries, and execution instructions.

Policy assets, business records, and attachments stored in the database are not synchronized through Git. Git manages module code, templates, deployment instructions, and development documentation.

## Contributing

Bug reports, documentation corrections, and feature suggestions are welcome.

- **Report problems**: open an [Issue](https://github.com/bluewms/bluewms/issues) with Odoo/module versions, reproduction steps, expected and actual behavior, and sanitized logs.
- **Contribute improvements**: open a [Pull Request](https://github.com/bluewms/bluewms/pulls) from a task branch, describing the purpose, impact, and validation. Update relevant documentation for feature changes and verify critical behavior.
- **Development conventions**: follow Odoo ORM, access control, and view conventions for the backend, and the corresponding version's Owl/Web conventions for the frontend. AI-assisted development can refer to the guidelines, review, and security skills in the official Odoo source. Human contributions are equally welcome.
- **Third-party changes**: preserve authorship and licenses, record sources and local modifications, and check compatibility when upgrading third-party modules.

Do not commit real passwords, API keys, customer business data, database backups, or private attachments.

## Planned development

- `blue_wcs_*`: automated equipment interfaces, operation execution, and WCS coordination.
- A standalone barcode module, planned separately from the inventory foundation.
- AI draft generation: connect cloud knowledge/memory services to convert requirements and sample code into verifiable drafts, while retaining local controls for trial runs, publishing, execution, and rollback.
- Continued Odoo 20 migration, testing, and deployment documentation improvements.

See the [Development plan](docs/planning/bluewms20-development-plan.md) and [Module architecture](docs/planning/bluewms20-module-architecture.md) for progress and scope. Planned capabilities are added to “Current features” only after delivery.

## Licenses and attribution

This repository contains **AGPL-3 and LGPL-3 modules**, each with its own license declaration. Refer to each module's `__manifest__.py`, `LICENSE`, and applicable `NOTICE.md` or copyright headers for the governing terms and attribution.

- BlueWMS inventory rules preserve attribution to the relevant OCA/original contributors. See the [Attribution notice](blue_stock_rules/NOTICE.md).
- MuK modules preserve their original MuK IT attribution. See the [Upstream documentation](docs/third-party/MuK-upstream-README.md) and [License text](docs/third-party/MuK-LICENSE).

Odoo itself is a separate upstream project. This repository's module declarations do not replace the licenses of upstream projects or dependencies.

## Maintenance and contact

Maintained by **宁波宝蓝物流科技有限公司 (Ningbo Baolan Logistics Technology Co., Ltd.)**.

Use GitHub Issues and Pull Requests for project discussions. Business inquiries: [bluewms.com](https://www.bluewms.com) · [blue.lang@outlook.com](mailto:blue.lang@outlook.com).
