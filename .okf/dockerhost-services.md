---
type: Concept
title: Services on dockerhost and the move to k0s
description: What runs on the single, unbacked-up host dockerhost, why moving a service to k0s already improves its protection, and the migration status per service.
timestamp: 2026-10-18T00:00:00Z
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
| Monitoring stack (Prometheus, Alertmanager, Grafana, Loki, Promtail, cAdvisor, blackbox, fritz-exporter) | Legacy monitoring, Ansible role `monitoring` | Being retired, stage 1 phases 1 to 3 done ([[legacy-monitoring-migration]], ADR-0023) |
| `jpspeedtest` (systemd) | Speed test every 30 minutes into InfluxDB | Replaced by the in-cluster exporter (ADR-0027) |
| Tandoor | Recipes; `postgres:17-alpine`, `ghcr.io/tandoorrecipes/recipes:latest` (with nginx inside), `adminer` | **Next**: stack written, not applied (ADR-0028, [[tandoor]]) |
| NetBox 4.2 | Inventory at `netbox.4jp.de` (PostgreSQL, Redis) | Not decided. It is the inventory the agent uses, so its loss would hurt most |
| InfluxDB 1.8.6 | Databases `vzlogger`, `home_assistant`, `node`, `default`, `_internal` (power meters, coffee, shutters, shellies) | Not decided. Feeds the `Power` dashboards, which stay legacy until the LAN work |
| mosquitto, `mqtt2influxdb` | MQTT broker and its bridge into InfluxDB | Not decided |
| `tesla-logger` | With its own Grafana 10.0.1 and MariaDB | Not decided |
| Portainer | Docker UI | Not decided; it manages the host that is being emptied |
| Traefik v3.2 | Reverse proxy with Cloudflare DNS-01 for `*.4jp.de` | Goes when the last routed service has moved |
| Watchtower | Keeps `latest` images current, also scraped by the legacy Prometheus | Goes with the host |
| Home Assistant | Role exists, **no container runs** | Dead; removal approved in principle for stage 2 |

# Risks while services are still there

- Everything in the table, and the legacy history (the Prometheus TSDB of about 93 GB, Grafana's 515 MB database with six dashboards that exist only there, Loki, InfluxDB), exists exactly once. Copying Grafana's database and the InfluxDB databases to the QNAP is cheap and is the user's call (see ADR-0023, update 2026-10-18).
- Each migration needs its own decision on how state moves (dump and restore, volume copy, or fresh install) and must keep the legacy instance stopped but intact until the new one is verified.

Related: [Tandoor](./tandoor.md), [Retiring the legacy dockerhost monitoring stack](./legacy-monitoring-migration.md), ADR-0018, ADR-0023, ADR-0028.
