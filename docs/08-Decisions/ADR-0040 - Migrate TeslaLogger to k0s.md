---
tags:
  - homelab
  - adr
  - kubernetes
  - teslalogger
  - mariadb
type: adr
status: accepted
date: 2026-10-28
created: 2026-10-28
updated: 2026-10-28
adr: 40
---

# ADR-0040 - Migrate TeslaLogger to k0s

## Status

Accepted on 2026-10-28. The stack is applied, the final import is done and DNS points at k0s; verification is tracked in `.okf/teslalogger.md`.

## Context

TeslaLogger (bassmaster187/TeslaLogger) ran on `dockerhost` from `/opt/tesla-logger` (git clone, mono layout, self-updated to 1.63.20.4, MariaDB 10.4.7) and **`dockerhost` has no backup** ([[ADR-0028 - Migrate Tandoor to k0s]]). Missed drives cannot be backfilled. The legacy database has 26 tables, about 80 MB (175k `pos` rows, one car), charset `utf8mb4`, collation `utf8mb4_unicode_ci`. The `/admin/` panel is at `tesla-logger.4jp.de`, Grafana at `grafana.tesla-logger.4jp.de`.

## Decision

- **Upstream's NET8 images** `bassmaster187/teslalogger`, `-webserver` and `-grafana` on a dedicated workspace `services/teslalogger`. All three share one version tag (one config field; Renovate `versioning=loose`).
- **MariaDB 10.11 LTS** through [[ADR-0039 - MariaDB operator on k0s]]. The operator supports 10.6 or newer, so the upstream pin 10.4.7 cannot stay; TeslaLogger runs on 10.11.8 since 2024 (upstream issue 1040). The dump and restore is the upgrade. Renovate is capped below 10.12. If TeslaLogger misbehaves on 10.11 the rollback is the legacy stack; 11.x is not tried.
- **Hardcoded names and credentials.** The app, its PHP panel and the Grafana datasource use host `database`, user `root`, password `teslalogger`, database `teslalogger`, and call `http://teslalogger:5000` and `http://grafana:3000`. So the MariaDB resource is named `database`, the Services `teslalogger`, `grafana` and `webserver`, all in one namespace, and the root password is the literal `teslalogger`. The NetworkPolicy from `utils.mariadb` is what contains this credential; it is not a secret.
- **One Pod for teslalogger, webserver and Grafana.** They share `/tmp` (PHP sessions, settings copies) and TeslaLogger writes Grafana's dashboards and plugins on every start. One RWO volume `teslalogger` (5 Gi) holds `/tmp`, `data`, `backup` (its own nightly dumps), invoices and Grafana's database as subPaths; dashboards and plugins are `emptyDir`s.
- **An init container prepares the volume.** Docker mode is detected by marker files in the image's own `/tmp`, which the volume hides, so the init container writes them, sets `/tmp` to mode 1777, hands Grafana's directory to uid 472 and copies the Grafana plugins before Grafana starts (it loads plugins only at startup).
- **Fresh Grafana database with a generated admin password** (Secret `grafana-admin`). The legacy one only had `admin`; all 42 dashboards are provisioned by TeslaLogger.
- **Own certificate for `grafana.tesla-logger.4jp.de`:** the cluster wildcard covers only `*.4jp.de`. The admin panel uses the wildcard. Port 5000 is not routed; the panel proxies it inside the cluster.
- **Updates come from Renovate.** The in-app update button and the Grafana restart need `docker.sock` and Watchtower; on k0s they only log errors (`Watchtower update error`, `Error getting Docker container image`), which are expected.
- **`replicas` is a config gate.** TeslaLogger's listener opens only after its DB connect and schema update and must not start on an empty database, so the stack is created with `replicas: 0`, the data is imported, then the gate is removed.
- **Not carried over:** Grafana's database, `bin/backup` (dumps of the same DB), MQTT (disabled). Carried: `settings.json`, `encryption.txt`, `geofence-private.csv`, `nosharedata.txt`.
- **Alerts:** `teslalogger-down` (warning; kube-state-metrics, no metrics endpoint exists) and the generic `mariadb-backup-stale`.
- **Cutover by DNS** with the records managed by the stack afterwards ([[ADR-0029 - Service names as Cloudflare A records]]). The legacy containers are stopped, not deleted; removal is stage-2 work that needs the user's approval.

## Consequences

- **Only one logger may run at a time**: two would poll the car, and a token refresh on one side may force a new login on the other. After a rehearsal the gate goes back to 0.
- Between `docker stop` of the legacy logger and k0s being ready no drives are logged; do the final run while the car is parked.
- **The `natel-discrete-panel` plugin is Angular**, which Grafana 13.2.4 (the upstream image) refuses to load; dashboards using it show a plugin error. Upstream's choice; not fixable here without leaving the image (follow-up: check which dashboards use it).
- The database is covered by the operator's logical dumps, the nightly Longhorn backup of its volume, and TeslaLogger's own nightly dump in `/etc/teslalogger/backup`. The state volume is covered by Longhorn. Retention of the logical dumps is not enforced (ADR-0039).

## Alternatives considered

- Plain MariaDB Deployment (rejected for the operator, ADR-0039); MariaDB 10.4.7 (below the operator's minimum, end of life).
- Separate Pods for webserver and Grafana: needs shared RWX volumes for `/tmp` and the Grafana content for no gain.
- Renaming the Grafana host below `*.4jp.de` to use the wildcard: breaks bookmarks; the user kept the name.
- Cluster-wide wildcard for `*.tesla-logger.4jp.de`: more ACME surface than one certificate.

## Related notes

- [[ADR-0028 - Migrate Tandoor to k0s]]
- [[ADR-0030 - Migrate NetBox to k0s]]
- [[ADR-0039 - MariaDB operator on k0s]]
