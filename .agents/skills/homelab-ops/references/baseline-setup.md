# Baseline Setup

Last updated from repository notes on 2026-02-24.

## Authority and Freshness

- This file is planning/supporting context only.
- NetBox is authoritative for current inventory, topology, VLANs, IPs, and prefixes.
- Before executing risky changes, confirm current runtime state in NetBox.

## Goals

- Managed VLAN-capable homelab with a 10G core.
- Segment IoT/home-automation devices from servers and clients.
- Keep guest Wi-Fi isolated.

## Core Components

### Firewall / Router

- Platform: MNBOXCONET N305 SFP DIY
- OS: OPNsense
- Role: Inter-VLAN routing, gateway
- Interfaces: 2x 10G SFP+, 2x 2.5G RJ45

### Core Switch

- Model: SL-SWTGW2C48NS
- Ports: 8x 10G SFP+, 4x 10G RJ45
- Features: VLAN, LACP, QoS, SNMP

### Access Switch

- Model: USW Pro 24 PoE
- Role: rack access and PoE distribution

### Storage / Compute Highlights

- NAS: QNAP TS-673A-8G, with 10Gtek 10GbE PCIE Netzwerkkarte für Intel X520-DA1
- DeskMini X300 nodes (3x): mixed roles including Proxmox and legacy Docker
- Endpoints include MacBook M1 and Windows workstation

## Current High-Level Architecture Direction

- 10G SFP+ core as central fabric.
- OPNsense handles L3 routing between VLANs.
- Optional desk-side aggregation switch.

## Open Decisions to Track During Ops

- Final desk topology (single core vs core + desk aggregation).
- Standard for office-basement interconnect (DAC vs fiber).
- Final MacBook 10G attachment path (TB->SFP+ preferred baseline).
