---
tags:
  - homelab
  - service
  - k0s
  - kubernetes
type: service
status: active
created: 2026-03-20
updated: 2026-03-20
---

# k0s

## Purpose

Kubernetes distribution used for the control plane in the homelab.

## Observed issue

One reported error path showed gRPC transport failures to `127.0.0.1:2379` with `connection refused`, indicating local etcd reachability or service availability problems.

## Incident links

- [[INC-2026-03-03 - k0s etcd connection refused]]
