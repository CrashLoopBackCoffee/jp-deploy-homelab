---
tags:
  - homelab
  - index
  - services
type: index
status: active
created: 2026-03-20
updated: 2026-03-20
---

# Service Catalog

| Service | Role | Notes |
| --- | --- | --- |
| [[OPNsense]] | Edge firewall, routing, VPN, DHCP/DNS integration point | Central network control plane |
| [[WireGuard]] | Site-to-site and roaming client VPN | Site-to-site is working; roaming clients had handshake issues |
| [[dnsmasq]] | DHCP and local hostname resolution candidate on OPNsense | Preferred over Kea for current scale |
| [[Unbound]] | Recursive DNS resolver | Candidate integration point with AdGuard |
| [[AdGuard]] | DNS filtering | Open question: placement vs Unbound and dnsmasq |
| [[Proxmox]] | Virtualization platform | LXC and host networking are relevant |
| [[k0s]] | Kubernetes control plane | etcd connectivity issue observed on one node |
| [[FritzBox]] | VoIP and legacy WLAN in one VLAN | Special case in network design |
