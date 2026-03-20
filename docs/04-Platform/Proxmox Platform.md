---
tags:
  - homelab
  - platform
  - proxmox
type: platform
status: active
created: 2026-03-20
updated: 2026-03-20
---

# Proxmox Platform

## Relevant findings

- Linux bridge VLAN behavior is critical for container connectivity.
- Container-facing veth interfaces require correct VLAN membership and tagging behavior.
- Physical bridge members also need the expected VLANs present.

## Related notes

- [[INC-2026-03-02 - LXC DHCP VLAN issue]]
- [[Linux Bridge VLAN Notes]]
