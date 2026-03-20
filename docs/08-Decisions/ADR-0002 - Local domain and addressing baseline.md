---
tags:
  - homelab
  - adr
  - dns
  - ipam
type: adr
status: accepted
date: 2026-02-22
adr: 2
---

# ADR-0002 - Local domain and addressing baseline

## Status

Accepted

## Context

Stable connectivity and coherent naming materially simplify homelab operations.

## Decision

- Use Telekom business connectivity assumptions as the WAN baseline.
- Treat static IPv4 as a core design feature.
- Use the delegated IPv6 `/56` for structured subnet allocation.
- Use `4jp.de` as the primary domain baseline for locally hosted services.

## Consequences

- DNS, VPN, and ingress design can rely on stable public addressing.
- Internal documentation should evolve toward explicit IPv4 and IPv6 subnet allocation per VLAN.
