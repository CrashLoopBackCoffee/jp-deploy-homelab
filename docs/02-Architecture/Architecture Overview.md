---
tags:
  - homelab
  - architecture
type: architecture
status: active
created: 2026-03-20
updated: 2026-10-03
---

# Architecture Overview

## High-level view

The target compute architecture for this repository is:

- [[OPNsense]] as firewall, router, and network control point
- Three bare-metal k0s nodes, each a controller+worker, introduced in phases: one node first, then two, then three
- One separate Proxmox host for Home Assistant, UniFi, and other VM/LXC workloads; it is not a fourth controller initially
- k0sctl owns k0s bootstrap and lifecycle outside Pulumi; Kubernetes Pulumi manages platform add-ons and workloads after the shared kubeconfig exists
- Treat the control plane as HA only after three controller/etcd members, a fault-tolerant external TCP API load balancer, and failure testing; endpoint design remains open
- Planned per-node storage: SATA SSD for system/k0s/etcd/runtime, optional separate SATA SSD for PostgreSQL local storage, and about 1 TB NVMe for Longhorn; exact inventory is unconfirmed
- Existing Proxmox VMs remain external; a k0s worker VM on Proxmox is an optional later addition
- Immich remains on the QNAP and is not deployed from this repository
- DNS and DHCP services built around [[dnsmasq]], [[Unbound]], and [[AdGuard]]
- [[WireGuard]] for site-to-site and roaming client VPN access

## Design themes observed so far

- Segmented network with VLANs
- Mixed modern and legacy network clients
- Operational preference for simple, understandable components
- Explicit attention to DHCP, DNS, and VPN behavior at the network edge

## Related notes

- [[Environment Facts]] — scale and HA constraints
- [[Network Segmentation]]
- [[DNS and DHCP Architecture]]
- [[Ingress and Remote Access]]
- [[ADR-0005 - Phased bare-metal k0s cluster]]
