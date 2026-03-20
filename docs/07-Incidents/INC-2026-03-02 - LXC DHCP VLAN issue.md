---
tags:
  - homelab
  - incident
  - proxmox
  - lxc
  - vlan
  - dhcp
type: incident
status: documented
date: 2026-03-02
severity: medium
---

# INC-2026-03-02 - LXC DHCP VLAN issue

## Summary

LXC networking on Proxmox showed DHCP-related problems that were tied to VLAN configuration on Linux bridge interfaces.

## Evidence captured

- `bridge vlan add dev veth104i0 vid 10 pvid untagged`
- `bridge vlan add dev enp3s0 vid 10`
- `bridge vlan show` confirmed VLAN presence on relevant interfaces
- DHCP broadcasts were observed on VLAN 10

## Durable lesson

Validate bridge VLAN state end-to-end across veth and uplink members before blaming DHCP itself.
