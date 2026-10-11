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
updated: 2026-10-06
adr: 5
---

# ADR-0005 - Phased bare-metal k0s cluster

## Status

Accepted as the architecture plan. This ADR authorizes documentation and design work only; it does not authorize host changes, cluster bootstrap, installation, Pulumi preview, or deployment.

## Context

Four Ryzen-based systems are available for the intended end state: three bare-metal Kubernetes nodes and one separate Proxmox host. Typical memory is 16–32 GB per system. Node 1 is `k0s0` (12 threads, 31 GiB RAM) with a 232.9 GiB SATA SSD, a 931.5 GiB NVMe holding an existing Proxmox install, and a 238.5 GiB NVMe holding a Windows-style install. The mapping of the other systems and their disks remains unconfirmed.

The Kubernetes Pulumi stack already installs MetalLB, NFS CSI, cert-manager, Traefik, and the CloudNativePG operator. It does not currently install Longhorn. Paperless currently uses a Bitnami PostgreSQL Helm release; the installed CloudNativePG operator has no database cluster resource managed by this repository today.

## Decision

### Target topology

- Run three physical bare-metal k0s nodes. Each is both a controller and a worker.
- Keep one separate Proxmox host for Home Assistant, UniFi, and other VM/LXC workloads. It is not a fourth k0s controller initially.
- A k0s worker VM on Proxmox is an optional later addition; it does not count toward the three-controller etcd quorum.
- Use k0sctl outside Pulumi for bootstrap and cluster membership. Keep Kubernetes Pulumi limited to add-ons and workloads after the shared kubeconfig exists.

### Expansion-compatible bootstrap

Start with only Node 1, using the k0sctl host role `controller+worker` and `noTaints: true` so regular workloads can be scheduled there. Use k0s-managed etcd, the default datastore. Do not use k0sctl role `single` or the k0s `--single` install flag: current k0s documentation says that mode disables features required to extend the cluster. Do not create a k0sctl configuration or install anything until the per-host and network inputs are known.

Use the same k0s cluster configuration on every controller. Add Node 2 and Node 3 by extending the k0sctl host list and applying the cluster lifecycle workflow; do not reinstall the initial node as part of normal expansion. Maintain the complete host list carefully: k0sctl documents that it can add nodes but cannot remove existing nodes.

### Phased rollout and acceptance gates

| Phase | Topology and intent | Required validation | HA classification |
| --- | --- | --- | --- |
| 1 | Node 1 only, `controller+worker`; build the baseline and retain the expansion-compatible mode. | Validate the cluster, ingress and workload load balancing, Longhorn provisioning on the NVMe with one replica, PostgreSQL on local storage, observability, backup, and restore. Inter-node behavior cannot be validated with one node. | Explicitly non-HA. A single controller and one copy of node-local data have no node-failure tolerance. |
| 2 | Add Node 2 as `controller+worker`. | Test joining and controller expansion; scheduling and pod rescheduling; inter-node networking; two Longhorn replicas spread across the two hosts, degraded-volume availability, and replica resynchronization after the failed host returns; PostgreSQL replication and failover behavior. | Not HA for this plan. k0s documentation notes that a two-node control plane may be described as HA in an API/control-plane sense, but it is not HA from etcd's quorum perspective. A two-member etcd cluster cannot retain quorum after losing either member. Do not call Phase 2 a proper HA cluster. |
| 3 | Add Node 3 as `controller+worker`, yielding three k0s controllers and a three-member etcd quorum. | Validate three Longhorn replicas spread across the three physical nodes in the healthy state, PostgreSQL instances across all three physical nodes, node loss, scheduling/rescheduling, data availability with two surviving replicas, and resynchronization/rebuild after recovery. | Treat the k0s control plane as HA only after the three-controller quorum, a fault-tolerant TCP API load-balancer endpoint, and the planned failure tests are all in place. This does not by itself make applications or their data HA. |

A three-controller etcd quorum is necessary but not sufficient for end-to-end control-plane availability: k0s also requires a TCP load balancer and a stable `spec.api.externalAddress`. Reserve and design that endpoint before bootstrap if possible, so the first node and later controllers use the same address.

The API load balancer is separate from MetalLB, which the current Kubernetes stack uses for in-cluster `LoadBalancer` services. It must route TCP ports 6443, 8132, and 9443 to the controllers. The VIP, implementation, placement, and failure characteristics remain open. The load balancer itself must not be an unaccounted single point of failure before claiming end-to-end control-plane HA. Shared power, switching, and routing remain additional failure domains.

### Per-node storage intent

| Device | Intended use | Target per k0s node |
| --- | --- | --- |
| SATA SSD | Operating system, k0s and etcd data, container runtime, images, and logs | 250–500 GB |
| Separate SSD (SATA or NVMe), if available | PostgreSQL local persistent volume for the PostgreSQL instance placed on that node | 250–500 GB |
| NVMe SSD | Dedicated Longhorn data disk | About 1 TB |

These are planning targets. Node 1 is verified: the 232.9 GiB SATA SSD is the OS disk, slightly below the 250 GB lower bound, the blank 931.5 GiB Kingston NVMe is the intended Longhorn disk, and the blank 238.5 GiB WDC NVMe is the node-local PostgreSQL disk, also below the 250 GB lower bound. Nodes 2 and 3 are unverified. PostgreSQL local storage is node-bound; PostgreSQL replication, not the local disk, supplies database copies on other nodes.

Longhorn will be introduced as a platform add-on later; it is not currently deployed. Target one replica per available host by phase: one on Node 1 in Phase 1, two across Nodes 1–2 in Phase 2, and three across Nodes 1–3 in the healthy Phase 3 state. Phase 1 has no replica redundancy. In Phase 2, one node failure leaves only one copy; there is no third host for restoring two host-diverse copies until the failed host returns. In Phase 3, one node failure leaves two copies, and the test must verify volume availability and restoration to three distinct hosts after recovery. Longhorn replication is not a substitute for backups; backup and restore must use an off-node destination.

Use CloudNativePG for the planned PostgreSQL replication path because its operator is already installed in the Kubernetes platform stack. Plan a deliberate migration from Paperless's current Bitnami PostgreSQL release before using Paperless as the replication test workload.

Start with one PostgreSQL instance in Phase 1, expand to two for Phase 2 tests, and three for Phase 3 validation, each with its own local SATA-backed persistent volume. CloudNativePG manages physical streaming replicas and a PVC per instance. Its default pod anti-affinity prefers separate nodes but does not require it, so configure and verify placement on distinct physical hosts in the Phase 2/3 steady state.

The migration, local-volume provisioner/storage class, anti-affinity behavior during failure, synchronous/asynchronous replication policy, and backup destination/retention must be designed and tested separately; none is implemented by this ADR.

## Consequences

- Phase 1 can proceed later without choosing k0s's non-expandable single-node mode.
- Phase 2 is a useful integration and recovery exercise but is intentionally not an HA milestone.
- Phase 3 is the first planned control-plane HA state, conditional on three-controller quorum, a fault-tolerant external API endpoint, and failure tests, not merely on having three controller processes.
- Workload availability, Longhorn data durability, PostgreSQL failover, and backups each require independent validation.
- Exact node inventory, disk availability, OS proposal acceptance, k0s/add-on versions, node addressing, VLANs/firewall paths, API VIP/load-balancer placement and redundancy, and database migration remain prerequisites for implementation.

## Alternatives considered

- Start with k0s `--single` / k0sctl role `single`: rejected because current k0s documentation says the mode cannot be extended to a multi-node cluster.
- Use the Proxmox host as a fourth controller from the outset: rejected; the control-plane plan is three physical bare-metal controllers, while Proxmox remains separate.
- Treat two controllers as proper HA: rejected for this plan because a two-member etcd quorum has no tolerance for losing one member.
- Store PostgreSQL only on Longhorn: rejected as the planned default because the requested layout provides dedicated local SATA storage for PostgreSQL and PostgreSQL itself will replicate across hosts. This does not rule out a later, explicitly evaluated storage design change.

## Related notes

- [[ADR-0004 - Bare-metal k0s and external infrastructure scope]]
- [[Architecture Overview]]
- [[Hardware Inventory]]
- [[k0s]]
- [[Runbook - k0s Recovery]]
- [[ADR-0006 - Ubuntu Server 24.04 LTS for k0s nodes]]
- [[Runbook - k0s Node OS Preparation]]
- [[Open Questions]]

## Sources

- [k0s Quick Start: expandable single-node install](https://docs.k0sproject.io/stable/install/)
- [k0sctl installation and lifecycle guidance](https://docs.k0sproject.io/stable/k0sctl-install/)
- [k0s multi-node controller requirements](https://docs.k0sproject.io/stable/k0s-multi-node/)
- [k0s control-plane HA, etcd guidance, API load balancer, and `externalAddress`](https://docs.k0sproject.io/stable/high-availability/)
- [k0sctl host role and `noTaints` fields](https://github.com/k0sproject/k0sctl#host-fields)
- [Longhorn replica scheduling across nodes and zones](https://longhorn.io/docs/1.12.0/nodes-and-volumes/nodes/scheduling/)
- [Longhorn replication, repair, and backup capabilities](https://longhorn.io/docs/1.12.0/what-is-longhorn/)
- [CloudNativePG physical streaming replication](https://cloudnative-pg.io/docs/1.30/replication)
- [CloudNativePG instance scheduling and anti-affinity](https://cloudnative-pg.io/docs/1.30/scheduling)
- [CloudNativePG per-instance persistent volumes](https://cloudnative-pg.io/docs/1.30/storage)
