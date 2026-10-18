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
* [Paperless](paperless.md) - fresh-install Paperless on k0s (prepared, not deployed): CloudNativePG database, restic to an off-site Nextcloud, QNAP intake, prerequisites and the go-live gate runbook.
* [Retiring the legacy dockerhost monitoring stack](legacy-monitoring-migration.md) - inventory of the old Ansible-managed Prometheus, Grafana and Loki, mapping to the k0s stack, findings, the network gate, the Mimir backfill constraints and the gated plan (ADR-0023).
* [Tandoor](tandoor.md) - migration of Tandoor Recipes from dockerhost: CloudNativePG database, restic to the off-site Nextcloud, prerequisites, and the import and cutover runbook (ADR-0028).
* [Operational lessons](operational-lessons.md) - pitfalls from the first rollout with the rule for each, plus suggested standing agent instructions.
