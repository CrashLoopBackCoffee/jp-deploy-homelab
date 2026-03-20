---
tags:
  - homelab
  - platform
  - lxc
type: platform
status: draft
created: 2026-03-20
updated: 2026-03-20
---

# LXC Standards

## Network baseline

- Verify VLAN membership on host bridge and container veth.
- Treat DHCP failures as a potential bridge VLAN problem before assuming DHCP server malfunction.
