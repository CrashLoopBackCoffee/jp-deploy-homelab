---
tags: [homelab, adr, tandoor, observability, alerting]
type: adr
status: accepted
date: 2026-10-25
created: 2026-10-25
updated: 2026-10-25
adr: 35
---

# ADR-0035 - Tandoor metrics scrape with a session cookie

## Status

Accepted on 2026-10-25. Amends the scrape approach of [ADR-0034](ADR-0034%20-%20Tandoor%202.7.1%20metrics%20authentication.md); staying on 2.7.1 stands.

## Context

Tandoor 2.7.1 redirects an unauthenticated `GET /metrics` to `/account/login/?next=/metrics`, so `up{job="tandoor"} == 0` and the alerts `tandoor-down` (critical) and `Scrape target down` fired (ADR-0034). A personal access token or Bearer header cannot help: in the deployed pod, `cookbook/helper/scope_middleware.py` tries `OAuth2Authentication` and `XSessionTokenAuthentication` only for paths starting with `/api/` or `/_allauth/` (line 115) and redirects every other unauthenticated path (line 139). Upstream issue TandoorRecipes/recipes#4888 reports the same and is open without a fix. Django session authentication (`AuthenticationMiddleware`) works on any path. Sessions live in the database and `SESSION_COOKIE_AGE` is 365 days. A signed-in user without a space passes the middleware (no userspace and no `signup_token`), and django-prometheus then serves the metrics.

## Decision

Alloy scrapes `/metrics` with the `sessionid` cookie of a dedicated user `tandoor-metrics`: non-staff, non-superuser, no groups, no space, unusable password. The session key is stored as the password of the 1Password item `Homelab/Tandoor Metrics Scrape`. Pulumi resolves it (`alloy.tandoor-session`), builds the `sessionid=<key>` header value into the existing `alloy-targets` Secret (`tandoor-cookie`), and Alloy sends it as the `Cookie` header from a `local.file`. The scrape sets `follow_redirects = false`, so an invalid session fails as HTTP 302 rather than as an unparsable login page. Tandoor stays on 2.7.1; no alert is suppressed or changed.

The user `tandoor-metrics` was created with `manage.py shell` because the admin account `alten` is staff without the add-user permission (`/admin/auth/user/add/` returned 403). The session was forged in the user's own terminal (`SessionStore` with the user's id, backend and `get_session_auth_hash()`), so the key never entered an agent transcript.

## Consequences

- The session expires after 365 days (2027-10-25). Re-mint at least yearly: [Tandoor note](../../.okf/tandoor.md) has the runbook; then replace the 1Password password and run `pulumi up` in `services/observability`, because the value is resolved at deploy time.
- `tandoor-down` fires when the session expires, is flushed, or the user's password changes; it doubles as the expiry signal. A logout of that session also deletes it.
- The cookie grants only space-less web access as a non-staff user.
- Remove the cookie, the config field and the user when upstream exempts `/metrics` (#4888).

## Alternatives considered

- Wait for upstream (ADR-0034): leaves two alerts firing and server errors unobserved.
- Remote-user header authentication: rejected. The header holds no secret and allows impersonation unless Traefik strips it, and `RemoteUserBackend` auto-creates users.
- A patched image or a ConfigMap overlay of `scope_middleware.py`: maintenance on every upgrade.
- PAT or Bearer token: not accepted outside `/api/` and `/_allauth/`.

## Verification

On 2026-10-25: `GET /metrics` through a port-forward with `Host: tandoor.tandoor.svc` returned 200 with 580 `django_http*` lines with the cookie and 302 without it. After `pulumi up` (Secret `alloy-targets` replaced, Helm release `alloy` updated, nothing else), Mimir returned `up{job="tandoor"} == 1` and 697 series (pre-2.7.1 baseline: 261). Grafana reported `tandoor-down`, `Scrape target down` and `tandoor-server-errors` inactive/ok. Alloy logs showed no Tandoor errors.

## Related

- [ADR-0034 - Tandoor 2.7.1 metrics authentication](ADR-0034%20-%20Tandoor%202.7.1%20metrics%20authentication.md)
- [ADR-0028 - Migrate Tandoor to k0s](ADR-0028%20-%20Migrate%20Tandoor%20to%20k0s.md)
- [Tandoor service note](../../.okf/tandoor.md)
