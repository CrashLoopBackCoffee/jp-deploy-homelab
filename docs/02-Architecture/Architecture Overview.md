---
tags:
  - homelab
  - architecture
type: architecture
status: active
created: 2026-03-20
updated: 2026-03-20
---

# Architecture Overview

## High-level view

The homelab appears to be centered around:

- [[OPNsense]] as firewall, router, and network control point
- [[Proxmox]] as virtualization platform
- [[k0s]] as Kubernetes control plane
- DNS and DHCP services built around [[dnsmasq]], [[Unbound]], and [[AdGuard]]
- [[WireGuard]] for site-to-site and roaming client VPN access

## Design themes observed so far

- Segmented network with VLANs
- Mixed modern and legacy network clients
- Operational preference for simple, understandable components
- Explicit attention to DHCP, DNS, and VPN behavior at the network edge

## Notable constraints

- No HA requirement for the current DHCP design
- Less than 20 VLANs expected
- Fritz!Box dependency for VoIP and legacy clients in one VLAN

## Related notes

- [[Network Segmentation]]
- [[DNS and DHCP Architecture]]
- [[Ingress and Remote Access]]
