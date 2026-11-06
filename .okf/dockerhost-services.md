---
type: Concept
title: Services on dockerhost and the move to k0s
description: What ran on the host dockerhost (powered off 2026-11-06), the migration status per service, and where its archive lives on the QNAP (ADR-0054).
timestamp: 2026-11-06T00:00:00Z
tags: [homelab, dockerhost, migration, backup, risk]
resource: /Users/alten/Documents/dockerhost
---

# The starting point: no backup

`dockerhost` (`192.168.178.125`, Ubuntu, Ansible repository `/Users/alten/Documents/dockerhost`, up 236 days on 2026-10-17, root disk 215 GB of 503 GB used) runs everything below from Docker Compose projects in `/opt/<service>`. **It has no backup at all** (stated by the user, 2026-10-18): all data sits on a single SSD, so one disk failure would lose every service on it, including the NetBox inventory.

# Why moving a service is already a gain

On k0s a service's data exists in two places: on the node (an LVM volume for PostgreSQL, a Longhorn volume for files) and on the QNAP's RAID5 volume through QuObjects. CloudNativePG archives base backups and WAL (restore and time-targeted PITR verified, ADR-0017, ADR-0018), and Longhorn's nightly recurring job backs up every volume that has no explicit job group (restore verified 2026-10-17). The encrypted HBS 3 job to the remote NAS follows soon and covers all services at once.

So the rule "no application database migrates before the HBS 3 off-site copy is verified" is **lifted for services moving off `dockerhost`** (ADR-0018, amended 2026-10-18), and no service needs an own extra off-site copy for that reason (ADR-0028). Limits to remember: RAID5 protects against a disk failure, not against deletion, ransomware, a QNAP failure or a fire, and until HBS 3 runs the QNAP holds the only copy besides the node.

# Inventory (from the read-only discovery of 2026-10-17)

| Service | What it is | State |
| --- | --- | --- |
| Monitoring stack (Prometheus, Alertmanager, Grafana, Loki, Promtail, cAdvisor, blackbox, fritz-exporter) | Legacy monitoring, Ansible role `monitoring` | **Retired 2026-11-05/06** (ADR-0054): history backfilled into Mimir, raw TSDB archived ([[legacy-monitoring-migration]], ADR-0023) |
| `jpspeedtest` (systemd) | Speed test every 30 minutes into InfluxDB | Replaced by the in-cluster exporter (ADR-0027); **removed from `dockerhost` on 2026-11-01** (unit, `/opt/monitoring/speedtest`, Ansible tasks; sources archived in `backups/dockerhost/workstation-legacy/dockerhost-legacy-speedtest`) |
| Tandoor | Recipes; `postgres:17-alpine`, `ghcr.io/tandoorrecipes/recipes:latest` (with nginx inside), `adminer` | **Moved** to k0s on 2026-10-18 (ADR-0028, [[tandoor]]); **removed from `dockerhost` on 2026-10-28** (stage 2) |
| NetBox 4.2 | Inventory at `netbox.4jp.de`; community `netbox-docker` layout in `/opt/netbox` (`netbox-netbox-1`, `netbox-netbox-housekeeping-1`, `netbox-postgres-1` with PostgreSQL 17.11, `netbox-redis-cache-1`; no worker; image `v4.2-3.2.0`) | **Moved** to k0s on 2026-10-20 as NetBox 4.7.3 (ADR-0030, [[netbox]]); **removed from `dockerhost` on 2026-10-28** (stage 2) |
| InfluxDB 1.8.6 | Databases `vzlogger`, `home_assistant`, `node`, `default`, `_internal` (power meters, coffee, shutters, shellies) | **Moved** to k0s on 2026-11-01 (ADR-0043, [[influxdb]]); **removed from `dockerhost` on 2026-11-01** (container, image, `/opt/influxdb`, unit, Ansible role). Final portable backups of `vzlogger`, `home_assistant`, `node` and `default` (5.4 GB, 624 files, checksums equal) are in `backups/dockerhost/workstation-legacy/dockerhost-legacy-influxdb-archive` on the QNAP (verified 2026-11-05, ADR-0054) |
| mosquitto, `mqtt2influxdb` | MQTT broker and its bridge into InfluxDB | **Replaced** by Home Assistant's Mosquitto add-on plus Telegraf on k0s (ADR-0045, [[influxdb]]); **stopped 2026-11-03 09:30Z** (units disabled, `docker update --restart=no`, containers `Exited`). Config and `mosquitto.db` are archived in `host/opt-configs.tar.zst` (ADR-0054) |
| `tesla-logger` | With its own Grafana 10.0.1 and MariaDB 10.4.7 | **Moved** to k0s on 2026-10-28 (ADR-0040, [[teslalogger]]); **removed from `dockerhost` on 2026-10-31** (stage 2) |
| Portainer | Docker UI | **Stopped and disabled 2026-11-06** (G2, ADR-0054); `portainer.db` archived in `host/opt-configs.tar.zst` |
| Traefik v3.2 | Reverse proxy with Cloudflare DNS-01 for `*.4jp.de` | **Stopped 2026-11-06** (G2, ADR-0054); `acme.json` archived in `host/opt-configs.tar.zst` |
| Watchtower | Keeps `latest` images current, also scraped by the legacy Prometheus | **Stopped 2026-11-05** (G1) and disabled 2026-11-06 (G2) |
| Home Assistant | Role existed, **no container ran** | **Removed from `dockerhost` on 2026-10-31** (`/opt/home-assistant`, 78 GB of which 77 GB were 2025 backups, the disabled unit, the Ansible role and playbook); config archived as `backups/dockerhost/workstation-legacy/dockerhost-legacy-home-assistant-config.tar.gz` (without `config/backups`); the live Home Assistant runs on Proxmox |

# Decommissioned (2026-11-06, ADR-0054)

`dockerhost` (`192.168.178.125`) is **powered off**; the user reported on 2026-11-06 that the disk wipe is done or under way (not verified by the agent), so the cold fallback is gone and the QNAP archive is the only copy. Nothing points at the host any more: the 10 Cloudflare records, the Wazuh `/32`, the NetBox IP, the workstation SSH block and `known_hosts` lines are gone; the NetBox device is `offline`.

Archive: QNAP share `backups`, directory `dockerhost` (SMB mount `/Volumes/backups/dockerhost/` on the workstation), about 51 GB with SHA-256 manifests (all `OK`):

- `host/`: `prometheus-tsdb.tar.zst` (42.9 GB), `monitoring-other-data`, `opt-configs`, `home-alten`, `root`, `etc`, `etc-systemd-units`, `var-log`, `docker-images` (all `.tar.zst`), `inventory/` (docker, systemd, dpkg, network and disk listings, `restart-policies.txt`, `cloudflare-records.tsv`) and `MANIFEST.sha256`. Excluded as reproducible: `/opt/go`, `/opt/poetry`, `~/.cache`, `~/.vscode-server`.
- `workstation-legacy/`: the former `~/dockerhost-legacy-*` files (InfluxDB archive, TeslaLogger backup, Home Assistant config, speedtest, Tandoor and NetBox config) with a manifest.
- `ansible/`: `dockerhost-ansible.bundle`, a git bundle of `/Users/alten/Documents/dockerhost` (kept read-only on the workstation).

The archive holds plaintext secrets (compose environment, `acme.json`, `.netrc`); keep the share private. Disabled units: `monitoring`, `reverse-proxy`, `portainer`, `watchtower`, `node_exporter`; all 13 containers have restart policy `no`. To revive the host: power it on, `systemctl enable --now` the units and restore the policies from `inventory/restart-policies.txt`.

# Risks

- The archive, the backfilled history in Mimir's `mimir-metrics` bucket and the raw TSDB all sit on the same QNAP; there is no off-site copy and the user declined one (ADR-0057). The QNAP S3 also produced damaged Mimir blocks (ADR-0056).
- Each migration needs its own decision on how state moves (dump and restore, volume copy, or fresh install) and must keep the legacy instance stopped but intact until the new one is verified.

Related: [Tandoor](./tandoor.md), [Retiring the legacy dockerhost monitoring stack](./legacy-monitoring-migration.md), ADR-0018, ADR-0023, ADR-0028.
