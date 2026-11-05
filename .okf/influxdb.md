---
type: Service
title: InfluxDB 1.x on k0s (Pulumi, applied; cut over 2026-11-01)
description: InfluxDB 1.11 on k0s for the power meter and Home Assistant history, how the data was moved and the gap closed, and the remaining steps (ADR-0043).
timestamp: 2026-11-04T00:00:00Z
tags: [homelab, kubernetes, influxdb, grafana, power, migration]
resource: https://app.pulumi.com/jaypee-solutions/influxdb/prod
---

# State

Stack `jaypee-solutions/influxdb/prod` (source `services/influxdb`), 12 resources: namespace `influxdb`, Deployment `influxdb` (`influxdb:1.11.8`, `Recreate`, uid 999), PVC `influxdb` (40 Gi Longhorn, expanded from 20 Gi online on 2026-11-01), Service `influxdb:8086`, IngressRoute `influx.4jp.de` (cluster wildcard certificate) and the Cloudflare A record `influx.4jp.de` (imported on 2026-11-01, now `10.10.88.1`). Authentication is off, as on the legacy instance. Renovate is capped below 2.

Data: databases `vzlogger` (2.4 GB, since 2018) and `home_assistant` (6.2 GB) restored from `influxd backup -portable` taken on the legacy instance at 2026-11-01T07:55:26Z. Counts of `current_power`, `meter1`, `meter2`, `bkw_current_power`, `rolladen_position`, `speedtest`, `W`, `V`, `A`, `Hz` and `%` up to 07:55:00Z and both series cardinalities (237 and 1191) are identical on both sides. `node`, `default` and `_internal` were not carried over.

New Grafana (`g.4jp.de`): datasources `InfluxDB vzlogger` and `InfluxDB home_assistant`, dashboard `Power` (uid `tBUT3NfGk`, vendored from the legacy Grafana as `assets/grafana/dashboards/power.json`, datasource rewritten). Queries through the Grafana API return data. `Power small` is not carried over (subset of `Power`, old Angular panels); the InfluxDB part of `Solax` is undecided.

# Data path

```
Tasmota meter / Shelly BKW / Shelly roller -> HA Mosquitto add-on (192.168.178.122:1883, login `devices`) -> Telegraf `mqtt-bridge` (k0s, 10.30.0.10:1883, login `telegraf`) -> http://influxdb.influxdb.svc:8086 (`vzlogger`)
Home Assistant -> InfluxDB integration -> https://influx.4jp.de: disabled 2026-11-04T20:43:11Z (ADR-0047); `home_assistant` has been frozen since then
```

`mqtt2influxdb` on `dockerhost` was switched on 2026-11-01 08:06 UTC (`host: influx.4jp.de`, `port: 443`, `ssl: true`, `verify_ssl: true`; backup of the old file at `~/config.yml.pre-k0s-influx` on the host). Home Assistant was repointed by the user at 08:50:20Z; the legacy instance has received nothing since. The meter publishes every 5 minutes.

Since 2026-11-03 (ADR-0045) the MQTT leg is Home Assistant's Mosquitto add-on plus Telegraf (`services/influxdb/influxdb/mqtt_bridge.py`, Deployment `mqtt-bridge`, `telegraf:1.40.3`, three `mqtt_consumer` inputs) instead of `dockerhost` mosquitto and `mqtt2influxdb`. Mapping kept: `current_power` (int, `MT691.Power_curr`), `meter1`/`meter2` (float, `MT691.Total_in`/`Total_out`) from `tele/tasmota_629634/SENSOR`; `bkw_current_power` (float, `apower`) from `bkw/status/switch:0`; `rolladen_position` (int) from `shellies/rolladen-dach/roller/0/pos`; one field `value`, no tags, a Starlark processor truncates timestamps to seconds. Old `rolladen_position` points also carried a string field `type="int"` (mqtt2influxdb wrote its `type: int` setting as a field); the new points do not. Config `json_v2` with several `[[json_v2]]` blocks on one input worked for the meter (all three measurements arrive).

Gap fill (2026-11-01): the points the legacy instance received after the first backup (07:55:26Z to 08:50:30Z) were exported there with `influx_inspect export` (line protocol, TSM and WAL) and loaded with `influx -import`; counts for `W`, `V`, `A`, `Hz`, `%`, `GB` (to 08:50:21Z) and the five `vzlogger` measurements (to 08:06:00Z) are identical on both sides, series cardinality 1191.

**Lost:** about three minutes of Home Assistant and BKW points (roughly 08:57 to 09:00Z) while the volume was full (below); they exist on neither instance.

# Facts that shaped the design

- The legacy writers are only Home Assistant (direct) and `mqtt2influxdb`; a tcpdump on `enp2s0` found no other LAN host, and Docker's NAT hides local sources (`172.18.0.1`).
- `mqtt2influxdb` supports `ssl` and `verify_ssl`; the python client sets the `Host` header from `host`, so the DNS name has to resolve to Traefik before it can be used (`10.10.88.1` as host does not route).
- Authentication was off before; the HTTP interface is now reachable by every LAN client through Traefik. Enabling it needs credentials in Home Assistant, `mqtt2influxdb` and the two Grafana datasources.
- **The volume filled up during the migration:** the first backup copy (5 GB) stayed on the volume while the restore was done, and the second round of restores filled the remaining space; influxd then logged `no space left on device` and kept the stuck `_internal` WAL error until the Pod was restarted. Expand first (Longhorn expanded 20 to 40 Gi online in about a minute), delete restore directories right after use.
- `influxd backup -portable -start` does not give an incremental window: the restored `_gap` databases ended at the first backup's last point. Use `influx_inspect export -start/-end` on the legacy data and WAL directories (`-datadir /var/lib/influxdb/data/influx -waldir /var/lib/influxdb/wal`) and `influx -import` for a time window.
- Do not use `pkill -f` patterns that appear in the same shell command line.

# Stage 2 (done 2026-11-01)

Removed from `dockerhost` after the user's approval: `influxdb_influxdb_1`, image `influxdb:1.8.6`, `/opt/influxdb` (9 GB), `influxdb.service`, the Ansible role and playbook `influxdb` (uncommitted in `~/Documents/dockerhost`), and `jpspeedtest` (unit, `/opt/monitoring/speedtest`, the speedtest tasks and templates; the in-cluster exporter had 23 points in 12 h). The legacy dashboard `Power small` is deleted in the Ansible role and on the host; it is not carried over. Archive: `~/dockerhost-legacy-influxdb-archive/final/{vzlogger,home_assistant,node,default}` (portable backups, `README.txt` with the restore command, per-file `sha256` equal to the source). The QNAP SMB share `altens` is a synced family share, so the archive was not put there; a copy needs a dedicated QNAP location (SSH to the QNAP needs a host-key check and a biometric approval).

Left on `dockerhost`: mosquitto and `mqtt2influxdb` (stopped 2026-11-03, not removed), and in the legacy Grafana the datasources `InfluxDB` and `InfluxDBHomeAssistant`, the dashboards `Power` (also on the new Grafana) and `Solax` (InfluxDB part), which now show no data.

# Remaining

Decide on authentication. `Solax` and `Warmwasser` read the Thanos archive since 2026-11-04 (ADR-0047). The database `home_assistant` was copied to `~/k0s-influxdb-home-assistant-archive/` (portable backup, 4.7 GB, checksums verified) and dropped on 2026-11-05; the Grafana datasource `InfluxDB home_assistant` is gone too, restore into a new name with `influxd restore -portable -db home_assistant -newdb home_assistant_restored` if needed. The old `sensor.<entity>` measurements stopped on 2026-03-26 when the new Home Assistant moved to the measurement-per-unit schema. Stage 2 for mosquitto and `mqtt2influxdb` (remove containers, images, `/opt/mosquitto`, `/opt/mqtt2influxdb`) needs the user's approval.

# Still to verify

Longhorn backup `backup-05c89632c9984c1d` of PVC `influxdb/influxdb` (`pvc-8f8ee2a7-47ed-451a-b078-15920924b1dc`) is `Completed` at 2026-11-02T02:24:31Z, 27.2 GB (27,244,101,632 B), the first backup of this volume. Still open: the `Power` dashboard on a day with Home Assistant and meter data fully on k0s.
