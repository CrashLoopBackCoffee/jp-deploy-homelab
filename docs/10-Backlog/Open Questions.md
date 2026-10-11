---
tags:
  - homelab
  - backlog
type: backlog
status: active
created: 2026-03-20
updated: 2026-10-03
---

# Open Questions

## DNS / DHCP

- What is the cleanest integration pattern between dnsmasq, Unbound, and AdGuard on OPNsense?
- Where should local hostnames be authored and synchronized from?

## Network

- What is the canonical VLAN-to-subnet and IPv6 allocation map? (CoRE sub-structure to be confirmed — see [[VLANs]])
- Sodola API investigation — does it have any programmable interface?
- GS308EPP VLAN trunk details — which VLANs on which ports?
- OPNsense SIP proxy vs FRITZbox direct registration to VoIP provider
- Which switch platform provides the best balance of trust, firmware quality, thermals, port mix, and power draw?
- Where should SFP+ be mandatory, where is RJ45 10G acceptable, and which links should use DAC, fiber, or copper?

## VPN

- What is the final documented root cause for the WireGuard floating client handshake failure?

## Platform

- Map the four Ryzen systems to Nodes 1–3 and the separate Proxmox host; confirm per-host CPU, RAM, NICs, OS, and management access.
- Map Nodes 2 and 3, their disks, and node addresses. For Phase 3, choose a fault-tolerant TCP load balancer and VIP to replace the Phase 1 API endpoint `10.10.8.1`.
- Configure Longhorn backups (target and schedule) and storage-class policy beyond the single-replica default (see [[ADR-0014 - Longhorn on a dedicated ext4 data disk]]), including coexistence with the NFS CSI driver; define per-host scheduling for CloudNativePG on the `openebs-lvm-postgres` class.
- Design and test Paperless migration from the current Bitnami PostgreSQL release to CloudNativePG, including distinct-host placement, replication policy, and off-node backup/restore retention.
- See [[ADR-0005 - Phased bare-metal k0s cluster]] for the accepted staged topology and remaining implementation prerequisites.
- NetBox sync tooling — `netbox-sync` or custom Python script?

## Documentation Gaps

- Full hardware inventory with purchase status
- Service inventory under `4jp.de`
- DNS zone and naming conventions
- Document and run the three-node etcd, Longhorn, PostgreSQL, and node-failure recovery acceptance tests before declaring control-plane HA.
- Per-service operations runbooks

## Operations Backlog

- Capture recurring troubleshooting commands as runbooks
- Document QNAP 10G module loading workaround (see [[Host Hardware Notes]])
- Document k0s and etcd recovery runbook (partial: see [[Runbook - k0s Recovery]])
