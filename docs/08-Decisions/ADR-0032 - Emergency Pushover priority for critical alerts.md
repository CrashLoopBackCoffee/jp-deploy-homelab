---
tags: [homelab, adr, observability, alerting]
type: adr
status: accepted
date: 2026-10-24
created: 2026-10-24
updated: 2026-10-24
adr: 32
---

# ADR-0032 - Emergency Pushover priority for critical alerts

## Status

Accepted on 2026-10-24.

## Context

The legacy Alertmanager sent Pushover notifications without an explicit priority, so its defaults applied: priority 2 while firing, retry every minute, expire after one hour, and priority 0 when resolved. The k0s Grafana contact point explicitly used priority 0, so critical alerts did not nag until acknowledged. This mattered during the `paperless-db` WAL-archiving failures on 2026-10-22.

## Decision

Route alerts with `severity=critical` to a separate `pushover-emergency` contact point at emergency priority 2, retry every 60 seconds, expire after 3600 seconds, and send resolved notifications at priority 0. Keep the existing `pushover` contact point at normal priority 0 for other alerts. `warning` is the default severity, and the notification policy's `repeat_interval` remains 12 hours. Change a rule's `severity` to tune whether it is an emergency; do not tune the contact point for individual rules.

The critical rule UIDs are:

- `node-not-ready`
- `longhorn-volume-unhealthy`
- `longhorn-backup-target-unavailable`
- `longhorn-volume-backup-stale`
- `cnpg-instance-down`
- `cnpg-wal-archiving-failing`
- `cnpg-backup-stale`
- `paperless-backup-stale`
- `mimir-samples-discarded`
- `tandoor-down`
- `netbox-down`
- `certificate-expiring`
- `probe-failing`
- `probe-failing-slow`

## Consequences

A firing critical alert repeats at the Pushover retry interval until acknowledged in the app or the one-hour expiration passes. Resolved messages use priority 0. Warnings and any other non-critical alerts continue through the normal priority-0 contact point.

## Verification

The Grafana provisioning API lists both contact points with the expected settings and shows the child route `severity = critical` to `pushover-emergency`; all 24 alert rules report `health=ok`. The emergency receiver test used the current v1beta1 receiver-test API and returned HTTP 200 with `status: success`. The user's confirmation that the notification repeats until acknowledged is still pending.
