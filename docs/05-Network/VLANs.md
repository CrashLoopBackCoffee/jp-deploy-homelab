---
tags:
  - homelab
  - network
  - vlan
type: network
status: active
created: 2026-03-20
updated: 2026-10-03
---

# VLANs

## Design Principle

VLAN-based segmentation with OPNsense as the L3 boundary. Core routing and policy remain in OPNsense; VLAN boundaries are explicit; legacy dependencies stay isolated.

> Domain and addressing baseline: see [[Addressing and Domains]]

## VLAN Schema

> Pattern: `VLAN x0 → 10.x0.0.0/16` — consistent and memorable

```yaml
vlans:
  - id: 1
    name: management
    subnet: 10.1.0.0/16
    notes: Switches

  - id: 10
    name: CoRE
    description: Servers and infrastructure
    subnet: 10.10.0.0/16
    notes: Existing external Proxmox, QNAP; bare-metal k0s nodes (k0s0 at 10.10.8.1)

  - id: 20
    name: PeRS
    description: Personal end devices
    subnet: 10.20.0.0/16

  - id: 30
    name: HoME
    description: Home automation
    subnet: 10.30.0.0/16

  - id: 40
    name: GaST
    description: Guest network, isolated
    subnet: 10.40.0.0/16

  - id: 50
    name: VoIP
    description: FRITZbox SIP only
    subnet: 10.50.0.0/16
    notes: Activate when FRITZbox is demoted
```

## CoRE Sub-structure (proposed, to be confirmed)

```text
10.10.0.0/24   → network infrastructure (OPNsense, switches)
10.10.1.0/24   → Proxmox hosts
10.10.2.0/24   → VMs — static assignments
10.10.10.0/24  → VMs — DHCP pool
10.10.20.0/24  → QNAP + storage
```

The proposed Proxmox and VM subnets remain unconfirmed and external to this repository. The first bare-metal k0s node, `k0s0`, uses `10.10.8.1/16` on VLAN 10; its gateway and the sub-range reserved for k0s nodes are not yet recorded, and there is no DNS record for it.

## Migration Plan

| Phase | Action | Status |
|---|---|---|
| **0** | Canonize VLAN schema in git | 🔲 Todo |
| **1** | Replicate clean VLANs onto Sodola core + JGS524Ev2 | 🔲 Todo |
| **2** | Migrate PoE clients JGS524Ev2 → USW Pro 24 | 🔲 Todo |
| **3** | Move non-PoE clients to clean JGS524Ev2 VLANs | 🔲 Todo |
| **4** | Demote FRITZbox to VoIP only, activate VoIP VLAN | 🔲 Todo |
| **5** | Decommission legacy VLAN 1 | 🔲 Todo |

## Related

- [[Network Segmentation]]
- [[ADR-0003 - Pet vs Cattle and IaC tooling]]
- [[Hardware Inventory]]
