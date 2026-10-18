# Native Wiki read-only gateway

This directory contains separately deployed cloud service sources and deployment material. It is not an Odoo addon. It remains in the development Git repository under `docs/cloud/`; production Odoo release archives exclude `docs/`.

This gateway forwards authenticated Odoo requests to TencentDB-Agent-Memory's standard `tools/list` and `tools/call` APIs. Tencent performs BM25 search and full-page reads. There is no local example library, Skill dependency, reindexer or arbitrary URL forwarding here.

Use the existing HTTPS model origin. Deploy `native_wiki_gateway.py` with Python 3.9+, adapt the service unit, and include `nginx-native-wiki.conf` inside that origin's HTTPS server. The process listens only on loopback port 8430. Keep deployment configuration and its service credential outside Git, readable only by the dedicated service account. The Odoo client continues to use its existing business user Key.

Copy `native-wiki-config.example.json` to the private service configuration and supply actual tenant, team and six Wiki IDs. Core and Knowledge endpoints must be fixed loopback services. The service credential belongs only on the cloud host; never copy it into Odoo, browser settings or model prompts.

The six target assets must contain the reviewed publication metadata: purpose `odoo_runtime_code_generation`, logical scope, Wiki version, contract list, generation approval, source commit and an `approved_pages` list with exact page digests. Candidate ERP/device/barcode knowledge may be read for discussion without an execution contract. Generating a draft requires approved knowledge and the current implemented contract.

Each configured business user needs five running Tasks with the exact names in `TASK_NAMES`, owned by that user and linked to their Agent. Identity resolution validates ownership and association, returns the actual IDs, and the Odoo model request supplies the proxy's standard `x-team-id`, `x-agent-id` and `x-task-id` preset headers. It fails rather than selecting the ordinary daily Task.

The HTTPS interface is limited to `identity`, `context`, `search`, `read` and `verify` under `/odoo-wiki/v1/`. It checks the business credential, Agent ownership, fixed resource bindings, current Core ACL, readiness, approval and contract before forwarding. Full-page reads check the approved digest and Wiki version before and after. Verification requires common guidance, the domain specification and a relevant example. Unknown identities, endpoints, domains and operations are rejected.

Before deployment, back up affected service/reverse-proxy files and metadata. Validate the proxy configuration, then reload it. Updating gateway code requires restarting this service; vendor containers are unchanged. For rollback, restore the previous reviewed gateway release and private configuration. Old Skill assets may remain available for older clients; this gateway never uses them as fallback.

From the repository root, run gateway checks with `python3 -m unittest discover -s docs/cloud/tests`. Odoo integration tests live in `blue_ai_client/tests`; run them in an isolated database with a matching dbfilter. Deployment and real Task-routing evidence are recorded in [the runtime guide](../migrations/native-wiki-runtime-20.md).
