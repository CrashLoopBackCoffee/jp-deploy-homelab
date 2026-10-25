---
tags: [homelab, adr, tandoor, observability, alerting]
type: adr
status: accepted
date: 2026-10-25
created: 2026-10-25
updated: 2026-10-25
adr: 34
---

# ADR-0034 - Tandoor 2.7.1 metrics authentication

## Status

Accepted on 2026-10-25.

## Context

After Tandoor 2.7.1 was deployed, Alloy's unauthenticated scrape of `/metrics` began receiving a redirect to `/account/login/?next=/metrics`. `ENABLE_METRICS=1` is set, but 2.7.1's `ScopeMiddleware.NO_AUTH_VIEWS` does not include `/metrics`; the endpoint is therefore blocked before Django Prometheus serves metrics. Mimir reports `up{job="tandoor"} == 0`, firing critical `tandoor-down` and warning `Scrape target down` alerts. `tandoor-server-errors` is inactive. The app Pod is 1/1 Ready; login and API requests work, and recent logs contain no 5xx errors.

## Decision

Keep Tandoor 2.7.1 and wait for an upstream fix to permit unauthenticated access to `/metrics`. Keep the existing alerts enabled; do not roll back the application or suppress the alerts while the app is healthy and no low-risk configuration-only fix is available.

## Consequences

Tandoor remains available to users, but application metrics are not scraped and the two target-health alerts continue to fire until the endpoint is accessible. The server-error alert cannot observe app 5xx while scraping is unavailable. Reassess when upstream releases a fix; then verify Mimir `up{job="tandoor"} == 1` and that the target-health alerts resolve.

## Alternatives considered

- Roll back to 2.6.15: could restore unauthenticated metrics access, but introduces downgrade-compatibility risk after the 2.7.1 migrations.
- Build and maintain a custom patched image: fixes the allowlist while retaining 2.7.1, but adds an image build/publish and maintenance path.
- Suppress the target alerts: rejected because it would hide the known scrape failure without restoring monitoring.

## Verification

On 2026-10-25, Grafana showed `tandoor-down` and `Scrape target down` firing and `tandoor-server-errors` inactive; Mimir returned `up{job="tandoor"} == 0`. The deployed Pod was 1/1 Ready, login/API requests succeeded, and recent logs showed no 5xx. No application or alert configuration was changed.

## Related

- [ADR-0028 - Migrate Tandoor to k0s](ADR-0028%20-%20Migrate%20Tandoor%20to%20k0s.md)
- [ADR-0033 - Tandoor 2.7.1 superuser email migration](ADR-0033%20-%20Tandoor%202.7.1%20superuser%20email%20migration.md)
- [Tandoor service note](../../.okf/tandoor.md)
