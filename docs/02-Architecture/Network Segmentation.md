---
tags:
  - homelab
  - architecture
  - network
  - vlan
type: architecture
status: active
created: 2026-03-20
updated: 2026-03-20
---

# Network Segmentation

## Known design characteristics

- VLAN-based segmentation is in use.
- Expected scale is below 20 VLANs.
- At least one VLAN contains a Fritz!Box for VoIP and legacy WLAN clients.
- Proxmox host networking and Linux bridge VLAN handling are operationally relevant.

## Architectural implications

- DHCP and DNS behavior must be validated per VLAN.
- Special-purpose VLANs with appliances such as a Fritz!Box should be documented as exceptions, not treated as generic client segments.
- LXC connectivity depends on correct bridge VLAN membership on both physical and virtual interfaces.

## Current Topology

```text
OPNsense
    │ (10G)
SL-SWTGW2C48NS (Sodola) ← Core
    ├── (10G) USW Pro 24 PoE
    │           └── WLAN APs
    │
    ├── JGS524Ev2 (Netgear) ← fragmented VLANs, migration source
    │           └── trunk → GS108Ev3 (1st floor)
    │                   ├── VLAN 1   legacy (FRITZbox + legacy clients)
    │                   ├── VLAN 10  CoRE → Proxmox
    │                   ├── VLAN 20  PeRS
    │                   ├── VLAN 30  HoME
    │                   └── VLAN 40  GaST
    │
    └── GS308EPP (1st floor PoE, trunk link)
```

## Target Topology

```text
OPNsense
    │ (10G)
SL-SWTGW2C48NS (Sodola) ← Core
    ├── (10G) USW Pro 24 PoE
    │           └── all PoE clients (APs, PoE devices)
    │
    ├── JGS524Ev2
    │           └── all non-PoE clients (clean VLANs)
    │
    └── FRITZbox (SIP/VoIP only — no routing, no NAT, no DHCP)
```

## Related notes

- [[VLANs]]
- [[Hardware Inventory]]
- [[Linux Bridge VLAN Notes]]
- [[INC-2026-03-02 - LXC DHCP VLAN issue]]
