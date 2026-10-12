---
tags:
  - homelab
  - index
  - adr
type: index
status: active
created: 2026-03-20
updated: 2026-10-12
---

# Decision Log

| ADR | Status | Topic |
| --- | --- | --- |
| [[ADR-0001 - Use dnsmasq instead of Kea on OPNsense]] | accepted | DHCP service direction on OPNsense |
| [[ADR-0002 - Local domain and addressing baseline]] | accepted | Connectivity, domain, and addressing assumptions |
| [[ADR-0003 - Pet vs Cattle and IaC tooling]] | superseded | Historical tooling rationale; Proxmox and cluster placement replaced by ADR-0004 |
| [[ADR-0004 - Bare-metal k0s and external infrastructure scope]] | accepted | Bare-metal k0s; external Proxmox and service boundaries |
| [[ADR-0005 - Phased bare-metal k0s cluster]] | accepted | Three-node expansion-compatible k0s topology, rollout phases, HA gates, and storage intent |
| [[ADR-0006 - Ubuntu Server 24.04 LTS for k0s nodes]] | accepted | Ubuntu 24.04 host OS for k0s nodes |
| [[ADR-0007 - Dedicated k0sctl automation account]] | accepted | Passwordless-sudo `k0sctl` user with the agent-held `k0s` key |
| [[ADR-0008 - Phase 1 k0s API endpoint]] | accepted | `k0s0` (`10.10.8.1`) as the Phase 1 API endpoint |
| [[ADR-0009 - LVM-backed local volumes for PostgreSQL]] | accepted | LVM-backed local volumes on the dedicated PostgreSQL disk; provisioner open |
| [[ADR-0010 - Cloudflare account token for the Kubernetes stack]] | accepted | Account API token and `acme-email` replace the global key and email in the Kubernetes stack |
| [[ADR-0011 - LAN-first ingress and service cleanup]] | accepted | Cloudflare for DNS only; LAN-first, later Caddy on OPNsense; removed svn, obsidian, ollama, ingress |
| [[ADR-0012 - Local DNS records through dnsmasq on OPNsense]] | accepted | Pulumi creates local DNS records as dnsmasq host records, not Unbound overrides |
| [[ADR-0013 - 1Password service account for Pulumi]] | accepted | Read-only service account token loaded by `.envrc` replaces per-run biometric approval |
| [[ADR-0014 - Longhorn on a dedicated ext4 data disk]] | accepted | Longhorn on the whole Kingston NVMe (ext4, `/var/lib/longhorn`), one replica until node 2, installed as a Helm Release |
| [[ADR-0015 - Remove MinIO and the s3 workspace]] | accepted | MinIO is deprecated and the QNAP has its own deploy repo: removed `services/s3`, `pulumi-minio` and the legacy Mimir |
| [[ADR-0016 - QuObjects backup target and encrypted offsite copy]] | accepted | Local QNAP QuObjects S3 for Longhorn and PostgreSQL; second QNAP via client-side encrypted HBS 3 backup, pending validation |
