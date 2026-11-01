---
type: Service
title: InfluxDB 1.x on k0s (Pulumi, applied; cut over 2026-11-01 except Home Assistant)
description: InfluxDB 1.11 on k0s for the power meter and Home Assistant history, how the data was moved, what still writes to the legacy instance, and the remaining cutover steps (ADR-0043).
timestamp: 2026-11-01T09:20:00Z
tags: [homelab, kubernetes, influxdb, grafana, power, migration]
resource: https://app.pulumi.com/jaypee-solutions/influxdb/prod
---

# State

Stack `jaypee-solutions/influxdb/prod` (source `services/influxdb`), 12 resources: namespace `influxdb`, Deployment `influxdb` (`influxdb:1.11.8`, `Recreate`, uid 999), PVC `influxdb` (20 Gi Longhorn), Service `influxdb:8086`, IngressRoute `influx.4jp.de` (cluster wildcard certificate) and the Cloudflare A record `influx.4jp.de` (imported on 2026-11-01, now `10.10.88.1`). Authentication is off, as on the legacy instance. Renovate is capped below 2.

Data: databases `vzlogger` (2.4 GB, since 2018) and `home_assistant` (6.2 GB) restored from `influxd backup -portable` taken on the legacy instance at 2026-11-01T07:55:26Z. Counts of `current_power`, `meter1`, `meter2`, `bkw_current_power`, `rolladen_position`, `speedtest`, `W`, `V`, `A`, `Hz` and `%` up to 07:55:00Z and both series cardinalities (237 and 1191) are identical on both sides. `node`, `default` and `_internal` were not carried over.

New Grafana (`g.4jp.de`): datasources `InfluxDB vzlogger` and `InfluxDB home_assistant`, dashboard `Power` (uid `tBUT3NfGk`, vendored from the legacy Grafana as `assets/grafana/dashboards/power.json`, datasource rewritten). Queries through the Grafana API return data. `Power small` is not carried over (subset of `Power`, old Angular panels); the InfluxDB part of `Solax` is undecided.

# Data path

```
Tasmota meter / Shelly BKW / Shelly roller -> mosquitto dockerhost:1883 -> mqtt2influxdb (dockerhost) -> https://influx.4jp.de (k0s)
Home Assistant (Proxmox, 192.168.178.122) -> InfluxDB integration -> still the legacy instance until the user repoints it
```

`mqtt2influxdb` on `dockerhost` was switched on 2026-11-01 08:06 UTC (`host: influx.4jp.de`, `port: 443`, `ssl: true`, `verify_ssl: true`; backup of the old file at `~/config.yml.pre-k0s-influx` on the host). The meter publishes every 5 minutes; the first point after the switch (08:10:30Z) arrived on k0s.

# Facts that shaped the design

- The legacy writers are only Home Assistant (direct) and `mqtt2influxdb`; a tcpdump on `enp2s0` found no other LAN host, and Docker's NAT hides local sources (`172.18.0.1`).
- `mqtt2influxdb` supports `ssl` and `verify_ssl`; the python client sets the `Host` header from `host`, so the DNS name has to resolve to Traefik before it can be used (`10.10.88.1` as host does not route).
- Authentication was off before; the HTTP interface is now reachable by every LAN client through Traefik. Enabling it needs credentials in Home Assistant, `mqtt2influxdb` and the two Grafana datasources.
- Do not use `pkill -f` patterns that appear in the same shell command line.

# Remaining cutover

1. **User:** point Home Assistant's InfluxDB integration at `influx.4jp.de`, port 443, SSL on (verify on; the certificate is the Let's Encrypt wildcard). Until then Home Assistant keeps writing to the legacy instance on `dockerhost:8086`.
2. Close the gap: `influxd backup -portable -database <db> -start 2026-11-01T07:55:26Z` on the legacy container, restore into `<db>_gap` (`-db <db> -newdb <db>_gap`) on k0s, `SELECT * INTO <db>.autogen.:MEASUREMENT FROM <db>_gap.autogen./.*/ GROUP BY *`, drop `<db>_gap`, compare counts after the last legacy point.
3. Stop the legacy `influxdb_influxdb_1` (stage 2, user approval): remove `/opt/influxdb` (9 GB), the unit, role and playbook after an archive of the databases to the QNAP.
4. Later: mosquitto and `mqtt2influxdb` to k0s; decide on Solax's InfluxDB panels and `Power small`.

# Still to verify

Home Assistant's writes on k0s after the user's change, the gap fill, and a Longhorn backup of the `influxdb` volume after 02:00 UTC.
