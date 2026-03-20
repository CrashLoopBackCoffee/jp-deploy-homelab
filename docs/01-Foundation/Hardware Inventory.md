---
tags:
  - homelab
  - hardware
  - inventory
type: foundation
status: active
created: 2026-03-20
updated: 2026-03-20
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
| Proxmox node | Compute (single → 3-node cluster) | IaC must be cluster-aware from day one |
| QNAP TS-673A | Always-on anchor | Hosts Gitea, MinIO, NetBox. QTS 5.2.8.3359 |

> Proxmox platform details: see [[Proxmox]]

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
