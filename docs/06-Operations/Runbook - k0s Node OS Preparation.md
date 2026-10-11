---
tags:
  - homelab
  - runbook
  - k0s
  - ubuntu
type: runbook
status: draft
created: 2026-10-03
updated: 2026-10-06
---

# Runbook - k0s Node OS Preparation

## Purpose and scope

Prepare the operating system on the first bare-metal k0s node only. This procedure does not bootstrap k0s, install Kubernetes add-ons, or modify the Longhorn or PostgreSQL disks. The proposed OS is Ubuntu Server 24.04 LTS; see [[ADR-0006 - Ubuntu Server 24.04 LTS for k0s nodes]].

## Stop conditions

Do not start installation until all of these are known:

- Which physical Ryzen system is Node 1, and whether its existing disks contain data that must be preserved.
- Disk identities and existing contents of the node's drives. Never assign roles by capacity alone. Node 1's drives are recorded below.
- The approved hostname, stable node address, DNS, management network, and the administrator machine allowed to SSH to the node. Node 1 is `k0s0` at `10.10.8.1/16` on VLAN 10 with no DNS record yet; the address is DHCP-assigned today.

Installing Ubuntu erases the selected system disk. Back up anything that must be retained. If disk identities are ambiguous, stop and inventory the hardware; never guess a `/dev/sdX` device name.

## Install Ubuntu Server

1. Download the official Ubuntu Server 24.04 LTS amd64 image and verify it using Ubuntu's published checksum.
2. Boot the Node 1 installer. Choose the minimal server installation with no desktop environment.
3. Configure networking only with the approved address and DNS details. Use the selected hostname from the host inventory.
4. Select only the explicitly approved and verified OS target, and preserve at least 15% free disk space for the k0s worker role. Do not partition, format, or assign the data drives. If practical, disconnect them until the OS install is complete. (Node 1 used its 232.9 GiB SATA SSD.)
5. Create the administrative user and select the installer's OpenSSH Server option. Install the administrator's public key and restrict SSH reachability to the management network.
6. Complete installation, remove the install media, and boot from the SATA system disk.

## First-boot checks

1. Apply current Ubuntu security updates and reboot if required.
2. Confirm the hostname, stable address, DNS resolution, and time synchronization match the approved network plan.
3. From the authorized management machine, verify SSH key access and administrative privilege escalation. k0sctl requires a Linux SSH user that is root or has passwordless `sudo`/`doas`; prefer a dedicated admin account with key-based SSH restricted to the management network.
4. Confirm the data drives are not part of the OS volume. Record the model/serial, interface, and capacity of every drive for the storage inventory.
5. Do not install k0s, kubelet, Docker, or a separate container runtime manually. k0sctl will install/manage k0s after the host and API endpoint details are ready.

## Node 1 as built (`k0s0`, 2026-10-10)

- Ubuntu Server 24.04.4 LTS, 12 CPU threads, 31 GiB RAM, NIC `enp6s0`, `10.10.8.1/16`, gateway `10.10.0.1`. The node uses DHCP; OPNsense has a static mapping for the address.
- OS disk: `sda`, Samsung SSD 750 (SATA), serial `S33SNWBH885401A`, 232.9 GiB. LVM layout with a 100 GiB root volume (12% used); about 130 GiB of the volume group is unallocated and can be added to root if needed.
- `nvme0n1`: Kingston SA2000M8, serial `50026B7685019679`, 931.5 GiB. A former Proxmox install (an empty experiment) was wiped on 2026-10-10; the disk is blank and reserved for Longhorn.
- `nvme1n1`: WDC PC SN520, serial `1904D9802882`, 238.5 GiB. A leftover Windows install was wiped on 2026-10-10. It is now the single physical volume of the LVM volume group `postgres` (238.47 GiB free, no logical volumes), created by `services/k0s/ansible/prepare-postgres-storage.yaml` ([[ADR-0009 - LVM-backed local volumes for PostgreSQL]]).
- Administration uses the `k0sctl` account from [[ADR-0007 - Dedicated k0sctl automation account]]; `open-iscsi` is installed and `iscsid.socket` is active.
- Swap is disabled (`/swap.img` is commented out in `/etc/fstab`) because kubelet does not start with swap enabled by default.
- The administrator machine's `known_hosts` needs all three host key types (ed25519, rsa, ecdsa) for `10.10.8.1`; k0sctl fails with a host-key mismatch if only ed25519 is present.
- `k0sctl apply --dry-run` against `services/k0s/k0sctl/cluster.yaml` succeeded: it would install k0s `v1.36.4+k0s.1` as a controller with `--enable-worker=true --no-taints=true`. The installed `k0sctl` is `v0.30.1`; the latest release is `v0.33.1`.

## Before later cluster bootstrap

- Build the one-host k0sctl configuration from the confirmed host and network inventory. Use role `controller+worker`, `noTaints: true`, and the default k0s-managed etcd. Do not use role `single` or `--single`.
- Confirm the stable `spec.api.externalAddress` and routing plan before bootstrap; do not guess an API VIP or use the in-cluster MetalLB address for this purpose.
- Before deploying Longhorn, satisfy the requirements for the selected Longhorn version. The current installation guide requires `open-iscsi` and a running `iscsid` daemon for the V1 data engine; install the NFSv4 client only if the chosen Longhorn backup or RWX features need it.

## Completion criteria

Node 1 boots Ubuntu Server 24.04 LTS from the SATA system disk; the system has its hostname and working time synchronization, key-based SSH with the required sudo access via the `k0sctl` account, and a stable address. The two NVMe drives are blank. Node preparation is complete; k0s was bootstrapped afterwards with k0sctl (`services/k0s/k0sctl/cluster.yaml`), not by this runbook.

## Sources

- [Ubuntu Server download](https://ubuntu.com/download/server)
- [k0s tested operating systems](https://docs.k0sproject.io/stable/system-requirements/)
- [k0sctl SSH management and host prerequisites](https://docs.k0sproject.io/stable/k0sctl-install/)
- [Longhorn installation requirements](https://longhorn.io/docs/1.13.0/deploy/install/)
- [Ubuntu Server 24.04 installation system requirements](https://ubuntu.com/server/docs/reference/installation/system-requirements/)
