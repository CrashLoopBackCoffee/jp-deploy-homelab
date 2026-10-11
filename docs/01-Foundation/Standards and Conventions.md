---
tags:
  - homelab
  - foundation
  - standards
type: foundation
status: active
created: 2026-03-20
updated: 2026-10-03
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
- **Pets** (OPNsense, switches, bare-metal k0s bootstrap): managed with **Ansible** or **k0sctl**
- **Kubernetes workloads**: managed with **Pulumi (Python)**
- Existing Proxmox VMs are external to this repository. The retained remote-Docker stacks are managed separately from Kubernetes.
- OpenTofu and Terraform are not used

> Current cluster and infrastructure scope: see [[ADR-0004 - Bare-metal k0s and external infrastructure scope]]

## Workstation and ecosystem

- macOS / MacBook
- Visual Studio Code
- Obsidian
- Cloudflare
- Hetzner

## Hardware procurement criteria

For low-cost managed switches, technical evaluation must include:

- Firmware provenance
- Update path
- Management-plane exposure
- Public security reports
- Vendor trust
