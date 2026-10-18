---
tags:
  - homelab
  - adr
  - kubernetes
  - tandoor
  - backup
type: adr
status: accepted
date: 2026-10-18
created: 2026-10-18
updated: 2026-10-18
adr: 28
---

# ADR-0028 - Migrate Tandoor to k0s

## Status

Accepted on 2026-10-18. The Pulumi stack is written; nothing is deployed and no data has moved yet.

## Context

Tandoor Recipes runs on `dockerhost` as three containers from an Ansible role (`/opt/tandoor`): PostgreSQL 12, the `vabene1111/recipes` image (untagged, kept current by Watchtower) and a separate nginx for static and media files, behind the host's Traefik at `tandoor.4jp.de`. It holds real recipes and uploaded images. The donor TH has a `tandoor` workspace (Tandoor 2.6.15, Postgres through the shared helper, Traefik, no backup beyond the database). MP has none.

[[ADR-0018 - PostgreSQL PITR and off-site recovery acceptance]] forbids moving application data before the encrypted HBS 3 off-site copy is verified, and the remote NAS is still offline. Paperless was exempt because it was a fresh install with its own off-site copy ([[ADR-0020 - Paperless fresh install with Nextcloud off-site backup]]). Tandoor has existing data, so it needs an explicit decision.

## Decision

- **The HBS 3 gate is waived for Tandoor, on one condition: the application has its own off-site copy that is restored successfully before the legacy instance is switched off.** The user chose this on 2026-10-18 over waiting for the remote NAS. The legacy instance on `dockerhost` stays untouched (stopped, not deleted) until that restore is proven. Every other application still waits for HBS 3.
- **A new workspace `services/tandoor`** (stack `jaypee-solutions/tandoor/prod`), shaped like Paperless: a one-replica Deployment (`Recreate`, the media volume is ReadWriteOnce), a Longhorn `mediafiles` volume, static files in an `emptyDir` that `collectstatic` rebuilds on every start, Traefik IngressRoute with the wildcard certificate.
- **Database: a dedicated CloudNativePG cluster `tandoor-db`** from the shared helper (PostgreSQL 17, Barman plugin to its own prefix in `cnpg-backups`, 21:00 UTC). The legacy PostgreSQL 12 is not upgraded in place: the data moves as a custom-format `pg_dump` restored with `pg_restore`, and the new image's `migrate` brings the schema forward.
- **Off-site copy: restic to the existing Nextcloud**, one CronJob without cluster permissions. An init container writes `pg_dump --format=custom` into an `emptyDir`, then restic backs up the dump and the read-only media volume (the pod is pinned to the application pod's node because the volume is ReadWriteOnce). Same Nextcloud account as Paperless, separate folder `tandoor` and a separate restic password (1Password item `Tandoor Backup`). Retention 7 daily, 4 weekly, 6 monthly. The CronJob runs at 01:30 UTC.
- **Accounts stay local.** Authentik single sign-on is a later, separate change (the user decided on 2026-10-18).
- **Cutover by DNS.** `tandoor.4jp.de` currently resolves to `dockerhost` (`192.168.178.125`) through the public Cloudflare record, on the LAN as well. The first deployment has no local DNS record and is tested with `curl --resolve` against `10.10.88.1`; the cutover change adds the dnsmasq host record (`utils.opnsense.dnsmasq.host.Host`, as for Paperless) and takes effect for LAN clients at once. The Cloudflare record is removed with the other legacy names in stage 2 of [[ADR-0023 - Retire the legacy dockerhost monitoring stack]].
- **No new secret key is carried over.** A new `SECRET_KEY` is generated, so users sign in again once.

## Consequences

- Tandoor's off-site copy is the only one outside the QNAP until HBS 3 works; its freshness needs an alert like `paperless-backup-stale` (follow-up in the `observability` stack once the first backup has run, otherwise the rule fires on a CronJob that does not exist yet).
- The restore of the dump and the media into the new instance is a manual runbook (`.okf/tandoor.md`), done with the application scaled to zero so `migrate` does not race the restore.
- The legacy image tag is unknown (`latest`). The migration state of the legacy database must be read before the first restore, to confirm that the pinned 2.6.15 is the same version or newer.
- Deleting the legacy role, `/opt/tandoor` and the public DNS record is stage-2 work and needs the user's approval.

## Alternatives considered

- Wait for HBS 3: safest in the letter of ADR-0018, but blocks the migration on an unscheduled hardware task while the legacy copy keeps running.
- Rely on CloudNativePG and Longhorn backups on the QNAP only: no off-site copy at all.
- Keep the donor's `Deployment` with a persistent `staticfiles` volume and Bitnami-style env wiring: the static volume is reproducible and only adds a volume to back up.
- Tandoor's own export: not a faithful full backup (users, shopping lists and meal plans are not all covered); `pg_dump` plus the media volume is.

## Related notes

- [[ADR-0016 - QuObjects backup target and encrypted offsite copy]]
- [[ADR-0017 - First CloudNativePG cluster and QuObjects recovery]]
- [[ADR-0018 - PostgreSQL PITR and off-site recovery acceptance]]
- [[ADR-0020 - Paperless fresh install with Nextcloud off-site backup]]
- [[ADR-0023 - Retire the legacy dockerhost monitoring stack]]
