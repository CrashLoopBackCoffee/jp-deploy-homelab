---
tags:
  - homelab
  - adr
  - home-assistant
  - observability
  - thanos
type: adr
status: accepted
date: 2026-11-03
created: 2026-11-03
updated: 2026-11-04
adr: 47
---

# ADR-0047 - Thanos archive for Home Assistant sensor history

## Status

Accepted on 2026-11-03. Spike, stack, scrape, backfill and the migration (step 4: dashboards, SOC, InfluxDB integration, archive copy) are done and verified on 2026-11-03 and 2026-11-04.

## Context

Home Assistant owns all home sensors and devices (ADR-0045, ADR-0046). Its recorder keeps raw states for 10 days and then only 5-minute min/mean/max statistics (285 statistic IDs, SQLite on the VM). That is HA's own storage, not an archive. The InfluxDB integration writes every state change of every entity to `home_assistant` on k0s (ADR-0043): 1330 entities, 753 series with data, about 400k points a day, 970 measurements, 6.3 GB since 2026-03, no retention policy, no include list. 80% of the points come from 87 series.

Of the 1330 entities, 204 have a `state_class`; by device class: power 56, energy 42, temperature 19, humidity 10, battery 23, voltage/current/frequency/reactive power 17, others 37. The Mimir of LGTM has one retention for all data (400 days), one bucket (`mimir-metrics`, not in the HBS off-site job, ADR-0023) and a 100,000-series budget (ADR-0026); retention in Prometheus-family stores is per store, not per series.

## Decision

- **A separate archive for curated HA sensors, built on Thanos** (Receive, Store Gateway, Compactor, Query) in its own namespace and its own QNAP S3 bucket, not in Mimir and not in InfluxDB. The user prefers Thanos from other projects; separate retention and a separate bucket keep the home archive independent of infra metrics.
- **Curated, in git.** Only an allowlist goes into the archive: power, energy, temperature, humidity, illuminance, PM2.5, electricity price (about 130 to 170 series). Voltage, current, frequency, battery, RSSI, uptime, firmware, diagnostics, ToF distance, automations and device trackers stay in HA's recorder only. The allowlist is HA's `prometheus.filter` in `deploy-home-assistant`.
- **Fixed-interval pull, 15 s.** HA's `prometheus` integration (`https://home-assistant.4jp.de/api/prometheus`, HTTPS on 443 only, through the local DNS record of ADR-0046; long-lived token in 1Password) is scraped by Alloy and written to Thanos Receive (`remote_write`). About 550 MB a year for 170 series; short spikes under 15 s are smoothed. The `friendly_name` label is dropped so a rename does not fork a series.
- **Retention:** raw data forever (`--retention.resolution-raw=0d`); downsampling disabled. No per-series retention.
- **Durability:** QNAP only (the user's choice). The bucket is separate, so adding it to the HBS job later needs no change to infra metrics.
- **Backfill:** the archive-tier entities of the existing InfluxDB `home_assistant` (since 2026-03) are converted to Prometheus blocks (mapping unit measurement and `entity_id` to the integration's metric names, state changes forward-filled onto the 15 s grid) and uploaded to the bucket. The InfluxDB database stays read-only afterwards until the archive is verified.
- **Grafana:** a Thanos Query datasource; `Warmwasser`, `Solax` and later dashboards read from it.
- **Home Assistant's InfluxDB integration** is switched off after the backfill is verified.

## Rejected

- **Second Mimir tenant:** cheapest, but shares the bucket and the retention policy with infra metrics and has no separate durability path.
- **Prometheus with a Thanos sidecar:** the smaller design (one Pod, ten-year local retention) was the recommendation; the user chose full Thanos.
- **VictoriaMetrics:** a new tool, though its backfill needs no conversion.
- **Keeping InfluxDB 1.x with retention policies:** no change to the event-driven gaps and the end-of-line product.

## Migration

1. **Spike (done 2026-11-03):** HA's `prometheus` integration is enabled with the allowlist (`config/prometheus_entities.yaml`, 144 entities; `deploy-home-assistant` commit 9f5fa97, deployed with a restart of about one minute). Results in "Spike results". Still open from this step: the bucket and access key in QuObjects (QNAP).
2. **Stack and scrape (done 2026-11-03, PR #130, #131):** `services/thanos` (Receive, Store Gateway, Compactor, Query on the bucket `ha-archive`), Alloy scrape of HA every 15 s into Receive only, Grafana datasource "Thanos archive". About 278 series arrive.
3. **Backfill (done 2026-11-03):** the 139 archive-tier entities from `home_assistant` (2023-10-04 to 2026-11-03, both Influx schemas) as 314 million samples in 2253 blocks, forward-filled onto the 15 s grid for at most 7 days, uploaded with the live external labels so the Compactor merges them; 480 sampled values matched InfluxDB exactly; Query returns the history through the Store Gateway. Details and pitfalls in `.okf/ha-archive.md`.
4. **Dashboards, freeze and archive copy (done 2026-11-04, PR #133):**
   - `Solax` and `Warmwasser` read the Thanos datasource (PromQL, selected by `entity`); only the BKW and `meter1` targets stay on InfluxDB `vzlogger`. `Power` has no HA entities and is unchanged.
   - `sensor.solax_battery_capacity` (the SOC panels) was added to HA's allowlist and backfilled (6.49 million samples, 2023-10-04 to the first live sample). This is an exception to "battery stays in the recorder": the inverter SOC is energy data, not the battery of a device.
   - HA's InfluxDB config entry was disabled (not deleted) at 2026-11-04T20:43:11Z; `deploy-home-assistant` ADR 0014. HA was the only writer on `home_assistant`, so the disabled entry was the freeze (auth is off); no points arrived afterwards (checked 5 minutes and 8 hours later).
   - Archive: a portable backup on the workstation, `~/k0s-influxdb-home-assistant-archive/` (4.7 GB, `SHA256SUMS` equal to the source, restore command in `README.txt`); the nightly Longhorn backup of the PVC also holds the data.
   - Retired on 2026-11-05 with the user's approval: `DROP DATABASE home_assistant` (the PVC fell from 8.9 to 2.6 GB used), the Grafana datasource `InfluxDB home_assistant` (provisioning `deleteDatasources`, PR #136) and the OPNsense HoME egress rule 130 (TCP 443 to `10.10.88.1`, deleted through the API and applied). A later Solax fix (PR #135): the panels' `merge` transformation collapsed the Prometheus series (all named `Value`) into one and was removed.

## Spike results (2026-11-03)

- **Scrape:** `GET https://home-assistant.4jp.de/api/prometheus` with a Bearer token: HTTP 200, 46 ms, 123 KB, 856 series in total. From a Pod the path works (DNS to `10.30.0.10` through OPNsense, TLS verifies, 401 without the token).
- **Series by family:** value series 130 (`homeassistant_sensor_power_w` 56, `_energy_kwh` 44, `_temperature_celsius` 15, `_humidity_percent` 8, `_illuminance_lx` 2, `_power_kw` 1, `_unit_w` 2, `_unit_celsius` 1, `homeassistant_binary_sensor_state` 1); per entity `homeassistant_entity_available` 144, `_state_change_total` 144, `_state_change_created` 144, `_last_updated_time_seconds` 144, `_entity_info` 121; `area_info` 13; Python and process metrics.
- **Labels:** `domain`, `entity` (for example `sensor.solax_house_load`), `friendly_name` (drop it, as planned). The metric name depends on the unit or device class, and entities without a device class get `homeassistant_sensor_unit_<unit>` (`mypv_*`), so dashboards select by `entity` with a name regex (`{__name__=~"homeassistant_(sensor|binary_sensor).*", entity="…"}`), not by metric name.
- **`unavailable`:** 14 of the 144 entities are unavailable now. They have `homeassistant_entity_available 0` and **no value series**, so the series ends and Prometheus marks it stale. A sensor that is available but stopped updating keeps exporting its last value; `homeassistant_last_updated_time_seconds` is the only hint.
- **Series to keep in the archive:** the 130 value series plus `homeassistant_entity_available` (144, constant, compresses to almost nothing). Drop `state_change_total`, `state_change_created`, `last_updated_time_seconds` (about 2–3 bytes per sample, little value), `area_info`, `python_*` and `process_*` in an Alloy relabel; `entity_info` (area per entity) is optional. That is 274 series, about 0.9 GB a year at 15 s.
- **Not exported:** no electricity-price sensor (only `sensor.tibber_price_level`, an enum); PM2.5 and part of the Vindstyrka and plug sensors are unavailable at the moment.
- **Thanos chart:** `stevehipwell/thanos` 1.24.2 (Thanos 0.42.4) has `receive` (disabled by default, local retention 48 h, ships blocks), `compact`, `storeGateway`, `query`, `queryFrontend`, `rule`; Receive and a bucket config (`objstoreConfig`) are supported.
- **HA restart:** the deploy restarted HA once; Zigbee2MQTT, the meter and the Telegraf bridge came back without errors, and the 10-minute `probe-failing` rule did not fire.

## Consequences

- Four more Pods on the single k0s node (about 12 CPU and 32 GB; Mimir already runs eight) for roughly 170 series; accepted for the separate retention and the Thanos growth path.
- A restart of Receive or Alloy leaves gaps in the archive; Alloy's WAL covers short ones. A scrape of HA is a dependency on the CoRE→HoME path (open, ADR-0008).
- Open: whether the single Longhorn volume of Receive and Compactor needs its own backup beyond the bucket.

## Related notes

- [[ADR-0043 - InfluxDB 1.x on k0s for power and Home Assistant history]]
- [[ADR-0026 - Mimir series budget and API server buckets]]
- [[ADR-0045 - Home Assistant Mosquitto as the single MQTT broker]]
- [[ADR-0046 - Home Assistant owns the garage lock and MyPV alerts]]
