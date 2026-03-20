---
tags:
  - homelab
  - backlog
type: backlog
status: active
created: 2026-03-20
updated: 2026-03-20
---

# Open Questions

## DNS / DHCP

- What is the cleanest integration pattern between dnsmasq, Unbound, and AdGuard on OPNsense?
- Where should local hostnames be authored and synchronized from?

## Network

- What is the canonical VLAN-to-subnet and IPv6 allocation map? (CoRE sub-structure to be confirmed — see [[VLANs]])
- Sodola API investigation — does it have any programmable interface?
- GS308EPP VLAN trunk details — which VLANs on which ports?
- OPNsense SIP proxy vs FRITZbox direct registration to VoIP provider
- Which switch platform provides the best balance of trust, firmware quality, thermals, port mix, and power draw?
- Where should SFP+ be mandatory, where is RJ45 10G acceptable, and which links should use DAC, fiber, or copper?

## VPN

- What is the final documented root cause for the WireGuard floating client handshake failure?

## Platform

- Proxmox cluster node count and naming convention
- NetBox sync tooling — `netbox-sync` or custom Python script?

## Documentation Gaps

- Full hardware inventory with purchase status
- Service inventory under `4jp.de`
- DNS zone and naming conventions
- Proxmox node inventory
- k0s cluster topology
- Per-service operations runbooks

## Operations Backlog

- Capture recurring troubleshooting commands as runbooks
- Document QNAP 10G module loading workaround (see [[Host Hardware Notes]])
- Document k0s and etcd recovery runbook (partial: see [[Runbook - k0s Recovery]])
