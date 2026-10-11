---
tags:
  - homelab
  - adr
  - kubernetes
  - network
type: adr
status: accepted
date: 2026-10-10
created: 2026-10-10
updated: 2026-10-10
adr: 8
---

# ADR-0008 - Phase 1 k0s API endpoint

## Status

Accepted on 2026-10-10 for Phase 1. Revisit before adding a second controller.

## Context

[[ADR-0005 - Phased bare-metal k0s cluster]] requires a stable `spec.api.externalAddress` for control-plane HA. Node 1 (`k0s0`) is `10.10.8.1/16` on VLAN 10 with a static DHCP mapping in OPNsense. No load balancer or VIP exists yet.

## Decision

- For Phase 1, `spec.api.externalAddress` and the API certificate SANs are `10.10.8.1`, the address of `k0s0`.
- The address is stable because it is a static DHCP mapping in OPNsense. The node itself stays on DHCP.
- The k0sctl configuration lives in `services/k0s/k0sctl/cluster.yaml`.

## Consequences

- Phase 1 is non-HA; a single-address endpoint is acceptable.
- Before Phase 3, introduce a fault-tolerant TCP load balancer and VIP (ports 6443, 8132, 9443), set it as `externalAddress`, and regenerate API certificates and kubeconfigs. Everything that stored the Phase 1 kubeconfig, including the shared 1Password item used by the Kubernetes Pulumi stack, must be refreshed.
- If the OPNsense mapping is removed or the address changes, the cluster API and certificates break.

## Related notes

- [[ADR-0005 - Phased bare-metal k0s cluster]]
- [[ADR-0007 - Dedicated k0sctl automation account]]
- [[k0s]]
