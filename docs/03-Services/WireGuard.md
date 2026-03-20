---
tags:
  - homelab
  - service
  - wireguard
type: service
status: active
created: 2026-03-20
updated: 2026-03-20
---

# WireGuard

## Purpose

VPN transport for site-to-site and roaming or floating clients.

## Current state

- Site-to-site tunnel is confirmed working.
- Floating clients have experienced handshake failures.

## Key lesson

A healthy site-to-site tunnel does not prove that client roaming configuration, peer selection, firewall policy, NAT, or endpoint reachability for floating clients is correct.

## Operational symptom seen

Kernel log excerpts showed repeated handshake initiation and handshake timeout / retry behavior.

## Related notes

- [[INC-2026-03-16 - WireGuard floating clients handshake failure]]
- [[WireGuard Handshake Diagnostics]]
- [[WireGuard Topology]]
