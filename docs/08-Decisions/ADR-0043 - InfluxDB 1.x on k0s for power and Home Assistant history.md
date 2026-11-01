---
tags:
  - homelab
  - adr
  - kubernetes
  - influxdb
  - grafana
type: adr
status: accepted
date: 2026-11-01
created: 2026-11-01
updated: 2026-11-01
adr: 43
---

# ADR-0043 - InfluxDB 1.x on k0s for power and Home Assistant history

## Status

Accepted on 2026-11-01. The stack is applied and the data is restored; the cutover steps are tracked in `.okf/influxdb.md`.

## Context

`dockerhost` still runs InfluxDB 1.8.6 (9 GB, authentication off). Two databases are live: `vzlogger` (2.4 GB; `current_power`, `meter1`, `meter2`, `bkw_current_power`, `rolladen_position`, since 2018) and `home_assistant` (6.2 GB; written by Home Assistant on Proxmox at `192.168.178.122`). `node`, `default` and `_internal` have not been written since 2022.

The smart meter (Tasmota `tasmota_629634`), the balcony power plug and the roller shutter publish to mosquitto on `dockerhost:1883`; `mqtt2influxdb` (on `dockerhost`) writes the points into `vzlogger`. The legacy Grafana dashboards `Power`, `Power small` and the InfluxDB part of `Solax` read these databases. ADR-0023 left them on `dockerhost` until the LAN decision; the cluster still cannot reach `192.168.178.0/24`, but the writers can reach Traefik's address `10.10.88.1` (verified from `dockerhost` for the TeslaLogger names), which is all a push-only writer needs.

## Decision

- **InfluxDB 1.11 on k0s** (`services/influxdb`, Deployment `Recreate`, one 20 Gi Longhorn volume), not InfluxDB 2/3 and not a conversion to Prometheus. The writers (Home Assistant, `mqtt2influxdb`) and the dashboards speak InfluxQL; 1.x keeps the history, needs no query rewrite and Renovate is capped below 2.
- **Same exposure as before:** one name `influx.4jp.de` through Traefik with the cluster wildcard certificate, in-cluster as `http://influxdb.influxdb.svc:8086`. The HTTP interface keeps authentication off, as on the legacy instance; the RPC port stays on localhost (backups run inside the Pod).
- **Data by portable backup:** `influxd backup -portable` of `vzlogger` and `home_assistant` on the legacy instance, `influxd restore -portable` on k0s while the legacy instance keeps running. At the cutover a second backup from the first one's time closes the gap. `node`, `default` and `_internal` are not carried over; they stay in the legacy files until stage 2.
- **Cutover by DNS and two config changes:** the Cloudflare record `influx.4jp.de` moves to Traefik's address (ADR-0029); `mqtt2influxdb` on `dockerhost` gets `host: influx.4jp.de`, `port: 443`, `ssl: true`; Home Assistant's InfluxDB integration gets the same (the user changes this one).
- **Dashboards in the new Grafana:** two datasources (`InfluxDB vzlogger`, `InfluxDB home_assistant`) and the legacy dashboard `Power` (uid `tBUT3NfGk`, so the old link pattern keeps working) provisioned from code. `Power small` is not carried over: it shows a subset of the same four measurements in old Angular panels (`graph`, `singlestat`). The InfluxDB part of `Solax` (database `home_assistant`) waits for a decision.
- **Mosquitto and `mqtt2influxdb` stay on `dockerhost`** for now; moving them is a separate decision.

## Consequences

- The MQTT path still depends on `dockerhost`; retiring it needs mosquitto and `mqtt2influxdb` on k0s and the Tasmota/Shelly devices repointed.
- Any LAN host can still write to or query InfluxDB without credentials (same exposure as the legacy instance, now behind Traefik). Enabling authentication needs credentials in Home Assistant, `mqtt2influxdb` and the Grafana datasources; not part of this change.
- Backups: the Longhorn volume backup (nightly). No logical dump is scheduled; a portable backup can be taken in the Pod at any time.
- Writers that still use `192.168.178.125:8086` lose their target once the legacy container stops; the tcpdump on 2026-11-01 found only Home Assistant and the local bridges.

## Alternatives considered

- Converting the power data to Prometheus/Mimir: needs a new exporter, a one-time backfill and a different Home Assistant integration; the history stays in InfluxQL anyway (rejected by the user, 2026-11-01).
- Archiving and dropping the dashboards: loses the live power view.
- Plain HTTP on a second entry point for the LAN writers: no benefit, both writers support TLS.

## Related notes

- [[ADR-0023 - Retire the legacy dockerhost monitoring stack]]
- [[ADR-0027 - Speedtest exporter and legacy dashboards]]
- [[ADR-0029 - Service names as Cloudflare A records]]
- [[ADR-0040 - Migrate TeslaLogger to k0s]]
