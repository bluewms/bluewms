# BlueWMS

[简体中文](README.md) | [English](README.en.md)

**A modular warehouse management system on Odoo 20 Community Edition, connecting manual operations, PDA workflows, ERP systems and automation.**

The core modules and five AI extension contracts are implemented. Select modules for each deployment and validate customer ERP protocols, equipment and physical scanners separately. Production versions are identified by GitHub Releases.

## Capabilities

| Area | Scope |
|---|---|
| Stock and locations | Companies/warehouses, lots/packages/owners, capacity positions, negative-stock protection, freezing and inbound restrictions |
| Putaway | Filtering/ranking after native admission, receipt and batch-name preferences, pallet integrity and capacity |
| Inventory counting | Dedicated count documents, book snapshots, confirmed counts, native adjustments and ERP/barcode bridges |
| PDA barcode | Four entry points, grouped picking/batch pages, quantity keypad, full QR capture, tracking, packing and backorders |
| ERP | Receipt/delivery/internal-transfer mapping, completion and count-difference events, persistent delivery and reconciliation |
| WCS and equipment | Line decisions, repeat/relay programs, category HTTP/JSON protocols, controlled callbacks and single stock accounting |

Modules are installed independently and combined through bridges. Business records, manual settings and published policies stay in the local instance.

## AI customization

**Describe a requirement → read the asset and approved knowledge → generate a draft → run trials and validation → user review/publication → local execution.**

Five contracts cover putaway `/1` and `/2`, WCS creation `/4`, ERP mapping `/1`, equipment protocol `/1` and barcode policy `/1`. Generated code transforms bounded JSON within the installed contract. Fixed modules enforce permissions, quantities, inventory, authorized equipment, connections and state transitions.

AI saves and validates drafts; users publish them. New models, fields and frontend components require regular module development. Published business rules run locally, without a model request for every warehouse operation. Each instance must have the corresponding module, user connection and approved knowledge before generation is available.

## Getting started

```sh
git clone https://github.com/bluewms/bluewms.git
cd bluewms
```

Prepare private configuration, database passwords and persistent volumes, set `BLUEWMS_RUNTIME_DIR`, then follow the [Docker setup guide](docker/README.md). Default ports are Odoo `8070` and PostgreSQL `5436`. Do not commit credentials.

Addons are top-level directories. Choose modules by dependency; see [module architecture](docs/module-architecture.md) and the [deployment lock](docker/deployment-lock.json). Before upgrades, back up the database and filestore and verify business records, manual settings, code assets and in-flight tasks.

## Documentation

- [Documentation index](docs/README.md): current usage, engineering, testing and operations guides.
- [AI workflow](docs/guides/ai.md): contracts, assets, shared Tasks and user publication.
- [Generation knowledge](docs/wiki/README.md): the canonical specifications, complete contracts and accurate examples.
- [Cloud publication status](docs/wiki-publication/README.md): actual versions and read-back evidence; Git merges do not publish knowledge.
- [Upgrades](docs/operations/upgrades.md), [Git workflow](docs/git-sync.md) and [validation](docs/testing/README.md).

Production Odoo archives exclude `docs/`; cloud services are deployed separately. Git retains project history. Addon versions and product release tags are managed separately.

## Contributing and licensing

Use [Issues](https://github.com/bluewms/bluewms/issues) and pull requests, merged to main with squash. Include purpose, impact and validation. Keep credentials, customer records and backups outside Git.

The repository contains AGPL-3 and LGPL-3 modules. Each module's manifest, LICENSE and copyright notices govern its license. Third-party components retain their original terms; see [dependencies](docs/third-party/README.md).

Maintained by 宁波宝蓝物流科技有限公司. [bluewms.com](https://www.bluewms.com) · [blue.lang@outlook.com](mailto:blue.lang@outlook.com).
