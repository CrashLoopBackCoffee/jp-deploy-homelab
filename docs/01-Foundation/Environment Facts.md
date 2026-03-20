---
tags:
  - homelab
  - foundation
type: foundation
status: active
created: 2026-03-20
updated: 2026-03-20
---

# Environment Facts

## Connectivity baseline

- ISP is Telekom business.
- WAN connectivity includes a static IPv4 address.
- IPv6 delegation is a `/56` prefix.

## Domain baseline

- Domain `4jp.de` is used for locally hosted and self-hosted services.

## Scale and operating assumptions

- No HA setup is currently assumed for OPNsense DHCP.
- VLAN count is expected to stay below 20.
- One VLAN contains a Fritz!Box for VoIP and some legacy WLAN clients.

## Tooling preferences relevant to the homelab

- Open-source solutions are preferred first.
- Primary working environment is centered around Python, AWS, Hetzner, macOS, VS Code, and Obsidian.
