---
tags:
  - homelab
  - adr
  - kubernetes
  - storage
type: adr
status: accepted
date: 2026-10-11
created: 2026-10-11
updated: 2026-10-11
adr: 14
---

# ADR-0014 - Longhorn on a dedicated ext4 data disk

## Status

Accepted on 2026-10-11. The chart is `longhorn/longhorn` 1.13.0.

## Context

[[ADR-0005 - Phased bare-metal k0s cluster]] reserves the 931.5 GiB Kingston NVMe on `k0s0` for replicated general-purpose volumes, while [[ADR-0009 - LVM-backed local volumes for PostgreSQL]] keeps databases on node-local LVM volumes. Phase 1 has one node, so replication has nothing to replicate to yet.

## Decision

- Longhorn stores replicas on the whole Kingston disk, formatted as ext4 with label `longhorn` and mounted at `/var/lib/longhorn` (Longhorn's default data path) through an `fstab` entry that uses the `/dev/disk/by-id` path and `nofail`. Longhorn manages replica files itself, so LVM adds nothing here.
- The disk is prepared with Ansible (`services/k0s/ansible/prepare-longhorn-storage.yaml`), which resolves the disk by by-id path, asserts its serial, and lets `community.general.filesystem` refuse a disk that already carries a different filesystem. The same play installs `nfs-common` (RWX volumes, NFS backup targets) and blacklists `sd*` devices in `/etc/multipath.conf`, because `multipathd` otherwise claims the block devices Longhorn exposes.
- The chart is installed by the Kubernetes Pulumi stack (`services/kubernetes/kubernetes/longhorn.py`) as a `helm.v3.Release`, because it uses pre-upgrade, post-upgrade, and pre-delete hook jobs that `helm.v4.Chart` does not run. The kubelet directory is set to the k0s path.
- The replica count is 1 (default setting and default StorageClass) until a second node joins; the default of 3 would leave every volume degraded. Raise `replica-count` in `services/kubernetes/Pulumi.prod.yaml` when nodes 2 and 3 are added.
- The chart's default StorageClass `longhorn` becomes the cluster default, since no other default exists. PostgreSQL keeps its explicit `openebs-lvm-postgres` class.
- The chart installs no CSI snapshot controller, so the one from OpenEBS stays the only one.

## Consequences

- With one replica, a disk failure loses volume data. Backups are an open item and must exist before Longhorn holds data that matters.
- Longhorn and OpenEBS both consume snapshot CRDs from one controller; upgrading either must keep that single controller.
- Formatting the Kingston disk is irreversible; it was blank and approved for Longhorn on 2026-10-10.
- `nofail` lets the node boot without the disk. If the disk is missing, `/var/lib/longhorn` is an empty directory on the root volume, so Longhorn could write replicas there. Check that `findmnt /var/lib/longhorn` shows the Kingston disk after any disk incident or reboot problem.

## Related notes

- [[ADR-0005 - Phased bare-metal k0s cluster]]
- [[ADR-0009 - LVM-backed local volumes for PostgreSQL]]
- [[k0s]]
- [[Open Questions]]
