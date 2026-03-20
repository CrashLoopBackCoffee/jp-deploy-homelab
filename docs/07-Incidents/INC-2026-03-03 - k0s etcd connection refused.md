---
tags:
  - homelab
  - incident
  - k0s
  - etcd
type: incident
status: documented
date: 2026-03-03
severity: high
---

# INC-2026-03-03 - k0s etcd connection refused

## Summary

k0s reported gRPC transport failures while dialing `127.0.0.1:2379`.

## Symptoms

Error pattern included:

- connection refused to local etcd endpoint
- failure to establish transport for local control plane dependency

## Likely fault domain

- etcd not running
- etcd not listening on expected interface
- local startup or state failure

## Durable lesson

When k0s fails on the loopback etcd endpoint, start with local node health, not network path assumptions.
