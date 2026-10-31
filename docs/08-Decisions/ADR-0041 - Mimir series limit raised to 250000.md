---
tags:
  - homelab
  - adr
  - observability
  - mimir
type: adr
status: accepted
date: 2026-10-29
created: 2026-10-29
updated: 2026-10-29
adr: 41
---

# ADR-0041 - Mimir series limit raised to 250000

## Status

Accepted on 2026-10-29.

## Context

Mimir's default `max_global_series_per_user` is 150,000. On 2026-10-29 the single ingester sat at that limit (in-memory series 150,000, active about 117,000) and rejected samples with reason `per_user_series_limit`: about 39,500 samples in one hour and about 173,000 in 24 hours, with Alloy logging HTTP 400 for whole 2,000-sample batches (the failure mode described in [[ADR-0026 - Mimir series budget and API server buckets]]). The in-memory count includes series of pods that no longer exist until the head block is compacted, so the rollouts of the Wazuh, Trivy, TeslaLogger and MariaDB work that day inflated it on top of steady growth (Wazuh jobs 51 to 58 series, Trivy 115). The ingester used about 400 MiB, with no memory limit set.

## Decision

Set `max_global_series_per_user` to **250,000** through a required config field of the observability stack (`max-global-series-per-user`), instead of the chart default. This leaves headroom for normal churn and for the planned Wazuh agent hosts while keeping a limit that still catches a cardinality explosion.

## Consequences

- The ingester holds up to about two thirds more series in memory (estimated about 700 MiB at the new limit; no memory limit is set, check the node before raising further).
- The alert `mimir-samples-discarded` (ADR-0026) stays the guard: it fires when the new limit is reached too.
- Series growth from new scrapes still needs an allow-list (the Wazuh and Trivy scrapes already have one).

## Alternatives considered

- Keep 150,000 and drop series: loses data that is wanted (cAdvisor 16.7k, ax51 16.2k, apiserver 15.1k are the largest jobs).
- A much higher limit: hides cardinality mistakes and costs memory on the single node.

## Related notes

[[ADR-0019 - LGTM observability stack on k0s]], [[ADR-0037 - Wazuh security monitoring on k0s]]
