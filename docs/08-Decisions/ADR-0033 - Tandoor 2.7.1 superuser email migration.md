---
tags: [homelab, adr, tandoor, accounts, database]
type: adr
status: accepted
date: 2026-10-24
created: 2026-10-24
updated: 2026-10-24
adr: 33
---

# ADR-0033 - Tandoor 2.7.1 superuser email migration

## Status

Accepted and applied on 2026-10-24.

## Context

The first Tandoor 2.7.1 rollout failed in migration `0243_auto_20261018_1149`. For each superuser without a verified `EmailAddress`, the migration creates `<username>@default-adminmail.tandoor` as primary and verified. Superuser 1 already had a primary but unverified address, so the insert violated `unique_primary_email`. The Deployment was rolled back to 2.6.15. The user approved account-data remediation; a fresh CloudNativePG plugin backup was taken before changing the row.

## Decision

Preserve the existing address and its `verified=False` state, but set it to non-primary. Add the migration's own `<username>@default-adminmail.tandoor` address as primary and verified, so migration 0243 can complete. Do not delete the existing address or represent it as verified without evidence. No password or other user fields change.

## Consequences

The original address remains on the account as unverified and non-primary. The primary address is the migration's synthetic fallback; it is not a claim that a deliverable mailbox was verified. If email delivery is needed, the user should add and verify a real address in Tandoor.

## Verification

- `tandoor-db-before-email-remediation` completed using the configured Barman Cloud plugin before the account change.
- Migration 0243 is recorded after the 2.7.1 rollout; CNPG is healthy.
- A raw database query found 10 recipes (IDs 1–10), matching the recorded import count. `/accounts/login/` returned HTTP 200 and the post-apply Pulumi preview reported 18 unchanged.
- A diagnostic `manage.py check` exited 137 and the app Pod recorded one `OOMKilled` restart. The Pod returned to 1/1 Ready and the login page returned HTTP 200 afterward; no resource settings were changed.

## Alternatives considered

- Mark the existing address verified: rejected because no verification occurred.
- Delete the existing address: rejected because it would destroy user data.
- Leave the conflict and wait for an upstream migration change: rejected because the user approved the migration-compatible account repair and the failed rollout had already been backed out.

## Related

- [ADR-0028 - Migrate Tandoor to k0s](ADR-0028%20-%20Migrate%20Tandoor%20to%20k0s.md)
- [Tandoor service note](../../.okf/tandoor.md)

## Citations

[1] [Tandoor 2.7.1 migration 0243](https://raw.githubusercontent.com/TandoorRecipes/recipes/2.7.1/cookbook/migrations/0243_auto_20261018_1149.py)
