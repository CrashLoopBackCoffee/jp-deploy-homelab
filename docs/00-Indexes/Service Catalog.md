---
tags:
  - homelab
  - index
  - services
type: index
status: active
created: 2026-03-20
updated: 2026-10-03
---

# Service Catalog

| Service | Role | Notes |
| --- | --- | --- |
| [[OPNsense]] | Edge firewall, routing, VPN, DHCP/DNS integration point | Central network control plane |
| [[WireGuard]] | Site-to-site and roaming client VPN | Site-to-site is working; roaming clients had handshake issues |
| [[dnsmasq]] | DHCP and local hostname resolution candidate on OPNsense | Preferred over Kea for current scale |
| [[Unbound]] | Recursive DNS resolver | Candidate integration point with AdGuard |
| [[AdGuard]] | DNS filtering | Open question: placement vs Unbound and dnsmasq |
| [[Proxmox]] | Existing virtualization platform | External to this repository; existing VMs remain unmanaged here |
| [[k0s]] | Kubernetes control plane and workloads | Three bare-metal controller+workers planned in phases; bootstrap with k0sctl; see ADR-0005 |
| [[FritzBox]] | VoIP and legacy WLAN in one VLAN | Special case in network design |
| [[Wazuh Security Monitoring]] | Software inventory, vulnerability management, security events | Planned on k0s (namespace wazuh); not deployed. See [[Wazuh Implementation Plan]] |
