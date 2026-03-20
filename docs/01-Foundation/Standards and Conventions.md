---
tags:
  - homelab
  - foundation
  - standards
type: foundation
status: active
created: 2026-03-20
updated: 2026-03-20
---

# Standards and Conventions

## Documentation conventions

- One service per service note.
- One decision per ADR note.
- One problem per incident note.
- Durable lessons belong in `09-Knowledge/`, not inside incident notes only.

## Technical conventions

- Prefer open-source components first.
- Keep DHCP/DNS architecture simple unless a concrete scaling or feature requirement justifies more complexity.
- Preserve explicit notes for exceptions such as the Fritz!Box VLAN.
- Manual control is acceptable where it reduces hidden complexity.

## IaC and scripting toolchain

- Python preferred for scripting
- `uv` for environment management
- `Ruff` for linting
- **Pets** (OPNsense, Proxmox, switches, k0s bootstrap): managed with **Ansible** or **k0sctl**
- **Cattle** (workloads and services on k0s): managed with **Pulumi (Python)**
- OpenTofu and Terraform are not used

> Full rationale and bootstrap sequence: see [[ADR-0003 - Pet vs Cattle and IaC tooling]]

## Workstation and ecosystem

- macOS / MacBook
- Visual Studio Code
- Obsidian
- Cloudflare
- Hetzner

## Infrastructure scale constraints

- No HA firewall or HA DHCP requirement
- Fewer than 20 VLANs expected

## Hardware procurement criteria

For low-cost managed switches, technical evaluation must include:

- Firmware provenance
- Update path
- Management-plane exposure
- Public security reports
- Vendor trust
