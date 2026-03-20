---
tags:
  - homelab
  - runbook
  - k0s
type: runbook
status: draft
created: 2026-03-20
updated: 2026-03-20
---

# Runbook - k0s Recovery

## Goal

Triage local etcd connectivity errors reported by k0s.

## Checks

1. Confirm etcd process availability on the node.
2. Validate listener on `127.0.0.1:2379`.
3. Inspect k0s and etcd logs for startup or corruption errors.
4. Confirm disk, permissions, and certificate state if applicable.
