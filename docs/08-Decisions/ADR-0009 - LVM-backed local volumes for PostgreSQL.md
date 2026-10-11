---
tags:
  - homelab
  - adr
  - kubernetes
  - storage
type: adr
status: accepted
date: 2026-10-10
created: 2026-10-10
updated: 2026-10-10
adr: 9
---

# ADR-0009 - LVM-backed local volumes for PostgreSQL

## Status

Accepted on 2026-10-10. The provisioner is OpenEBS LVM LocalPV (chart `lvm-localpv` 1.10.1).

## Context

[[ADR-0005 - Phased bare-metal k0s cluster]] plans a node-local PostgreSQL volume per k0s node, with CloudNativePG supplying replication between nodes. On `k0s0` this is the blank 238.5 GiB WDC NVMe. CloudNativePG creates one PersistentVolumeClaim per instance, and several databases may share the disk.

## Decision

- Provision PostgreSQL volumes by putting the dedicated disk in an LVM volume group and creating logical volumes per PersistentVolumeClaim with the OpenEBS LVM LocalPV CSI driver. TopoLVM was the alternative; OpenEBS was chosen for fewer components (a controller and a node plugin, no `lvmd`, scheduler extender, or webhook) and because its chart enables CSI storage capacity tracking, which handles nodes with different disk sizes.
- The driver and the StorageClass `openebs-lvm-postgres` (`volgroup: postgres`, ext4, `WaitForFirstConsumer`, expansion allowed) are installed by the Kubernetes Pulumi stack (`services/kubernetes/kubernetes/openebs_lvm.py`), not by hand on the node. The chart's kubelet directory is set to the k0s path and analytics are off. The chart's default snapshot CRDs and snapshot controller stay enabled: with the CRDs disabled, its `snapshot-controller` container crash-loops (found on the first apply on 2026-10-10).
- The node-level volume group is prepared with Ansible (`services/k0s/ansible/prepare-postgres-storage.yaml`), because disks are per-host state outside Kubernetes. On `k0s0` it is the volume group `postgres` on the whole WDC NVMe (identified by serial), created on 2026-10-10 with no logical volumes yet.
- Volumes remain node-bound; database copies on other nodes come from PostgreSQL replication, not the disk.

## Consequences

- Per-claim size limits and several databases on one disk, unlike a statically mounted whole-disk local PV.
- Another storage add-on to operate beside NFS CSI and Longhorn.
- Expanding a volume needs a pod restart: after a PVC edit the claim reports `FileSystemResizePending` until the pod is recreated (tested: 1 GiB to 2 GiB, data preserved). Rolling CloudNativePG instances covers this.
- Capacity tracking relies on `WaitForFirstConsumer`; nodes with different volume-group sizes are fine, but size every PVC to fit the smallest node.
- Delete PVCs before uninstalling the driver. Removing the driver first leaves an orphaned logical volume and a stale kubelet mount that must be cleaned by hand (`umount`, then `lvremove`).
- Snapshot CRDs and the snapshot controller are installed by this chart, so another snapshot controller (for example Longhorn's) must not be added. No snapshot classes are configured, and restore from snapshots of thick volumes is unsupported by the driver.

## Related notes

- [[ADR-0005 - Phased bare-metal k0s cluster]]
- [[k0s]]
- [[Open Questions]]
