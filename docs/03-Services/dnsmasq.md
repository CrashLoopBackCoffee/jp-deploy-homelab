---
tags:
  - homelab
  - service
  - dnsmasq
type: service
status: planned
created: 2026-03-20
updated: 2026-03-20
---

# dnsmasq

## Purpose

Candidate DHCP service on OPNsense after ISC DHCP deprecation, with optional support for local hostname handling.

## Why it matters here

- Fits the current expected scale.
- No HA requirement is present.
- Simplicity is preferred over feature surplus.

## Current decision status

dnsmasq is the preferred direction over Kea for this homelab.

## Open question

Exact integration with [[Unbound]] and [[AdGuard]] still needs final architecture definition.
