---
tags:
  - homelab
  - adr
  - kubernetes
  - observability
type: adr
status: accepted
date: 2026-10-17
created: 2026-10-17
updated: 2026-10-17
adr: 26
---

# ADR-0026 - Mimir series budget and API server buckets

## Status

Accepted and applied on 2026-10-17.

## Context

Mimir limits a tenant to 150,000 active series (`max_global_series_per_user`, the default). Adding the probes and scrapes of [[ADR-0025 - Probe and scrape targets from 1Password]] exceeded it: Alloy logged `per-user series limit of 150000 exceeded` and only some of the new series were accepted (6 of 27 website probes, no `ax51` or `pretix` series).

The count on 2026-10-17 was 143,291 active and 150,000 in memory. The job `apiserver` alone held **82,727** series, and about 66,000 of them were histogram buckets (`apiserver_request_duration_seconds_bucket` 21,096, `apiserver_request_sli_duration_seconds_bucket` 14,212, `etcd_request_duration_seconds_bucket` 11,496, `apiserver_request_body_size_bytes_bucket` 10,400 and four smaller ones). For comparison, the whole legacy Prometheus held about 40,000 series for every target. No alert rule, generated dashboard or vendored dashboard in this repository uses an `apiserver_*` or `etcd_*` metric. The ingester used 0.54 GB at 150,000 series (about 3.6 KB per series) on a node with 31 GB, so memory was not the constraint.

## Decision

- **Drop every `*_bucket` series of the `apiserver` job** in Alloy, through a `prometheus.relabel` between the scrape and the remote write. `_count`, `_sum` and `apiserver_request_total` stay, so request rates, errors and average latency remain available.
- **Do not raise the tenant limit.** The waste, not the limit, was the problem, and a higher limit would have hidden it. After the change the series in memory fell from 150,000 to 88,090 (113,790 later with the new probes and scrapes), which leaves a third of the budget free.
- **Free the headroom at once** by flushing the ingester head (`POST /ingester/flush?wait=true` on the ingester pod, HTTP 204): series that stopped arriving leave memory at the next head compaction, which could be two hours away, and the cap counts series in memory.

## Consequences

- There are no API server latency quantiles (`histogram_quantile`). If a panel or rule needs one, keep a single bucket metric back (for example `apiserver_request_duration_seconds_bucket` without its `sli` twin) and check the series count first.
- The budget is now a known quantity: roughly 100,000 series in steady state. The LAN targets still to come (dockerhost node-exporter and cAdvisor, QNAP, FritzBox, jexporter) will add some, so check `cortex_ingester_memory_series` before adding them and decide then whether to trim or to raise `max_global_series_per_user`; 3.6 KB per series makes 300,000 about 1.1 GB.
- The backfill of the legacy history does not count against this limit: uploaded blocks bypass the ingesters.
- A rule on the series count is worth adding: nothing warned before the cap was hit. Follow-up, not built here.
- **Update 2026-10-18: the label limit, and what Alloy does with a rejected write.** Mimir allows 30 label names per series (`err-mimir-max-label-names-per-series`). The AX51 cAdvisor turns every Docker label into a `container_label_*` label, and some series carried 33 to 36 labels. Mimir answers such a write with a 400; Alloy treats that as non-recoverable and drops the whole batch of 2,000 samples, so about 1% of all samples (about one batch a minute) were lost from 2026-10-17 17:11 UTC, spread over unrelated series. The `ax51` scrape now drops `container_label_.+` in a `prometheus.relabel` (the same pattern as for the API server). Nothing used these labels; `name`, `image` and `id` stay. After the change the rejections stopped (0 errors and 0 discarded samples in 2 minutes, all three `ax51` targets up). Not done: `container_network_advance_tcp_stats_total` is the largest family (7,425 live series, of about 17,000 for the whole job) and nothing uses it; drop it if the series budget gets tight. The limit itself is not raised, for the reason given above.

## Alternatives considered

- **Raise `max_global_series_per_user` to 300,000:** works and is cheap in memory, but keeps 66,000 series that nothing reads.
- **Drop only the largest bucket metric:** leaves most of the cost; the others are just as unused.
- **Wait for the head compaction instead of flushing:** up to two hours of partly rejected probes and scrapes.

## Related notes

- [[ADR-0019 - LGTM observability stack on k0s]]
- [[ADR-0025 - Probe and scrape targets from 1Password]]
