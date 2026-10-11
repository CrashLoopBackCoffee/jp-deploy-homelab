---
tags:
  - homelab
  - adr
  - kubernetes
  - operating-system
type: adr
status: accepted
date: 2026-10-03
created: 2026-10-03
updated: 2026-10-10
adr: 6
---

# ADR-0006 - Ubuntu Server 24.04 LTS for k0s nodes

## Status

Accepted on 2026-10-10 as the k0s host OS. Node 1 already runs Ubuntu; host details are still to be recorded in the runbook and plan.

## Context

[[ADR-0005 - Phased bare-metal k0s cluster]] establishes k0s, k0sctl, and three bare-metal controller+worker nodes. The current stable k0s system-requirements page resolves to k0s `v1.36.4+k0s.1` and lists Ubuntu 24.04 among the operating systems tested in k0s CI. k0sctl manages Linux hosts over SSH; its documented Linux access requires root or a user with passwordless `sudo` (or `doas`).

Talos is a minimal, immutable, API-driven operating system designed to run Kubernetes. It has no SSH shell or package manager and is configured with `talosctl`; its own workflow generates machine configurations and bootstraps Kubernetes. It is therefore a different Kubernetes platform choice, not a base OS for the existing SSH-managed k0sctl installation. Choosing Talos would replace k0s/k0sctl and require a separate cluster migration decision.

Talos can run Longhorn, but current Longhorn guidance requires Talos system extensions for iSCSI and util-linux tools, privileged pod security, and explicit data-volume/mount configuration. This is feasible, but it adds Talos-specific storage integration to this small cluster.

## Decision

- Use **Ubuntu Server 24.04 LTS (amd64), minimal/no desktop** on all three bare-metal k0s nodes. It is an explicit k0s-tested Ubuntu release and fits the existing k0sctl-over-SSH lifecycle.
- Keep the same Ubuntu release on all k0s nodes to limit operational variation. This does not apply to the separate Proxmox host.
- Do not install k0s, kubelet, Docker, or a separate container runtime during OS installation. Bootstrap k0s later with k0sctl as `controller+worker` and `noTaints: true`; never use role `single` / `--single`.
- On Node 1 the OS disk is the 232.9 GiB Samsung SATA SSD, slightly below the 250–500 GB planning target. This is not a documented k0s/Ubuntu minimum-size failure; maintain k0s's required 15% free space on the worker disk. The Kingston 1 TB NVMe (Longhorn) and the WDC 256 GB NVMe (PostgreSQL) are blank and not part of the OS volume. Never select a disk by a guessed `/dev/sdX` name.
- Enable OpenSSH Server and use a dedicated administration account with an SSH key and the required passwordless `sudo`, reachable only from the management network. Set the hostname, stable IP/DNS, and time synchronization from the approved network plan.
- Before Longhorn is deployed on Ubuntu, follow its current node prerequisites, including installing `open-iscsi` and ensuring `iscsid` is running. Add the NFS client only if the selected Longhorn backup or RWX configuration requires it.

The first-node OS preparation procedure is in [[Runbook - k0s Node OS Preparation]]. It stops before k0s bootstrap until the disk identities, management access, network values, and stable API endpoint plan are known.

## Alternatives considered

- **Talos Linux:** not selected for the current k0s architecture. It is a reasonable choice if the project deliberately switches to Talos-managed Kubernetes and accepts API-only OS operations and Talos-specific Longhorn configuration.
- **Ubuntu 26.04 LTS:** not selected yet because the current k0s CI operating-system table does not list it. Reconsider after k0s documents or tests that release.
- **Ubuntu 22.04 LTS:** tested by k0s, but Ubuntu 24.04 is also tested and has a longer remaining standard support window.

## Consequences

- Node 1 can be prepared with a conventional Linux/SSH workflow compatible with k0sctl.
- The cluster remains on k0s; this proposal does not change the distribution or Pulumi kubeconfig integration.
- Hostname, static/DHCP-reserved address, disk serials, existing disk contents, and exact management access are intentionally not guessed.
- Ubuntu Server 24.04 LTS is the accepted OS; the Node 1 installation was completed outside this repository, and its hostname, address, and disk layout are not yet recorded.

## Related notes

- [[ADR-0005 - Phased bare-metal k0s cluster]]
- [[k0s]]
- [[Runbook - k0s Node OS Preparation]]
- [[Open Questions]]

## Sources

- [k0s system requirements and tested operating systems](https://docs.k0sproject.io/stable/system-requirements/)
- [k0sctl SSH-based host management](https://docs.k0sproject.io/stable/k0sctl-install/)
- [k0sctl Linux SSH-user requirements](https://github.com/k0sproject/k0sctl#configuration-file-spec-fields)
- [Talos for Linux administrators](https://docs.siderolabs.com/talos/v1.14/learn-more/talos-for-linux-admins)
- [Talos cluster installation and bootstrap workflow](https://docs.siderolabs.com/talos/v1.14/getting-started/getting-started)
- [Longhorn prerequisites for Talos Linux](https://longhorn.io/docs/1.13.0/advanced-resources/os-distro-specific/talos-linux-support/)
- [Longhorn node installation requirements](https://longhorn.io/docs/1.13.0/deploy/install/)
- [Ubuntu release and support lifecycle](https://ubuntu.com/about/release-cycle)
- [Ubuntu Server 24.04 installation system requirements](https://ubuntu.com/server/docs/reference/installation/system-requirements/)
