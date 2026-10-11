---
type: Host
title: k0s0 (Node 1 of the bare-metal k0s cluster)
description: Identity, access, disks, and preparation state of the first k0s node, including how it was bootstrapped.
timestamp: 2026-10-11T15:00:00Z
tags: [homelab, k0s, node, storage, ansible]
---

# Identity

| Item | Value |
| --- | --- |
| Hostname | `k0s0` |
| Address | `10.10.8.1/16`, VLAN 10 (CoRE), gateway `10.10.0.1`; DHCP client with a static mapping in OPNsense; no DNS record |
| Hardware | Ryzen, 12 threads, 31 GiB RAM, NIC `enp6s0` |
| OS | Ubuntu Server 24.04 LTS (`docs/08-Decisions/ADR-0006 - Ubuntu Server 24.04 LTS for k0s nodes.md`) |
| k0s | `v1.36.4+k0s.1`, one `controller+worker` with `noTaints`, k0s-managed etcd, API `https://10.10.8.1:6443` (`docs/08-Decisions/ADR-0008 - Phase 1 k0s API endpoint.md`) |

# Access

- Interactive account `alten` (key with fingerprint confirmation, sudo with password) is for humans only.
- Automation uses the `k0sctl` account: no password, authorized key `k0s` from the SSH agent, passwordless sudo (`docs/08-Decisions/ADR-0007 - Dedicated k0sctl automation account.md`). The same account is used by Ansible.
- The administrator machine's `known_hosts` needs all three host key types (ed25519, rsa, ecdsa) for `10.10.8.1`, otherwise k0sctl fails with a host-key mismatch.
- sshd still allows password authentication globally; the `k0sctl` user has no password. Hardening is not done.

# Disks

| Device | Model / serial | Size | Role |
| --- | --- | --- | --- |
| `sda` | Samsung SSD 750, `S33SNWBH885401A` | 232.9 GiB | OS, k0s, etcd. LVM `ubuntu-vg`; root volume 100 GiB, about 130 GiB free in the VG |
| `nvme1n1` | WDC PC SN520, `1904D9802882` | 238.5 GiB | Node-local PostgreSQL: LVM volume group `postgres`, managed by OpenEBS LVM LocalPV (`docs/08-Decisions/ADR-0009 - LVM-backed local volumes for PostgreSQL.md`) |
| `nvme0n1` | Kingston SA2000M8, `50026B7685019679` (by-id `nvme-KINGSTON_SA2000M81000G_50026B7685019679`) | 931.5 GiB | Longhorn data disk: whole-disk ext4 labelled `longhorn`, mounted at `/var/lib/longhorn` (`docs/08-Decisions/ADR-0014 - Longhorn on a dedicated ext4 data disk.md`) |

Both NVMe drives previously held a throwaway Proxmox install and a Windows install; the user approved wiping them on 2026-10-10. Never address disks by `/dev/sdX` or `/dev/nvmeX`: use by-id paths and check serials.

# Preparation done outside Pulumi

- Swap is disabled (`/swap.img` commented out in `/etc/fstab`), because kubelet does not start with swap by default.
- `open-iscsi` is installed and `iscsid.socket` is active (Longhorn prerequisite).
- The `postgres` volume group is created by `services/k0s/ansible/prepare-postgres-storage.yaml`, which resolves the disk by by-id path, asserts its serial, and uses `community.general.lvg` (idempotent, refuses disks with existing signatures).
- The Kingston disk is prepared by `services/k0s/ansible/prepare-longhorn-storage.yaml` (applied 2026-10-11): serial assert, ext4 label `longhorn`, `fstab` mount by by-id path with `nofail`, `nfs-common`, and an `sd*` blacklist in `/etc/multipath.conf` so `multipathd` (active by default) leaves Longhorn devices alone.
- k0s was installed by `k0sctl apply` from `services/k0s/k0sctl/cluster.yaml`; `k0sctl apply --dry-run` is a useful preview.
- NetBox documents `k0s0` since 2026-10-11 (device, `enp6s0` with MAC, primary IPv4 `10.10.8.1/16`, platform Ubuntu Server 24.04 LTS). Verified read-only with `nbcli`'s Python and `pynetbox` (NetBox 4.2): one device, one IP record assigned to the interface, prefix `10.10.0.0/16` linked to VLAN 10. The MAC is a separate MAC object and not yet set as the interface's primary MAC.

# Open items

- No DNS record for `k0s0`; tools use the IP.
- Nodes 2 and 3 are unmapped. If `/var/lib/longhorn` is ever unmounted, Longhorn would write replicas to the root volume; check `findmnt /var/lib/longhorn` after disk incidents.
- See [the cluster plan](./k0s-cluster-plan.md) for phases and HA gates.
