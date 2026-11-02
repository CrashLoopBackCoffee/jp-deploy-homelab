---
tags: [homelab, adr, observability, alerting, qnap]
type: adr
status: accepted
date: 2026-11-02
created: 2026-11-02
updated: 2026-11-02
adr: 44
---

# ADR-0044 - QNAP Hybrid Backup Sync job alert

## Status

Accepted on 2026-11-02.

## Context

ADR-0016 asks for monitoring of Hybrid Backup Sync (HBS) job results. The legacy rule (fewer than 11 `Finished Sync job` lines per day from `BackupNAS`) has been silent since the QNAP moved to `job="qnap-syslog"` (ADR-0024). The QNAP runs four nightly jobs (`01_alten`, `02_uli`, `03_altens`, `04_fotos`), finishing between 01:19 and 02:41 UTC. On 2026-10-30 only `01_alten` finished (05:03 UTC): a real miss that nothing reported.

## Decision

Loki rule `qnap-hbs-jobs-missing` in `services/observability/observability/alert_rules.py`, severity `critical` (emergency Pushover per ADR-0032), `no_data_state=Alerting`, no `for` (the window already debounces):

- Query: `[Hybrid Backup Sync] Finished incoming Sync job` lines of `{job="qnap-syslog"}`, job name extracted into `hbs_job` with `regexp`.
- Fires when fewer than N distinct `hbs_job` values finished in 26 hours, or when no finished line exists at all (`absent_over_time` branch).
- N is the Pulumi setting `grafana.qnap-hbs-nightly-jobs` in `services/observability/Pulumi.prod.yaml` (4 today). Change it when an HBS job is added or removed; the rule text and summary follow. The rule is rebuilt by `alert_rules.qnap_hbs_rule(nightly_jobs)`.

## Consequences

- Detection is about 1-2 h after the latest normal finish time.
- The alert clears after the next complete night.
- A QNAP syslog outage longer than 26 h also pages: wanted, because the jobs become unobservable.
- Job failures that still log `Finished` are not covered; the dashboard panel on `Failed` lines (`homelab-qnap-backup`) stays the place for those.
- Changing the job count rolls the Grafana pod (`checksum/provisioning` annotation).

## Alternatives considered

- A 24 h line count: false positives when a run finishes later than the night before, and a duplicate run hides a missing job.
- A 36 h window: about 12 h later detection.
- Warning severity: rejected by the user.
- A hardcoded job count in `alert_rules.py`: a code change for every HBS job added or removed; a stack setting is easier to adjust.

## Verification

Backtest on Loki, 2026-10-26T04:00Z to 2026-11-02T05:00Z, 15-minute step: the count branch fires only from 2026-10-30 03:30Z to 2026-10-31 02:30Z (the real miss), the absent branch fires 2026-10-30 04:15-05:00Z, no false positives otherwise. With a non-existent `job`, the expression returns `{job="..."} 1`.

The rule expression from code returned `1` at 2026-10-30T12:00Z and `0` on 2026-11-02 (four jobs ran overnight). Applied from `main` on 2026-11-02 (PR #117): the provisioning API returns the rule with `severity=critical` and `noDataState=Alerting`; Grafana reports `health=ok`, `state=inactive` and 39 rules in total.

## Related notes

- [[ADR-0016 - QuObjects backup target and encrypted offsite copy]]
- [[ADR-0023 - Retire the legacy dockerhost monitoring stack]]
- [[ADR-0024 - QNAP syslog into Loki]]
- [[ADR-0032 - Emergency Pushover priority for critical alerts]]
