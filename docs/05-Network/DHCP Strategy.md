---
tags:
  - homelab
  - network
  - dhcp
type: network
status: active
created: 2026-03-20
updated: 2026-03-20
---

# DHCP Strategy

## Current direction

- Move away from deprecated ISC DHCP on OPNsense.
- Prefer dnsmasq over Kea for current needs.

## Why

- No HA requirement
- Modest VLAN count
- Preference for simpler operational model
