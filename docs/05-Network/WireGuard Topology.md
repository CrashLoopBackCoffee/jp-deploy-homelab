---
tags:
  - homelab
  - network
  - wireguard
type: network
status: active
created: 2026-03-20
updated: 2026-03-20
---

# WireGuard Topology

## Known topology elements

- Site-to-site tunnel exists and works.
- Floating or roaming clients use a distinct access path and are not yet equivalent operationally to site-to-site peers.

## Design note

Document site-to-site peers and roaming peers separately, including:
- endpoint reachability
- allowed IPs
- NAT expectations
- firewall rules
- DNS reachability after tunnel establishment
