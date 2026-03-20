---
tags:
  - homelab
  - adr
  - dnsmasq
  - kea
  - opnsense
type: adr
status: accepted
date: 2026-02-22
adr: 1
---

# ADR-0001 - Use dnsmasq instead of Kea on OPNsense

## Status

Accepted

## Context

ISC DHCP on OPNsense was deprecated. The replacement options considered were Kea and dnsmasq.

The environment characteristics are:

- no HA requirement
- fewer than 20 VLANs expected
- preference for simpler operations
- local hostnames are useful, but manual management is acceptable

## Decision

Prefer dnsmasq over Kea for the current homelab.

## Consequences

- Lower operational complexity
- Good fit for current scale
- Architecture effort can focus on integration with Unbound and AdGuard rather than on Kea-specific features

## Alternatives considered

- Kea: more feature-rich, but not currently justified by scale or HA requirements
