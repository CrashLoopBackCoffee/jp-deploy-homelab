---
okf_version: "0.1"
---

# Repository Review

* [Current state versus adjacent donor repositories](current-state-vs-donors.md) - Donor comparison plus bare-metal k0s placement, external service boundaries, and current verification.
* [Phased bare-metal k0s cluster plan](k0s-cluster-plan.md) - expansion-compatible three-node target, HA gates, storage intent, and the accepted Ubuntu host OS.
* [k0s0 (Node 1)](k0s0-node.md) - identity, access accounts, disks and their roles, and the preparation done outside Pulumi.
* [Kubernetes platform stack](kubernetes-platform-stack.md) - add-ons deployed by the prod Pulumi stack, configuration mapping, secrets flow, and local DNS.
* [PostgreSQL pilot recovery](postgres-pilot-recovery.md) - QuObjects Barman backup settings, WAL recovery evidence, and safe follow-up operations.
* [Operational lessons](operational-lessons.md) - pitfalls from the first rollout with the rule for each, plus suggested standing agent instructions.
