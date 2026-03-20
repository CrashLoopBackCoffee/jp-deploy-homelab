---
tags:
  - homelab
  - iac
  - decisions
  - tooling
type: adr
status: accepted
date: 2026-03-08
created: 2026-03-20
updated: 2026-03-20
---

# ADR-0003 — Pet vs Cattle and IaC Tooling

## Status

Accepted

## Context

The homelab has two distinct categories of infrastructure:

- **Long-lived, high-touch systems** (OPNsense, Proxmox, network switches, k0s cluster bootstrap) that require imperative management, careful ordering, and manual validation.
- **Reproducible service workloads** (everything running on top of k0s) where declarative IaC and programmatic logic deliver the most value.

Additionally, NetBox as a source of truth creates a **circular bootstrap dependency** — it is itself part of the infrastructure it is meant to document. Git must be the source of truth, with NetBox as a derived documentation mirror.

## Decision

**Git is the single source of truth. Everything else is a derived artifact.**

- **Pets** (OPNsense, Proxmox, network switches, k0s cluster bootstrap): managed with **Ansible** or **k0sctl**
- **Cattle** (all workloads and services running on top of k0s): managed with **Pulumi (Python)**
- OpenTofu and Terraform are not used

### Infrastructure Tiers

| Tier | Layer | Tool | Notes |
|---|---|---|---|
| Tier 0 | OPNsense | Ansible | Pet — high-touch, long-lived |
| Tier 0/1 | Proxmox | Ansible | Pet — high-touch, long-lived |
| Tier 0 | Switches | Ansible / documented YAML | Pet — limited API, documented manually |
| Tier 1 | k0s bootstrap | k0sctl | Pet — cluster lifecycle tool |
| Tier 1/2 | Platform & Apps | Pulumi (Python) | Cattle — K8s workloads and services |
| Tier 1 | State backend | MinIO on QNAP | S3-compatible, always-on anchor |
| Tier 1 | Git server | Gitea on QNAP | Source of truth host |
| Tier 2 | Documentation mirror | NetBox on QNAP | Populated from IaC state via sync script |

### Bootstrap Sequence

> This sequence must be executable from a complete cold start.

```text
1. QNAP is up (always-on anchor)
2. git clone from Gitea on QNAP
3. Apply tier0/opnsense    → network exists, VLANs up
4. Apply tier0/switches    → switching topology correct
5. Apply tier1/proxmox     → VMs declared and running
6. Apply tier1/platform    → NetBox, MinIO, k8s control plane
7. Apply tier2/apps        → workloads running
8. Run NetBox sync         → documentation reflects reality
```

Steps 1–4 require zero services running on Proxmox.

### Git Repository Structure

```text
repo/
├── network/
│   ├── vlans.yaml              ← canonical VLAN schema
│   └── switches/
│       ├── sodola-core.yaml
│       ├── jgs524ev2.yaml
│       ├── gs108ev3.yaml
│       └── gs308epp.yaml
├── tier0/
│   ├── opnsense/               ← Ansible (pet)
│   └── switches/               ← Ansible / documented YAML (pet)
├── tier1/
│   ├── proxmox/                ← Ansible (pet)
│   ├── k0s/                    ← k0sctl (pet)
│   └── platform/               ← Pulumi (Python) (cattle)
└── tier2/
    └── apps/                   ← Pulumi (Python) (cattle)
```

## Consequences

- Lower lock-in risk vs proprietary IaC tooling
- Consistent Python across scripting and IaC layers
- Clear separation of operational concern between pets and cattle
- NetBox sync step makes documentation a derived output, not a prerequisite

## Related

- [[Hardware Inventory]]
- [[VLANs]]
- [[Open Questions]]
