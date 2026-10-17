---
tags:
  - homelab
  - adr
  - kubernetes
  - observability
  - migration
type: adr
status: accepted
date: 2026-10-17
created: 2026-10-17
updated: 2026-10-17
adr: 27
---

# ADR-0027 - Speedtest exporter and legacy dashboards

## Status

Accepted and applied on 2026-10-17 (phase 3 of [[ADR-0023 - Retire the legacy dockerhost monitoring stack]]).

## Context

The legacy stack measured the internet speed with a Python script on `dockerhost` that wrote to InfluxDB every 30 minutes, and showed it on an InfluxDB dashboard. The user decided to move this to Prometheus metrics. The user also chose which dashboards to keep from the legacy Grafana: `Prometheus Blackbox Exporter`, `Status` and `Pretix` (created in its UI, so they exist only in its database), plus `WordPress Core Updates` (provisioned from Ansible).

## Decision

- **Deploy `billimek/prometheus-speedtest-exporter` 1.3.1 in the `observability` namespace** (the donor's choice) as a one-replica Deployment with a ClusterIP Service. It has no CPU limit, because a limit would throttle the measurement, and a 256 MiB memory limit. Its port is called `probe`, not `metrics`, so Alloy's generic pod scrape does not pick it up: every scrape runs a real test.
- **Alloy scrapes `/probe?script=speedtest` every 30 minutes** (the legacy cadence) with a 3-minute timeout, as job `speedtest`.
- **Rebuild `Internet Speed` in code** on the exporter's series: download and upload in bit/s (the exporter reports bytes per second, multiplied by 8), latency and jitter, test duration and success.
- **Port the four kept dashboards unchanged** into `assets/grafana/dashboards/` (extracted from the legacy Grafana database, and from the Ansible repository for the WordPress one). A small extension of the adapter points their datasource, named `Prometheus` or by its old UID, at Mimir. They contain no host names or customer data (checked before they were committed).

## Consequences

- **Verified 2026-10-17:** the exporter works (a test took 12 s: 193 Mbit/s down, 40 Mbit/s up); Grafana lists 14 dashboards; every one of the 24 panel queries of the four ported dashboards returns data against Mimir (Blackbox 10, Status 1, Pretix 6, WordPress 7). The first scheduled speed test was still to come when this was written, so the Internet Speed panels fill within 30 minutes.
- **The exporter's names are wrong:** `speedtest_latency_seconds` and `speedtest_jittter_seconds` (three t) are milliseconds (7.99 and 0.401 for an 8 ms link). The dashboard uses the unit `ms` and the code says why.
- **The test measures the cluster's uplink**, through OPNsense, not the old host's.
- **Data volume:** one test moved about 138 MB down and 18 MB up. At one test every 30 minutes that is about 7.5 GB per day (about 225 GB per month). The legacy script had the same cadence; if the line has a cap, an interval of 60 minutes halves it (the exporter README recommends long intervals).
- **The dashboard ConfigMap** is 489 KB of Kubernetes' 1 MiB limit for a ConfigMap; a few more community dashboards fit, a large one may not, and the node-exporter dashboard alone is 227 KB.
- The legacy Pretix dashboard's `buckets` panel matches `url_name` with `=`, which returns nothing when the variable is set to All; this is how the legacy dashboard worked and was left as it was.
- Superseded legacy dashboards (`Docker and system monitoring`, `Traefik3`, `coffee`, `SwitchBot Meter`, `Temperature`) are not ported, as decided in ADR-0023.

## Alternatives considered

- **The donor's LoadBalancer Service for the exporter:** exposes an endpoint that starts speed tests to the LAN; only Alloy needs it.
- **Scrape every 60 minutes as the exporter README suggests:** half the data volume, but a coarser history than the legacy one.
- **Rewrite the legacy dashboards in code:** more work and no benefit for four small dashboards that already work.

## Related notes

- [[ADR-0025 - Probe and scrape targets from 1Password]]
- [[ADR-0026 - Mimir series budget and API server buckets]]

## References

- [prometheus-speedtest-exporter](https://github.com/billimek/prometheus-speedtest-exporter)
