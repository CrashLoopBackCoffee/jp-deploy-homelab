---
tags:
  - homelab
  - knowledge
  - dns
  - dhcp
  - adguard
  - unbound
  - dnsmasq
type: knowledge
status: active
created: 2026-03-20
updated: 2026-03-20
---

# dnsmasq Unbound AdGuard Integration Notes

## Key insight

The main challenge is not choosing one component in isolation, but assigning each DNS responsibility cleanly.

## Responsibilities to allocate explicitly

- DHCP authority
- local hostname registration
- recursive resolution
- filtering / blocking
- client-facing resolver addresses

## Current project direction

- dnsmasq is favored for DHCP
- Unbound remains relevant for recursive resolution
- AdGuard remains relevant for filtering
- final composition still requires explicit design
