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
adr: 23
---

# ADR-0023 - Retire the legacy dockerhost monitoring stack

## Status

Accepted on 2026-10-17. The migration is **planned, not started**; the runbook, inventory and gates are in `.okf/legacy-monitoring-migration.md`.

## Context

The user's old monitoring runs on the single host `dockerhost` (`192.168.178.125`, Ubuntu) from the Ansible role `monitoring` in `/Users/alten/Documents/dockerhost`: Prometheus (365 days of retention, about 93 GB in August), Alertmanager to Pushover, Grafana with Entra ID login and 18 provisioned dashboards, Loki 2.4.1 with Promtail, cAdvisor, blackbox-exporter, fritz-exporter and a systemd speedtest that writes to InfluxDB. The replacement already runs on k0s ([[ADR-0019 - LGTM observability stack on k0s]]): Mimir, Loki, Grafana, Alloy and Pushover alerting.

The legacy stack scrapes 13 jobs (about 55 targets, 32 of them HTTP probes). Many targets sit on `192.168.178.0/24`, which the cluster cannot reach today: every probe from a pod to that subnet timed out on 2026-10-17, while the modem at `192.168.1.1` answered. `dockerhost` itself stays in service (Traefik, NetBox, InfluxDB, Home Assistant and other stacks), so only the monitoring role is retired.

## Decision

- **Retire the legacy monitoring stack in two stages.** Stage 1 moves everything that does not need the LAN; the legacy Prometheus, Alertmanager and Grafana keep running for the LAN-only remainder. Stage 2 removes them once the LAN part is solved or the user accepts the loss. The user deferred the LAN targets ("will handle later"), so stage 2 is gated on that.
- **Keep the history by backfilling the Prometheus TSDB into Mimir.** Mimir's retention rises from 30 to 365 days, TSDB block upload is enabled, and the blocks are re-sliced to at most 24 hours aligned to UTC days, because Mimir rejects longer blocks. Storage for blocks, the store-gateway and the compactor is sized for it first.
- **Replace the speedtest-to-InfluxDB script with an in-cluster Prometheus speedtest exporter** and rebuild the internet-speed dashboard on Mimir. The other InfluxDB-backed dashboards (Power, Power small, the InfluxDB part of Solax) depend on LAN-side sources and move to Prometheus metrics with the LAN work.
- **Grafana signs in through Authentik OIDC**, following [[ADR-0021 - Paperless single sign-on through the shared Authentik]]: an AX41 blueprint owns the groups and bindings, the provider and secret stay in the Authentik UI, and a 1Password item holds the client credentials. Entra ID is dropped.
- **`grafana.4jp.de` points at the new Grafana.** One hostname is canonical (recommended `g.4jp.de`, with `grafana.4jp.de` redirecting) because an OIDC redirect URI is bound to the Grafana `root_url`.
- Alert rules are ported by judgement, not copied: duplicates of the 16 rules already in the new stack and rules that cannot fire are dropped.

## Consequences

- Until stage 2, alerts exist twice for migrated targets. Remove the migrated jobs and rules from the legacy Prometheus when a target is cut over, to avoid duplicate Pushover messages. Applying the legacy role restarts its whole stack.
- Deferring the LAN means these stay on the legacy stack for now: dockerhost host and container metrics, QNAP node metrics, the FritzBox, the Windows desktop (`ohmgraphite`), `jexporter` (mypv, SwitchBot, Zweiradgarage), Watchtower, the BackupNAS syslog and its backup rules, and the home-automation dashboards. The alerts **ZweiradGarage** and **WarmWaterOutage** only exist there.
- The Loki rules that count `Finished Sync job` lines from `BackupNAS` are the only monitoring of the HBS sync jobs that [[ADR-0016 - QuObjects backup target and encrypted offsite copy]] asks for. They need the syslog receiver in the new stack before the HBS 3 work.
- Backfill needs a free path to Mimir and the data side by side. The workstation has 43 GB free and cannot stage 93 GB, so the upload runs on `dockerhost` through an SSH reverse tunnel to a `kubectl port-forward`, which adds no exposed endpoint.
- Block upload is an experimental Mimir feature. The first run is a one-week test on a copy; the full run follows only if the test queries correctly.
- Decommissioning deletes data on `dockerhost` and DNS records. Each destructive step needs the user's approval, and the TSDB and Grafana database are archived first.

## Alternatives considered

- **Migrate the LAN targets at the same time:** needs an OPNsense decision (a narrow allow rule from `k0s0`, or a push agent with an authenticated write endpoint) that the user chose to postpone.
- **Archive the TSDB only, or drop the history:** cheaper, but the user wants the history in one place.
- **Keep Entra ID for Grafana:** no new Authentik application, but a second identity provider to maintain next to the one already brokering Mailcow and Paperless.
- **Keep the legacy stack running indefinitely:** rejected; it is a single host with Loki pinned to a 2021 release and secrets in an Ansible vault.

## Related notes

- [[ADR-0019 - LGTM observability stack on k0s]]
- [[ADR-0021 - Paperless single sign-on through the shared Authentik]]
- [[ADR-0016 - QuObjects backup target and encrypted offsite copy]]

## References

- [Configure TSDB block upload](https://grafana.com/docs/mimir/latest/configure/configure-tsdb-block-upload/)
- [mimirtool backfill](https://grafana.com/docs/mimir/latest/manage/tools/mimirtool/#backfill)
- [Migrating from Thanos or Prometheus to Grafana Mimir](https://grafana.com/docs/mimir/latest/set-up/migrate/migrate-from-thanos-or-prometheus/)
