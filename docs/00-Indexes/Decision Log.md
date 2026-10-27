---
tags:
  - homelab
  - index
  - adr
type: index
status: active
created: 2026-03-20
updated: 2026-10-26
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
| [[ADR-0017 - First CloudNativePG cluster and QuObjects recovery]] | accepted | Single-instance `postgres-pilot` with Barman plugin backups and WAL archiving to QuObjects; latest-state restore verified |
| [[ADR-0018 - PostgreSQL PITR and off-site recovery acceptance]] | accepted | Time-targeted PITR verified on the pilot; encrypted HBS 3 off-site copy deferred and unverified |
| [[ADR-0019 - LGTM observability stack on k0s]] | accepted | Loki, Mimir (blocks in QuObjects), Grafana and Alloy in a separate `observability` Pulumi project; Grafana at `g.4jp.de`, alerts provisioned from code and delivered by Pushover |
| [[ADR-0020 - Paperless fresh install with Nextcloud off-site backup]] | accepted | Fresh Paperless install with local accounts, a dedicated CloudNativePG database, restic over WebDAV to an off-site Nextcloud and a QNAP NFS intake share; Paperless-specific go-live gate instead of waiting for HBS 3 |
| [[ADR-0021 - Paperless single sign-on through the shared Authentik]] | accepted | Paperless signs in through the existing Authentik at id.jaypee.solutions (identity broker for Mailcow), groups `paperless` and `paperless-admins` managed by an AX41 blueprint, upgrade to Paperless 3.3.1 for superuser mapping; local login stays |
| [[ADR-0022 - CloudNativePG base backups at 21:00 UTC]] | accepted | Base backups of `postgres-pilot` and `paperless-db` move from 03:00 to 21:00 UTC (23:00 CEST) to avoid the QNAP's HBS sync window; revisit at the end of DST |
| [[ADR-0023 - Retire the legacy dockerhost monitoring stack]] | accepted | Two-stage retirement; stage 2 waits for LAN targets, with Prometheus history backfilled to Mimir |
| [[ADR-0024 - QNAP syslog into Loki]] | accepted | Receive QNAP syslog in RFC 5424/3164 over TCP/UDP through Alloy and Loki |
| [[ADR-0025 - Probe and scrape targets from 1Password]] | accepted | Keep probe/scrape targets and credentials in three Homelab 1Password items, rendered into an Alloy Secret |
| [[ADR-0026 - Mimir series budget and API server buckets]] | accepted | Drop unused API-server histogram buckets instead of raising Mimir's series limit |
| [[ADR-0027 - Speedtest exporter and legacy dashboards]] | accepted | Deploy the speedtest exporter and port selected legacy dashboards into the observability stack |
| [[ADR-0028 - Migrate Tandoor to k0s]] | accepted | Move Tandoor from dockerhost to k0s with CloudNativePG and Longhorn; keep local accounts and defer extra off-site backup |
| [[ADR-0029 - Service names as Cloudflare A records]] | accepted | Manage service DNS names as unproxied Cloudflare A records pointing to Traefik |
| [[ADR-0030 - Migrate NetBox to k0s]] | accepted | Migrate NetBox to the official Helm chart and CloudNativePG on k0s |
| [[ADR-0031 - Pulumi access token in the Homelab vault]] | accepted | Keep the Pulumi Personal Access Token item in Homelab so the service account can read it |
| [[ADR-0032 - Emergency Pushover priority for critical alerts]] | accepted | Route critical alerts through emergency-priority Pushover and keep normal alerts at priority 0 |
| [[ADR-0033 - Tandoor 2.7.1 superuser email migration]] | accepted | Preserve the existing unverified address and add the migration-compatible verified primary fallback |
| [[ADR-0037 - Wazuh security monitoring on k0s]] | proposed | Wazuh 4.14.9 on k0s for inventory and vulnerability management, Grafana integration, native agents, Trivy Operator |
| [[ADR-0038 - OPNsense metrics and syslog into the LGTM stack]] | accepted | os-node_exporter plus API exporter, RFC 5424 syslog on port 1516 with parsed filterlog, generated dashboards, three alerts |
