---
tags:
  - homelab
  - knowledge
  - linux
  - bridge
  - vlan
type: knowledge
status: active
created: 2026-03-20
updated: 2026-03-20
---

# Linux Bridge VLAN Notes

## Key insight

Container DHCP failure can be caused by incorrect Linux bridge VLAN membership even when the DHCP server itself is healthy.

## Practical checks

- Inspect `bridge vlan show`
- Validate the container veth VLAN membership
- Validate the physical uplink bridge member VLAN membership
- Confirm PVID and untagged expectations match the design

## Example from project history

VLAN 10 had to be explicitly present on both `veth104i0` and `enp3s0`.
