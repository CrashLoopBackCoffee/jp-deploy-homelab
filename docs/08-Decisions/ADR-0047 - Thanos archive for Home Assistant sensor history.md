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
updated: 2026-11-03
adr: 47
---

# ADR-0047 - Thanos archive for Home Assistant sensor history

## Status

Accepted on 2026-11-03. Not built; the one-day spike below comes first.

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

1. **One-day spike, nothing applied:** enable HA's `prometheus` integration with the allowlist; scrape it through a port-forward; check metric and label names, the series count against the allowlist, the behaviour of `unavailable` sensors and the scrape duration. Check the `stevehipwell/thanos` Helm chart (application version 0.42.x) supports Receive, and create the bucket and access key in QuObjects.
2. `services/thanos` stack: Receive (one replica, PVC), Store Gateway, Compactor (PVC), Query, bucket secret; Alloy scrape job and `remote_write` in `observability` or its own Alloy; Grafana datasource.
3. Backfill script and a verification against the InfluxDB counts.
4. Switch off the HA InfluxDB integration; update the OKF notes.

## Consequences

- Four more Pods on the single k0s node (about 12 CPU and 32 GB; Mimir already runs eight) for roughly 170 series; accepted for the separate retention and the Thanos growth path.
- A restart of Receive or Alloy leaves gaps in the archive; Alloy's WAL covers short ones. A scrape of HA is a dependency on the CoRE→HoME path (open, ADR-0008).
- Open: whether the single Longhorn volume of Receive and Compactor needs its own backup beyond the bucket.

## Related notes

- [[ADR-0043 - InfluxDB 1.x on k0s for power and Home Assistant history]]
- [[ADR-0026 - Mimir series budget and API server buckets]]
- [[ADR-0045 - Home Assistant Mosquitto as the single MQTT broker]]
- [[ADR-0046 - Home Assistant owns the garage lock and MyPV alerts]]
