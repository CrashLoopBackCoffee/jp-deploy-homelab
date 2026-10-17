---
tags:
  - homelab
  - adr
  - kubernetes
  - paperless
  - authentik
type: adr
status: accepted
date: 2026-10-15
created: 2026-10-15
updated: 2026-10-15
adr: 21
---

# ADR-0021 - Paperless single sign-on through the shared Authentik

## Status

Accepted on 2026-10-15. The Paperless 3.x upgrade it requires is **done and verified**. The Authentik side was rolled out by the user on 2026-10-17 (AX41 PR #97 merged, 1Password item `Paperless OIDC` created). The Paperless settings are in `feature/paperless-sso`; they are previewed (1 Secret replaced, 1 StatefulSet updated) but **not applied** until the issuer's discovery document returns 200.

## Context

[[ADR-0020 - Paperless fresh install with Nextcloud off-site backup]] deployed Paperless with local accounts only. The user prefers proper Authentik integration. An Authentik already runs at `https://id.jaypee.solutions` on the AX41 server (repository `jaypee-solutions/AX41`, Ansible and Docker Compose). It serves as the **identity broker for Mailcow**, so every mailbox owner can authenticate there and multi-factor authentication is enforced at Mailcow, not in Authentik. The donor `mp-deploy-homelab` connects its Paperless to its own Authentik (commit "connect paperless to authentik", 3 October) with a client blueprint, and `th-deploy-homelab` has run Paperless 3.x since September. Paperless can map a group claim to superuser only from v3.1.0; JP ran 2.18.4, and v3 can only be reached from 2.20.15.

## Decision

- **No second Authentik.** Paperless uses the existing one at `https://id.jaypee.solutions` through OpenID Connect (django-allauth, provider id `authentik`). The user's Mailcow-based MFA is unchanged and out of scope here.
- **Authentik side lives in the AX41 repository** (pull request `jaypee-solutions/AX41#97`), following that repository's ADR 0003: a blueprint creates the groups `paperless` and `paperless-admins` and binds both to the application slug `paperless`. The binding is a security requirement: an application without bindings is open to every user, and this Authentik also authenticates every Mailcow mailbox owner. The provider and application (redirect URI, flow, signing key, secret) are created in the Authentik UI by the user.
- **Groups.** `paperless-admins` members become Paperless superusers, `paperless` members join the Paperless group `paperless` (`PAPERLESS_SOCIAL_ACCOUNT_SYNC_GROUPS`, `PAPERLESS_SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP`). The group names are a contract between the two repositories.
- **Upgrade to Paperless 3.3.1**, staged as 2.18.4 → 2.20.15 → 3.3.1 as the migration guide requires, with a database backup and a restic backup taken first. The v3 consumer settings follow TH's working configuration, with QNAP's `@Recycle` and `@Recently-Snapshot` folders added to the ignored directories.
- **Local login stays** as break-glass (the generated `admin`, the login form, the API). A first SSO login creates the Paperless account automatically; Authentik decides who gets that far.
- **Secrets.** Client id and secret are read by Pulumi from a 1Password item `Paperless OIDC` in the `Homelab` vault, created by the user after the Authentik UI step. They reach Paperless through the existing config Secret, never through values or the repository.
- **Mail is postponed.** With the shared Authentik, the mail requirement is Paperless ingestion and notifications; the user deferred it.

## Consequences

- Paperless 3.3.1 is deployed and verified (2026-10-15): version and migrations, the real document intact, the consumer (an intake file consumed, a file in `@Recycle` ignored), form login through Traefik without the v3 proxy `403`, the nightly backup job with `restic check`, and a **disaster-recovery import of the Nextcloud backup into a clean throwaway v3 instance** (the document came back with an identical checksum). The earlier delete-and-restore gate of ADR-0020 was re-verified this way because the instance now holds a real document and a delete-and-restore on the live database would put it at risk.
- Paperless is no longer empty: a scanned document arrived through the QNAP intake on 2026-10-15 and is backed up (restic snapshot and database backup `paperless-db-pre-v3`).
- The SSO apply needs, from the user: the Authentik application and provider (settings listed in the AX41 note), the AX41 deployment, and the 1Password item. Until the item exists any Paperless preview that references it would fail, so the SSO code ships as a separate change.
- The `paperless` Paperless group must exist before group sync can use it, and its permissions are set in Paperless, not in Authentik.
- Authentik's own backup and availability are the AX41 repository's concern. If Authentik is down, Paperless still works through the local login.
- Changing the Paperless hostname or the allauth provider id means changing the redirect URI in Authentik too.

## Alternatives considered

- Deploy a second Authentik on k0s (the donor's design): rejected by the user; the shared one already brokers Mailcow and would split identities.
- Stay on Paperless 2.18.4 with permission-based admins: possible, but the user chose real superuser mapping; the instance was nearly empty at decision time.
- A fully declarative provider in the blueprint (as the donor does): conflicts with AX41's ADR 0003 and would need the client secret in the Ansible vault as well as in 1Password.

## Related notes

- [[ADR-0020 - Paperless fresh install with Nextcloud off-site backup]]
- [[ADR-0018 - PostgreSQL PITR and off-site recovery acceptance]]

## References

- [authentik: Integrate with Paperless-ngx](https://integrations.goauthentik.io/documentation/paperless-ngx)
- [Paperless-ngx v3 migration guide](https://docs.paperless-ngx.com/migration-v3/)
- [Paperless-ngx authentication and SSO settings](https://docs.paperless-ngx.com/configuration/#authentication)
