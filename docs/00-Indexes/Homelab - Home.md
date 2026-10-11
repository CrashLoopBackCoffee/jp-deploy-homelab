---
tags:
  - homelab
  - index
type: index
status: active
created: 2026-03-20
updated: 2026-10-03
---

# Homelab - Home

## Purpose

Central entry point for the Homelab knowledge base.

## Core indexes

- [[Service Catalog]]
- [[Decision Log]]
- [[Incident Log]]
- [[Architecture Overview]]
- [[Network Overview]]

## Foundation

- [[Environment Facts]]
- [[Addressing and Domains]]
- [[Standards and Conventions]]
- [[Hardware Inventory]]

## Key architecture notes

- [[DNS and DHCP Architecture]]
- [[Network Segmentation]]

## Services

- [[OPNsense]]
- [[WireGuard]]
- [[dnsmasq]]
- [[Unbound]]
- [[AdGuard]]
- [[Proxmox]] (external)
- [[k0s]]
- [[FritzBox]]

## Recent incidents

- [[INC-2026-03-16 - WireGuard floating clients handshake failure]]
- [[INC-2026-03-03 - k0s etcd connection refused]]
- [[INC-2026-03-02 - LXC DHCP VLAN issue]]

## Key decisions

- [[ADR-0001 - Use dnsmasq instead of Kea on OPNsense]]
- [[ADR-0002 - Local domain and addressing baseline]]
- [[ADR-0003 - Pet vs Cattle and IaC tooling]] (superseded)
- [[ADR-0004 - Bare-metal k0s and external infrastructure scope]]
- [[ADR-0005 - Phased bare-metal k0s cluster]]
- [[ADR-0006 - Ubuntu Server 24.04 LTS for k0s nodes]] (proposed)

## Durable knowledge

- [[WireGuard Handshake Diagnostics]]
- [[Linux Bridge VLAN Notes]]
- [[dnsmasq Unbound AdGuard Integration Notes]]
