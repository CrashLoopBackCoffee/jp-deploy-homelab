---
tags:
  - homelab
  - hardware
  - inventory
type: foundation
status: active
created: 2026-03-20
updated: 2026-10-03
---

# Hardware Inventory

## Deployed Network Hardware

| Device | Role | IaC Strategy |
| --- | --- | --- |
| OPNsense (N305, 2x 10G SFP+) | Firewall / Router | Ansible (pet) |
| Sodola SL-SWTGW2C48NS | 10G core switch | Documented YAML (pet) |
| USW Pro 24 PoE | PoE / WLAN / migration target | Ansible (pet) |
| JGS524Ev2 (Netgear) | Non-PoE clients (target state) | Documented YAML (pet) |
| GS108Ev3 (Netgear) | 1st floor VLAN switch | Documented YAML (pet) |
| GS308EPP (Netgear) | 1st floor PoE | Documented YAML (pet) |
| FRITZbox | VoIP/SIP only (target state) | Documented YAML (pet) |

> IaC tooling rationale: see [[ADR-0003 - Pet vs Cattle and IaC tooling]]

## Deployed Compute / Storage

| Device | Role | Notes |
| --- | --- | --- |
| Four Ryzen-based systems (planned allocation) | Compute / virtualization | Intended allocation: three bare-metal k0s controller+workers plus one separate Proxmox host for Home Assistant, UniFi, and other VM/LXC workloads. Typical memory is 16–32 GB per system; exact mapping and specifications remain unconfirmed. See [[ADR-0005 - Phased bare-metal k0s cluster]]. |
| Existing Proxmox VMs | External compute | Two existing VMs remain outside this repository; their mapping to the planned Proxmox host is to be confirmed. |
| QNAP TS-673A | Always-on anchor | Hosts Gitea, NetBox, and Immich, deployed from the QNAP's own repository. QTS 5.2.8.3359 |

> Existing Proxmox platform details are retained as an external reference: see [[Proxmox]].

## Planned k0s Node Storage (Unverified)

| Device | Intended use | Target per node |
| --- | --- | --- |
| SATA SSD | OS, k0s/etcd, container runtime, images, and logs | 250–500 GB |
| Separate SSD (SATA or NVMe), if available | PostgreSQL local persistent volume | 250–500 GB |
| NVMe SSD | Dedicated Longhorn data disk | About 1 TB |

These are planning targets, not a verified inventory or disk assignment. Confirm the devices, health, and per-node availability before implementation. Each k0s node is planned as both controller and worker; the Proxmox host is not a fourth controller initially. A k0s worker VM on Proxmox is optional later.

## Candidate Switches

### MikroTik CRS309-1G-8S+IN

- Compact SFP+ core switch candidate

### MikroTik CRS305-1G-4S+IN

- Desk-side or small aggregation role candidate

### SODOLA 12-Port 10G Managed Switch

- 8x 10G SFP+, 4x 10GBase-T, 1U, web GUI, fan-cooled

## Endpoint Adapters

### MacBook M1

- Thunderbolt to SFP+ under consideration; aligned with SFP+ core direction

### Other Adapters

- Sonnet Solo10G-TB3
- OWC alternatives
- Compatibility considerations with DeskMini X300
