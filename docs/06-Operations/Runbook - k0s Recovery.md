---
tags:
  - homelab
  - runbook
  - k0s
type: runbook
status: draft
created: 2026-03-20
updated: 2026-10-03
---

# Runbook - k0s Recovery

## Goal

Triage local etcd connectivity errors reported by k0s.

This runbook applies to the bare-metal cluster described in [[ADR-0005 - Phased bare-metal k0s cluster]]. The rollout starts with one controller+worker and is explicitly non-HA; two controllers are still not an HA milestone for this plan. The control plane is treated as HA only after three controller/etcd members, a fault-tolerant external API load balancer, and the planned failure tests are complete. k0sctl owns bootstrap and lifecycle operations; Pulumi is used only after the shared kubeconfig is available for platform add-ons and workloads.

## Checks

1. Confirm etcd process availability on the node.
2. Validate listener on `127.0.0.1:2379`.
3. Inspect k0s and etcd logs for startup or corruption errors.
4. Confirm disk, permissions, and certificate state if applicable.
