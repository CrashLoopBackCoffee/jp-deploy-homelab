---
tags:
  - homelab
  - platform
  - proxmox
type: platform
status: external
created: 2026-03-20
updated: 2026-10-03
---

# Proxmox Platform

> These findings apply to existing external Proxmox systems. Proxmox management is no longer part of this repository.

## Relevant findings

- Linux bridge VLAN behavior is critical for container connectivity.
- Container-facing veth interfaces require correct VLAN membership and tagging behavior.
- Physical bridge members also need the expected VLANs present.

## Related notes

- [[INC-2026-03-02 - LXC DHCP VLAN issue]]
- [[Linux Bridge VLAN Notes]]
