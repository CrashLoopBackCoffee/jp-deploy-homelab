---
tags:
  - homelab
  - adr
  - kubernetes
  - infrastructure
type: adr
status: accepted
date: 2026-10-03
created: 2026-10-03
updated: 2026-10-03
adr: 4
---

# ADR-0004 - Bare-metal k0s and external infrastructure scope

## Status

Accepted. This supersedes the Proxmox-management and VM-based cluster-placement portions of [[ADR-0003 - Pet vs Cattle and IaC tooling]].

## Context

The Kubernetes Pulumi stack has been changed to consume an externally bootstrapped k0s kubeconfig. The k0s cluster is intended to run on bare-metal nodes rather than Proxmox VMs. The repository still contained donor-project Proxmox management, a Proxmox-hosted Z-Wave controller that is not used, an Immich deployment that belongs on the QNAP, and a UniFi stack for a separate Proxmox host.

There are already two running Proxmox VMs, and UniFi runs on another Proxmox host. These systems are external to this repository. The repository's current focus is Kubernetes, while the user explicitly chose to retain the unrelated remote-Docker workspaces for Obsidian, S3/MinIO, and legacy monitoring unchanged.

## Decision

- Run k0s directly on bare-metal nodes. Do not create or manage k0s VMs through Proxmox.
- Bootstrap and lifecycle-manage k0s with k0sctl outside Pulumi. The Kubernetes Pulumi stack consumes the shared kubeconfig and manages platform add-ons; service Pulumi stacks continue to deploy Kubernetes workloads.
- Remove Proxmox infrastructure management and provider dependencies from this repository.
- Remove the unused Z-Wave controller deployment and its MQTT metrics configuration.
- Remove the Immich Pulumi workspace; Immich remains on the QNAP and is not managed here.
- Remove the UniFi Pulumi workspace; UniFi and the existing Proxmox VMs remain external and are not moved, destroyed, or reconfigured by this repository.
- Retain the S3/MinIO and monitoring legacy remote-Docker workspaces unchanged; their placement is outside this decision. The Obsidian workspace was originally retained too, and was removed later by [[ADR-0011 - LAN-first ingress and service cleanup]].
- Do not run Pulumi updates, destroys, or state operations as part of this repository cutover. Review any old stack state separately before reusing it.
- The target is three bare-metal k0s nodes plus one separate Proxmox host; exact machine mapping, specifications, disk inventory, and network addressing remain open. See ADR-0005 for the phased design.

## Consequences

- The active repository no longer provisions Proxmox infrastructure, UniFi, Immich, or Z-Wave.
- Existing Proxmox hosts and VMs continue to exist outside this repository. No infrastructure deployment or teardown was performed.
- k0s bootstrap remains a prerequisite for the Kubernetes Pulumi stack, and k0sctl must publish the kubeconfig at the shared 1Password reference.
- The target topology is recorded in ADR-0005; exact per-host inventory, disk availability, and VLAN/address assignment remain open questions.
- The retained remote-Docker workspaces mean the repository is Kubernetes-focused but not exclusively Kubernetes-only.

## Alternatives considered

- Keep k0s on Proxmox VMs: rejected because the user plans to install k0s on bare metal and sees no value in managing Proxmox here.
- Keep the Z-Wave VM deployment: rejected because Z-Wave is not used.
- Move Immich into Kubernetes: rejected because it remains on the QNAP.
- Move UniFi into this repository or Kubernetes: rejected because UniFi runs on a separate Proxmox host.

## Related notes

- [[ADR-0003 - Pet vs Cattle and IaC tooling]]
- [[ADR-0005 - Phased bare-metal k0s cluster]]
- [[Architecture Overview]]
- [[Hardware Inventory]]
- [[k0s]]
- [[Proxmox]]
- [[VLANs]]
