---
tags:
  - homelab
  - iac
  - decisions
  - tooling
type: adr
status: superseded
date: 2026-03-08
created: 2026-03-20
updated: 2026-10-03
---

# ADR-0003 — Pet vs Cattle and IaC Tooling

## Status

Superseded in part by [[ADR-0004 - Bare-metal k0s and external infrastructure scope]]. Its Proxmox-management and VM-based cluster-placement decisions are no longer current; the historical pet/cattle and tooling rationale is retained.

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

The k0s cluster is bootstrapped and lifecycle-managed with k0sctl, outside Pulumi. The Kubernetes Pulumi stack consumes its kubeconfig from the shared 1Password item and manages only platform add-ons and workloads; it republishes that secret as the `kubeconfig` stack output for existing Pulumi consumers.

### Infrastructure Tiers

| Tier | Layer | Tool | Notes |
|---|---|---|---|
| Tier 0 | OPNsense | Ansible | Pet — high-touch, long-lived |
| Tier 0/1 | Proxmox | Ansible | Pet — high-touch, long-lived |
| Tier 0 | Switches | Ansible / documented YAML | Pet — limited API, documented manually |
| Tier 1 | k0s bootstrap | k0sctl | Pet — cluster lifecycle tool |
| Tier 1/2 | Platform & Apps | Pulumi (Python) | Cattle — K8s workloads and services |
| Tier 1 | State backend | Pulumi Cloud (`jaypee-solutions`) | MinIO was removed ([[ADR-0015 - Remove MinIO and the s3 workspace]]) |
| Tier 1 | Git server | Gitea on QNAP | Source of truth host |
| Tier 2 | Documentation mirror | NetBox on QNAP | Populated from IaC state via sync script |

### Bootstrap Sequence

> This sequence must be executable from a complete cold start.

```text
1. QNAP is up (always-on anchor)
2. Clone the Git repository from Gitea on QNAP
3. Apply tier0/opnsense → network exists, VLANs up
4. Apply tier0/switches → switching topology is correct
5. Apply tier1/proxmox → required VMs are declared and running
6. Run tier1/k0s with k0sctl → bootstrap the cluster and publish kubeconfig to the shared 1Password item
7. Apply tier1/platform → platform workloads (NetBox)
8. Apply tier2/apps → workloads running
9. Run NetBox sync → documentation reflects reality
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
- The Kubernetes Pulumi stack requires the externally managed kubeconfig from the shared 1Password item; k0sctl remains responsible for creating and updating that credential.

## Related

- [[Hardware Inventory]]
- [[VLANs]]
- [[Open Questions]]
