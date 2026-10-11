---
type: Architecture
title: Phased bare-metal k0s cluster plan
description: Three-node expandable k0s plan with phased HA gates, storage intent, and a proposed Ubuntu host OS.
timestamp: 2026-10-06T00:00:00Z
tags: [homelab, kubernetes, k0s, architecture, storage]
---

# Target topology

The planned allocation is three physical bare-metal k0s nodes plus one separate Proxmox host. Each k0s node is both controller and worker. The Proxmox host runs Home Assistant, UniFi, and other VM/LXC workloads; it is not a fourth controller initially. A k0s worker VM there is an optional later capacity addition and does not count toward etcd quorum.

The four systems are Ryzen-based and typically have 16–32 GB RAM. Node 1 is `k0s0` at `10.10.8.1/16` on VLAN 10 (CoRE) with gateway `10.10.0.1`, 12 CPU threads, 31 GiB RAM, and no DNS record yet; the other host mappings remain unconfirmed. Its disks are a 232.9 GiB Samsung SATA SSD (OS), a 931.5 GiB Kingston NVMe (Longhorn data disk, ext4 at `/var/lib/longhorn`), and a 238.5 GiB WDC NVMe (LVM volume group `postgres` for node-local PostgreSQL volumes). Ubuntu Server 24.04 LTS is the accepted host OS (accepted 2026-10-10) and is installed on Node 1. See `docs/08-Decisions/ADR-0005 - Phased bare-metal k0s cluster.md`, `docs/08-Decisions/ADR-0006 - Ubuntu Server 24.04 LTS for k0s nodes.md`, and `docs/08-Decisions/ADR-0007 - Dedicated k0sctl automation account.md`.

# Host OS recommendation

The current stable k0s system-requirements page resolves to `v1.36.4+k0s.1` and lists Ubuntu 24.04 among the operating systems tested in CI. Recommend minimal Ubuntu Server 24.04 LTS for all three k0s nodes; k0sctl manages Linux hosts over SSH with a root or passwordless-sudo account.

Talos is a minimal, immutable, API-managed operating system designed to run Kubernetes. It has no SSH shell or package manager and uses `talosctl` to configure and bootstrap its Kubernetes cluster. Treat Talos as a replacement for k0s/k0sctl, not as a base OS under the current k0s plan. Longhorn does support Talos, but requires Talos-specific system extensions, privileged pod security, and explicit volume/mount configuration.

Node 1 (`k0s0`) boots from its 232.9 GiB Samsung SATA SSD, slightly below the 250 GB planning target; the root volume uses 100 GiB of the LVM volume group, leaving room to grow while preserving the required 15% free space. The Kingston 1 TB and WDC 256 GB NVMe drives were wiped on 2026-10-10 and have since been prepared: the Kingston is the Longhorn data disk and the WDC is the `postgres` volume group. See `docs/06-Operations/Runbook - k0s Node OS Preparation.md`. On 2026-10-10 k0sctl bootstrapped Phase 1 here: k0s `v1.36.4+k0s.1`, one controller+worker, schedulable (no taints); `k0s0` is Ready and the kube-system pods are running. The Kubernetes Pulumi stack `jaypee-solutions/kubernetes/prod` is applied (MetalLB, NFS CSI, cert-manager, Traefik, CloudNativePG operator, OpenEBS LVM, Longhorn; 112 resources, checked 2026-10-11).

# Expansion-compatible bootstrap

Start with Node 1 only, in the k0sctl `controller+worker` role with `noTaints: true`, using k0s-managed etcd. Do not use role `single` or the k0s `--single` flag: the current k0s Quick Start says that `--single` disables multi-node features and the cluster cannot be extended. Add the second and third controllers through the same k0sctl-managed cluster configuration; maintain identical k0s configuration across controllers.

Phase 1 is explicitly non-HA. Phase 2 has two controllers and is still not HA for this plan: k0s documentation distinguishes API/control-plane availability from etcd quorum HA, and a two-member etcd quorum cannot survive losing one member. Phase 3 establishes three controller/etcd members; only after the stable, fault-tolerant API endpoint and failure tests are complete is the control plane treated as HA. Application and data availability require separate validation.

k0s control-plane HA requires an external TCP load balancer and a stable `spec.api.externalAddress`, routing ports 6443, 8132, and 9443. The VIP, load-balancer implementation/placement, redundancy, and failure characteristics are open. The load balancer itself must not be an unaccounted single point of failure for an end-to-end HA claim. This endpoint is distinct from the current in-cluster MetalLB setup for Kubernetes `LoadBalancer` services.

# Phases

| Phase | Nodes | Validation focus | Status semantics |
| --- | --- | --- | --- |
| 1 | Node 1 controller+worker | Cluster baseline, ingress/service load balancing, Longhorn on NVMe with one replica, PostgreSQL on local storage, observability, backup and restore | Non-HA; no inter-node validation or node-failure tolerance |
| 2 | Nodes 1–2 controller+workers | Controller expansion, joining, scheduling/rescheduling, inter-node networking, two Longhorn replicas across two hosts and resynchronization after host recovery, PostgreSQL replication/failover | Not HA; two-member etcd has no single-member failure tolerance and no third host for restoring full host-diverse Longhorn replicas while one is unavailable |
| 3 | Nodes 1–3 controller+workers | Three Longhorn replicas across three physical nodes in the healthy state, three-host PostgreSQL, node-loss and recovery tests | First planned control-plane HA state, conditional on the external endpoint and tests |

# Storage intent per k0s node

| Device | Intended use | Planning target |
| --- | --- | --- |
| SATA SSD | OS, k0s/etcd data, runtime, images, logs | 250–500 GB |
| Separate SSD (SATA or NVMe), if spare | Node-local PostgreSQL persistent volume | 250–500 GB |
| NVMe SSD | Dedicated Longhorn data disk | About 1 TB |

These are planning targets. Node 1 is verified: the SATA SSD is the OS disk (232.9 GiB, slightly below the 250 GB target), the 931.5 GiB Kingston NVMe is the Longhorn disk, and the 238.5 GiB WDC NVMe is the node-local PostgreSQL disk (below the 250 GB target). Nodes 2 and 3 are unverified. PostgreSQL copies must be provided by PostgreSQL replication across separately stored instances; a local disk does not replicate itself.

Longhorn is deployed by the Kubernetes Pulumi stack on Node 1 with one replica ([[ADR-0014 - Longhorn on a dedicated ext4 data disk]]). Plan one replica per available physical host as the cluster grows: one copy on the single Phase 1 node, two copies across Nodes 1–2 in Phase 2, and three copies across Nodes 1–3 in the healthy Phase 3 state. A single-node volume has no replica redundancy. In Phase 2, one node failure leaves one copy and no third host is available for full host-diverse replica replacement until the failed host returns. In Phase 3, one failure leaves two copies; test volume availability and restoration to three distinct hosts after recovery. Longhorn replication does not replace off-node backup and restore.

The CloudNativePG operator is currently installed by the Kubernetes stack, but Paperless uses a Bitnami PostgreSQL Helm release. CloudNativePG is the planned implementation for PostgreSQL replication: it manages physical streaming replicas and creates a PVC per instance. Its default anti-affinity prefers separate nodes but is not a hard placement guarantee, so distinct-host placement must be configured and verified for the Phase 2/3 goal. Paperless migration, anti-affinity behavior during node failure, sync policy, and backup/retention remain separate implementation work; the `openebs-lvm-postgres` StorageClass for the volumes already exists.

# Open implementation inputs

- Map each physical system to Node 1, Node 2, Node 3, or Proxmox; confirm CPU, RAM, NICs, BIOS, OS, and management access.
- Node 1's API endpoint is `10.10.8.1` for Phase 1 (see `docs/08-Decisions/ADR-0008 - Phase 1 k0s API endpoint.md`); the Kubeconfig must be refreshed when a load balancer is introduced. The PostgreSQL provisioner is OpenEBS LVM LocalPV (ADR-0009), applied through the Kubernetes stack; no CloudNativePG database cluster uses it yet.
- Decide node IPs, DNS, VLAN/subnet, routing/firewall rules, and a stable API VIP plus TCP load-balancer placement.
- Select k0s and add-on versions, the Longhorn backup target and storage-class policy, coexistence with current NFS CSI, and CloudNativePG instance placement.
- Design and test Paperless database migration to CloudNativePG, replication semantics, and off-node backup/restore target and retention.
- Document shared power, switch, routing, and load-balancer failure domains before describing service-level availability.

# Citations

[1] [k0s Quick Start: expandable controller+worker install](https://docs.k0sproject.io/stable/install/)
[2] [k0sctl lifecycle and host role fields](https://docs.k0sproject.io/stable/k0sctl-install/)
[3] [k0s multi-node controller requirements](https://docs.k0sproject.io/stable/k0s-multi-node/)
[4] [k0s HA semantics, etcd, TCP load balancer, and external address](https://docs.k0sproject.io/stable/high-availability/)
[5] [k0sctl `controller+worker` and `noTaints` fields](https://github.com/k0sproject/k0sctl#host-fields)
[6] [Longhorn replica scheduling](https://longhorn.io/docs/1.12.0/nodes-and-volumes/nodes/scheduling/)
[7] [Longhorn replication and backup capabilities](https://longhorn.io/docs/1.12.0/what-is-longhorn/)
[8] [CloudNativePG physical streaming replication](https://cloudnative-pg.io/docs/1.30/replication)
[9] [CloudNativePG scheduling and anti-affinity](https://cloudnative-pg.io/docs/1.30/scheduling)
[10] [CloudNativePG per-instance persistent volumes](https://cloudnative-pg.io/docs/1.30/storage)
[11] [k0s tested operating systems](https://docs.k0sproject.io/stable/system-requirements/)
[12] [k0sctl SSH host requirements](https://docs.k0sproject.io/stable/k0sctl-install/)
[13] [Talos for Linux administrators](https://docs.siderolabs.com/talos/v1.14/learn-more/talos-for-linux-admins)
[14] [Talos cluster installation and bootstrap](https://docs.siderolabs.com/talos/v1.14/getting-started/getting-started)
[15] [Longhorn requirements for Talos](https://longhorn.io/docs/1.13.0/advanced-resources/os-distro-specific/talos-linux-support/)
[16] [Longhorn installation requirements](https://longhorn.io/docs/1.13.0/deploy/install/)
[17] [Ubuntu release and support lifecycle](https://ubuntu.com/about/release-cycle)
[18] [Ubuntu Server installation system requirements](https://ubuntu.com/server/docs/reference/installation/system-requirements/)
