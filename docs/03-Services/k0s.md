---
tags:
  - homelab
  - service
  - k0s
  - kubernetes
type: service
status: active
created: 2026-03-20
updated: 2026-10-10
---

# k0s

## Purpose

Kubernetes distribution used for the control plane in the homelab.

## Deployment model

The target is three bare-metal k0s nodes, each a controller and worker, plus a separate Proxmox host for Home Assistant, UniFi, and other VM/LXC workloads. The Proxmox host is not a fourth controller initially; a worker VM there is optional later. k0sctl owns bootstrap and cluster lifecycle outside Pulumi. The Kubernetes Pulumi stack consumes the shared kubeconfig and manages platform add-ons; service stacks manage workloads.

## Host OS

Minimal Ubuntu Server 24.04 LTS runs on all three bare-metal k0s nodes (accepted in [[ADR-0006 - Ubuntu Server 24.04 LTS for k0s nodes]]) because the current k0s support matrix lists Ubuntu 24.04 as CI-tested and k0sctl manages Linux hosts over SSH. Talos is an alternative Kubernetes platform, not a base OS for this k0s/k0sctl design. Node preparation is described in [[Runbook - k0s Node OS Preparation]].

## Node inventory

| Node | Hostname | Address | VLAN | DNS | Status |
| --- | --- | --- | --- | --- | --- |
| Node 1 | `k0s0` | `10.10.8.1/16` (static DHCP mapping in OPNsense; gateway `10.10.0.1`) | 10 (CoRE) | none yet; use the IP in k0sctl | Phase 1 live: k0s v1.36.4+k0s.1, controller+worker, Ready (2026-10-10) |

Access: `k0sctl@10.10.8.1` with passwordless sudo, see [[ADR-0007 - Dedicated k0sctl automation account]]. The cluster configuration is `services/k0s/k0sctl/cluster.yaml`; its Phase 1 API endpoint is `10.10.8.1` ([[ADR-0008 - Phase 1 k0s API endpoint]]). Disk layout is recorded in [[Runbook - k0s Node OS Preparation]]. The admin kubeconfig is published in 1Password at `op://Homelab/Kubeconfig prod/password`, which the Pulumi stacks consume. The Kubernetes Pulumi stack (`jaypee-solutions/kubernetes/prod`) is applied: MetalLB (pool `10.10.88.1`–`10.10.88.250`), NFS CSI, cert-manager with a Let's Encrypt wildcard certificate for `*.4jp.de` (DNS-01 through Cloudflare, [[ADR-0010 - Cloudflare account token for the Kubernetes stack]]), Traefik at `10.10.88.1` with a dnsmasq record `k8s-ingress-prod.4jp.de` ([[ADR-0012 - Local DNS records through dnsmasq on OPNsense]]), CloudNativePG, and OpenEBS LVM with the `openebs-lvm-postgres` StorageClass ([[ADR-0009 - LVM-backed local volumes for PostgreSQL]]). Secrets come from `.envrc` through a 1Password service account ([[ADR-0013 - 1Password service account for Pulumi]]).

## Expansion-compatible bootstrap

Start with Node 1 only as k0sctl role `controller+worker`, with `noTaints: true` so normal workloads can be scheduled there. Use the default k0s-managed etcd datastore. Do not use role `single` or the k0s `--single` flag: current k0s documentation says that mode disables multi-node features and the cluster cannot be extended. Add Nodes 2 and 3 as controller+workers through the same k0sctl-managed cluster; use consistent k0s configuration on all controllers.

## Rollout and HA gates

- **Phase 1:** one controller+worker; explicitly non-HA. Validate the baseline, ingress/service load balancing, Longhorn provisioning with one replica, PostgreSQL, observability, backups, and restore. Inter-node behavior is not testable yet.
- **Phase 2:** two controller+workers; test controller expansion, join, scheduling/rescheduling, inter-node networking, two Longhorn replicas across both hosts and resynchronization after host recovery, and PostgreSQL replication/failover. This plan does not call two controllers HA: a two-member etcd quorum cannot survive loss of either member, and there is no third host for restoring full host-diverse Longhorn replicas while one is unavailable.
- **Phase 3:** three controller+workers and a three-member etcd quorum; validate three Longhorn replicas across all physical hosts, three-host PostgreSQL placement, node loss, data availability, and recovery. Treat the control plane as HA only after the fault-tolerant external API endpoint and failure tests are also working. Application/data availability remains a separate property.

k0s control-plane HA requires a stable external TCP load balancer configured as `spec.api.externalAddress`, routing ports 6443, 8132, and 9443. Plan this separately from the in-cluster MetalLB service load balancer. The API VIP, load-balancer placement, and its own failure tolerance are open inputs; an unprotected single load balancer would remain a control-plane availability dependency.

## Storage and PostgreSQL

Planned per-node storage is a 250–500 GB SATA SSD for OS/k0s/etcd/runtime/images/logs, an optional separate 250–500 GB SSD for a node-local PostgreSQL persistent volume, and about 1 TB NVMe for Longhorn. On `k0s0` these are the Samsung SATA SSD, the WDC 256 GB NVMe, and the Kingston 1 TB NVMe; the other nodes are unverified. Longhorn runs on `k0s0` with one replica ([[ADR-0014 - Longhorn on a dedicated ext4 data disk]]), so volumes are not redundant, and two physical hosts cannot restore host-diverse replica placement while one remains unavailable.

The Kubernetes stack currently installs the CloudNativePG operator but no database cluster. Paperless uses a Bitnami PostgreSQL Helm release today. CloudNativePG is the planned replication path; migrating Paperless and selecting storage classes, replication policy, and backup/restore behavior require a separate tested change.

See [[ADR-0005 - Phased bare-metal k0s cluster]] for the full topology, acceptance gates, source links, and open implementation inputs.

## Observed issue

One reported error path showed gRPC transport failures to `127.0.0.1:2379` with `connection refused`, indicating local etcd reachability or service availability problems.

## Incident links

- [[INC-2026-03-03 - k0s etcd connection refused]]
