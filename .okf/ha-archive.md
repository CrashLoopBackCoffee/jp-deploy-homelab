---
type: Service
title: Home Assistant sensor archive on Thanos (Pulumi, prod)
description: Curated long-term archive of Home Assistant sensors on k0s - data path, labels, queries, retention, the InfluxDB backfill procedure with its parameters and verification, and the pitfalls found while building it (ADR-0047).
timestamp: 2026-11-03T00:00:00Z
tags: [homelab, kubernetes, thanos, home-assistant, archive, backfill, influxdb]
resource: https://app.pulumi.com/jaypee-solutions/thanos/prod
---

# State

Stack `jaypee-solutions/thanos/prod` (source `services/thanos`, applied 2026-11-03), namespace `thanos`, chart `oci://ghcr.io/stevehipwell/helm-charts/thanos` 1.24.2 (Thanos 0.42.4): Receive (router and ingestor, 10 Gi, keeps 48 h and ships 2 h blocks), Store Gateway (5 Gi), Compactor (20 Gi, `--retention.resolution-raw=0d`, downsampling off) and Query. The bucket `ha-archive` is on the QNAP (`qnap.4jp.de:8443`, key in `op://Homelab/QuObjects Home-Assistant`, not part of `mimir-metrics`, no off-site copy).

# Data path

```
Home Assistant `prometheus:` (config/prometheus_entities.yaml, 144 entities, deploy-home-assistant)
  -> Alloy `prometheus.scrape` https://home-assistant.4jp.de/api/prometheus, every 15 s, Bearer token (1Password `HA Prometheus Scrape`, long-lived token `alloy-archive`)
  -> `prometheus.relabel`: keep `homeassistant_(sensor_.+|binary_sensor_state|entity_available)|up`, drop label `friendly_name`
  -> `remote_write` to http://thanos-receive-router.thanos.svc.cluster.local:19291/api/v1/receive (not to Mimir)
Grafana datasource "Thanos archive" (uid `thanos-archive`) -> http://thanos-query.thanos.svc.cluster.local:10902
```

About 278 series arrive (value series 133, `entity_available` 144, `up`). Series labels: `domain`, `entity` (identity), `instance="home-assistant.4jp.de:443"`, `job="home-assistant"`; Receive adds the external labels `tenant_id="default-tenant"` and `receive_replica="thanos-receive-ingestor-0"` (Query removes the replica label).

# Querying

The metric name follows the unit and device class, so select by the `entity` label: `{__name__=~"homeassistant_(sensor|binary_sensor).*", entity="sensor.solax_house_load"}`. Examples: `homeassistant_sensor_power_w`, `_energy_kwh`, `_temperature_celsius`, `_humidity_percent`, `_illuminance_lx`, `_power_kw`; entities without a device class (`sensor.mypv_*`) are `homeassistant_sensor_unit_w` and `_unit_celsius`; PM2.5 is `homeassistant_sensor_pm25_u0xb5g_per_mu0xb3`. An `unavailable` entity has `homeassistant_entity_available 0` and no value series. An available entity that stopped updating keeps exporting its last value.

# Backfill from InfluxDB (done 2026-11-03)

Source: database `home_assistant` (since 2026-03-26 measurement per unit with tag `entity_id`; 2023-10-04 to 2026-03-26 measurement `sensor.<entity>` with the same tag). Method, as a throwaway tool under `/tmp/backfill` (not committed):

1. `plan.py`: for each allowlist entity find the exporter metric name (from the live series; computed from device class and unit for the 11 entities that are unavailable now), the Influx measurements, first and last point, and the point count (96 million points for 139 entities with data; 5 entities have none).
2. `backfill.py`: fetch the raw state-change points (both schemas), forward-fill them onto a 15 s grid (what a scrape would have seen) for at most 7 days after the last change, write OpenMetrics per UTC day, and make blocks with `promtool tsdb create-blocks-from openmetrics --max-block-duration=24h`. Grid times use milliseconds so an event after the grid second is not used.
3. `thanos tools bucket upload-blocks --path blocks --label 'tenant_id="default-tenant"' --label 'receive_replica="thanos-receive-ingestor-0"'` with an objstore file (credentials from 1Password; delete the file afterwards). The labels equal the live blocks, so the Compactor merges both (vertical compaction and replica deduplication are on).
4. Cut at 2026-11-03T18:00Z; a last block covers 18:00 to 18:29:15Z, before the first live sample (18:29:33Z), so nothing overlaps and nothing is missing.

Result (2026-11-03): 139 entities, 2023-10-04 to 2026-11-03, 314 million samples in 2253 blocks (about 370 MB) uploaded in 8 minutes; generation took 35 minutes. Query returned 34 to 37 value series in 2023 to 2025 (the old-schema Solax and Shelly entities), 107 in June 2026 and 134 now.

Verification: 480 random (entity, time) pairs in three windows (October 2026, March 2025, June 2026) matched the Influx value exactly (after fixing a sub-second ordering bug); Thanos Query returned the same value for a past time as Influx (585 W on 2025-03-10); the label sets equal the live series.

# Pitfalls

- A 3-hour forward-fill limit lost 40% of the entities: idle plugs and energy counters change once a day; 48 h still lost some; 7 days was chosen.
- `promtool tsdb dump` needs a `wal` directory next to the blocks; remove it before the upload. `upload-blocks` has no dry run.
- The classic chart repo `stevehipwell.github.io/helm-charts` redirects to `steve.hipwell.xyz/helm-charts` and fails in Pulumi (`Chart.yaml file is missing`); the OCI chart works.
- boto3 against QuObjects needs `request_checksum_calculation='when_required'` (`InvalidDigest` otherwise); minio-go (Thanos, Mimir) works.
- Influx `SHOW SERIES WHERE "entity_id"=...` lists both schemas' measurements for one entity; query both in one `FROM` to stitch the history.
- The Store Gateway syncs the bucket every 15 minutes (the chart default), so uploaded blocks appear in Query up to 15 minutes later; `/api/v1/stores` shows its min and max time.
- Gen1 Shelly CoIoT pushes stopped reaching HA after the dual-NIC change (ADR 0013 in deploy-home-assistant): not an archive issue, found while the backfill ran.

# Open

Dashboards still read InfluxDB; repointing them and switching off HA's InfluxDB integration are the last steps of ADR-0047.
