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

Accepted on 2026-10-18. The Pulumi stack is applied (16 resources, PR #31) and runs against an empty database; no data has moved yet. Amended the same day: the first draft added an own off-site copy (restic to the Nextcloud); the user rejected it, see Decision.

## Context

Tandoor Recipes runs on `dockerhost` as three containers (`/opt/tandoor`; names and images read on the host on 2026-10-18): `tandoor_db_recipes_1` (`postgres:17-alpine`), `tandoor_web_recipes_1` (`ghcr.io/tandoorrecipes/recipes:latest`, which contains nginx and gunicorn) and `tandoor_adminer_recipes_1` (`adminer:latest`, a database UI), behind the host's Traefik at `tandoor.4jp.de`. The Ansible role in the repository describes something older (PostgreSQL 12, `vabene1111/recipes`, a separate nginx container), so the host has drifted from its code. Tandoor holds real recipes and uploaded images. The donor TH has a `tandoor` workspace (Tandoor 2.6.15, shared Postgres helper, Traefik); MP has none.

**`dockerhost` has no backup at all** (stated by the user, 2026-10-18): its data lives on a single SSD, so one disk failure would lose every service on it. [[ADR-0018 - PostgreSQL PITR and off-site recovery acceptance]] had made the encrypted HBS 3 off-site copy a precondition for moving any application data, which ignored that the starting point is no backup.

## Decision

- **Moving a service from `dockerhost` to k0s is itself a safety gain and is not gated on HBS 3.** On k0s the data has a local copy on the node and a second, independent copy on the QNAP (a RAID5 volume): CloudNativePG base backups with WAL archiving to QuObjects for the database ([[ADR-0017 - First CloudNativePG cluster and QuObjects recovery]], restore and time-targeted PITR verified) and Longhorn's nightly backup of the volumes to QuObjects (restore verified 2026-10-17). The encrypted HBS 3 job to the remote NAS follows soon and adds the off-site copy for all services at once. See the amendment in ADR-0018.
- **Tandoor gets no extra off-site copy.** No restic job and no Nextcloud repository, so no new secrets or prerequisites. The user chose this on 2026-10-18.
- **A new workspace `services/tandoor`** (stack `jaypee-solutions/tandoor/prod`), shaped like Paperless: a one-replica Deployment (`Recreate`, the media volume is ReadWriteOnce), a Longhorn `mediafiles` volume (in Longhorn's default recurring-job group, so it is backed up nightly without extra configuration), static files in an `emptyDir` that `collectstatic` rebuilds on every start, a Traefik IngressRoute with the wildcard certificate.
- **Database: a dedicated CloudNativePG cluster `tandoor-db`** from the shared helper (PostgreSQL 17, Barman plugin to its own prefix in `cnpg-backups`, daily 21:00 UTC, 14-day recovery window). The legacy database is also PostgreSQL 17, but its data directory is not reused: the data moves as a custom-format `pg_dump` restored with `pg_restore`, and the new image's `migrate` brings the schema forward. `cnpg-backup-stale` covers the new cluster. Adminer is not migrated; `kubectl exec` into the CloudNativePG pod serves the same purpose.
- **The legacy instance stays until the migration is proven.** It is stopped, not deleted, after cutover, and removal is stage-2 work that needs the user's approval. Its stopped containers are the rollback.
- **Accounts stay local.** Authentik single sign-on is a later, separate change.
- **Cutover by DNS.** `tandoor.4jp.de` currently resolves to `dockerhost` (`192.168.178.125`) through the public Cloudflare record, on the LAN as well. The first deployment has no local DNS record and is tested with `curl --resolve` against `10.10.88.1`; the cutover change adds the dnsmasq host record (`utils.opnsense.dnsmasq.host.Host`, as for Paperless) and takes effect for LAN clients at once. The Cloudflare record is removed with the other legacy names in stage 2 of [[ADR-0023 - Retire the legacy dockerhost monitoring stack]].
- **No secret key is carried over.** A new `SECRET_KEY` is generated, so users sign in again once.

## Consequences

- Until HBS 3 runs, the QNAP holds the only copy besides the node's own disks. A RAID5 volume survives one disk failure but not deletion, ransomware, a controller or QNAP failure, or a fire. That is still strictly better than a single SSD without any backup, and it is the same exposure as every other service on the cluster.
- The import of the dump and the media into the new instance is a manual runbook (`.okf/tandoor.md`), done with the application scaled to zero so `migrate` does not race the restore. The first restore is also the first test of the data path; the CloudNativePG base backup of `tandoor-db` should complete before the legacy instance is stopped.
- Read on the host on 2026-10-18: the legacy image was built on 2026-09-07, the day 2.6.15 was released, its newest applied migration is `cookbook 0242_space_household_setup_completed`, which is also the newest migration in the 2.6.15 source, and its database is PostgreSQL 17.11. The pinned 2.6.15 is therefore the same version, the import needs no schema upgrade, and the dump from 17.11 restores into the 17.10 image. The data is small: 16 MB database, under 1 MB of media, so the `mediafiles` volume is 2 Gi.
- Preferences carried over: `FRACTION_PREF_DEFAULT=0`, `COMMENT_PREF_DEFAULT=1`, `SHOPPING_MIN_AUTOSYNC_INTERVAL=5`, `ENABLE_PDF_EXPORT=1`, and `ENABLE_METRICS=1` (see the next point). Not carried: `ALLOWED_HOSTS=*` (the stack sets the hostname). PDF export may need more memory than the 1 Gi limit; check on first use.
- **Metrics are enabled and scraped (the user's decision, 2026-10-18).** Tandoor serves `/metrics` (django-prometheus) on the application port without authentication, and the legacy Prometheus never scraped it. Here Alloy scrapes the Service `tandoor.tandoor.svc:80` every 30 seconds as job `tandoor`; that in-cluster name is added to `ALLOWED_HOSTS` because Django rejects other Host headers. The IngressRoute does not route `/metrics` (`Host(...) && !PathPrefix('/metrics')`), so the endpoint is not reachable from the LAN. The existing `Scrape target down` rule covers the job. The scrape is applied after the import, because the application is scaled to zero during it.
- The same reasoning applies to the other services still on `dockerhost` (see `.okf/dockerhost-services.md`); each one needs its own decision about how its state moves.

## Alternatives considered

- Wait for HBS 3 before moving anything: keeps a service on a host with no backup in order to protect it with a backup that does not exist yet.
- An own off-site copy with restic to the Nextcloud (the first draft of this ADR, Paperless pattern): more moving parts, a new secret and a second restore path, for a service whose next safeguard is the HBS 3 job that is coming anyway. Rejected by the user.
- Keep the donor's persistent `staticfiles` volume: the static volume is reproducible and only adds a volume to back up.
- Tandoor's own export: not a faithful full backup (users, shopping lists and meal plans are not all covered); `pg_dump` plus the media volume is.

## Related notes

- [[ADR-0016 - QuObjects backup target and encrypted offsite copy]]
- [[ADR-0017 - First CloudNativePG cluster and QuObjects recovery]]
- [[ADR-0018 - PostgreSQL PITR and off-site recovery acceptance]]
- [[ADR-0020 - Paperless fresh install with Nextcloud off-site backup]]
- [[ADR-0023 - Retire the legacy dockerhost monitoring stack]]
