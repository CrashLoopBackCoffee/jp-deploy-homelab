---
okf_version: "0.1"
---

# Repository Review

* [Current state versus adjacent donor repositories](current-state-vs-donors.md) - Donor comparison plus bare-metal k0s placement, external service boundaries, and current verification.
* [Phased bare-metal k0s cluster plan](k0s-cluster-plan.md) - expansion-compatible three-node target, HA gates, storage intent, and the accepted Ubuntu host OS.
* [k0s0 (Node 1)](k0s0-node.md) - identity, access accounts, disks and their roles, and the preparation done outside Pulumi.
* [Kubernetes platform stack](kubernetes-platform-stack.md) - add-ons deployed by the prod Pulumi stack, configuration mapping, secrets flow, and local DNS.
* [PostgreSQL pilot recovery](postgres-pilot-recovery.md) - QuObjects Barman backup settings, WAL recovery evidence, and safe follow-up operations.
* [Observability stack](observability-stack.md) - LGTM on k0s, Grafana at g.4jp.de, Pushover alert routing, verification evidence, and metric and provisioning pitfalls.
* [NetBox](netbox.md) - migration of the NetBox inventory from dockerhost to k0s: discovery results, official chart, CloudNativePG database, import with the 4.2 to 4.7 upgrade, cutover runbook and verification (ADR-0030).
* [Paperless](paperless.md) - fresh-install Paperless on k0s (prepared, not deployed): CloudNativePG database, restic to an off-site Nextcloud, QNAP intake, prerequisites and the go-live gate runbook.
* [Retiring the legacy dockerhost monitoring stack](legacy-monitoring-migration.md) - inventory of the old Ansible-managed Prometheus, Grafana and Loki, mapping to the k0s stack, findings, the network gate, the Mimir backfill constraints and the gated plan (ADR-0023).
* [Tandoor](tandoor.md) - migration of Tandoor Recipes from dockerhost: CloudNativePG database, Longhorn media volume, prerequisites, import and cutover runbook, and the 2.7.1 metrics-auth incident and decision (ADR-0028, ADR-0034).
* [Services on dockerhost](dockerhost-services.md) - what runs on the unbacked-up host dockerhost, why moving a service to k0s already improves its protection, and the migration status per service.
* [Operational lessons](operational-lessons.md) - pitfalls from the first rollout with the rule for each, plus suggested standing agent instructions.
* [Wazuh security monitoring (planned)](wazuh.md) - architecture, upstream 4.14.9 facts and pitfalls, LGTM integration contracts and phased plan (ADR-0037).
