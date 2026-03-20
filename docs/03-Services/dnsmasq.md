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

## Current decision status

dnsmasq is the accepted direction. See [[ADR-0001 - Use dnsmasq instead of Kea on OPNsense]].

## Open question

Exact integration with [[Unbound]] and [[AdGuard]] still needs final architecture definition. See [[dnsmasq Unbound AdGuard Integration Notes]].
