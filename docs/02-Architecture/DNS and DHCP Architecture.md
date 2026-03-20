---
tags:
  - homelab
  - architecture
  - dns
  - dhcp
type: architecture
status: draft
created: 2026-03-20
updated: 2026-03-20
---

# DNS and DHCP Architecture

## Current understanding

OPNsense is the key control point. The main design question has been how to combine:

- [[dnsmasq]] for DHCP and optionally local hostname handling
- [[Unbound]] for recursive DNS
- [[AdGuard]] for filtering

## Recorded decision

[[dnsmasq]] is accepted over Kea for DHCP on OPNsense. See [[ADR-0001 - Use dnsmasq instead of Kea on OPNsense]].

## Open architecture question

The unresolved design question is how to integrate AdGuard, dnsmasq, and Unbound cleanly, or whether Unbound can cover enough ground to reduce reliance on AdGuard in some paths.

## Working assumptions

- Local hostnames are useful but can still be managed manually where needed.
- DNS and DHCP choice is mostly independent from the Fritz!Box VLAN exception.
- Complexity should be introduced only when it produces clear operational benefit.
