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

Accepted on 2026-10-18. The Pulumi stack is written and previews cleanly (16 resources to create); nothing is deployed and no data has moved yet. Amended the same day: the first draft added an own off-site copy (restic to the Nextcloud); the user rejected it, see Decision.

## Context

Tandoor Recipes runs on `dockerhost` as three containers from an Ansible role (`/opt/tandoor`): PostgreSQL 12, the `vabene1111/recipes` image (untagged, kept current by Watchtower) and a separate nginx for static and media files, behind the host's Traefik at `tandoor.4jp.de`. It holds real recipes and uploaded images. The donor TH has a `tandoor` workspace (Tandoor 2.6.15, shared Postgres helper, Traefik); MP has none.

**`dockerhost` has no backup at all** (stated by the user, 2026-10-18): its data lives on a single SSD, so one disk failure would lose every service on it. [[ADR-0018 - PostgreSQL PITR and off-site recovery acceptance]] had made the encrypted HBS 3 off-site copy a precondition for moving any application data, which ignored that the starting point is no backup.

## Decision

- **Moving a service from `dockerhost` to k0s is itself a safety gain and is not gated on HBS 3.** On k0s the data has a local copy on the node and a second, independent copy on the QNAP (a RAID5 volume): CloudNativePG base backups with WAL archiving to QuObjects for the database ([[ADR-0017 - First CloudNativePG cluster and QuObjects recovery]], restore and time-targeted PITR verified) and Longhorn's nightly backup of the volumes to QuObjects (restore verified 2026-10-17). The encrypted HBS 3 job to the remote NAS follows soon and adds the off-site copy for all services at once. See the amendment in ADR-0018.
- **Tandoor gets no extra off-site copy.** No restic job and no Nextcloud repository, so no new secrets or prerequisites. The user chose this on 2026-10-18.
- **A new workspace `services/tandoor`** (stack `jaypee-solutions/tandoor/prod`), shaped like Paperless: a one-replica Deployment (`Recreate`, the media volume is ReadWriteOnce), a Longhorn `mediafiles` volume (in Longhorn's default recurring-job group, so it is backed up nightly without extra configuration), static files in an `emptyDir` that `collectstatic` rebuilds on every start, a Traefik IngressRoute with the wildcard certificate.
- **Database: a dedicated CloudNativePG cluster `tandoor-db`** from the shared helper (PostgreSQL 17, Barman plugin to its own prefix in `cnpg-backups`, daily 21:00 UTC, 14-day recovery window). The legacy PostgreSQL 12 is not upgraded in place: the data moves as a custom-format `pg_dump` restored with `pg_restore`, and the new image's `migrate` brings the schema forward. `cnpg-backup-stale` covers the new cluster.
- **The legacy instance stays until the migration is proven.** It is stopped, not deleted, after cutover, and removal is stage-2 work that needs the user's approval. Its stopped containers are the rollback.
- **Accounts stay local.** Authentik single sign-on is a later, separate change.
- **Cutover by DNS.** `tandoor.4jp.de` currently resolves to `dockerhost` (`192.168.178.125`) through the public Cloudflare record, on the LAN as well. The first deployment has no local DNS record and is tested with `curl --resolve` against `10.10.88.1`; the cutover change adds the dnsmasq host record (`utils.opnsense.dnsmasq.host.Host`, as for Paperless) and takes effect for LAN clients at once. The Cloudflare record is removed with the other legacy names in stage 2 of [[ADR-0023 - Retire the legacy dockerhost monitoring stack]].
- **No secret key is carried over.** A new `SECRET_KEY` is generated, so users sign in again once.

## Consequences

- Until HBS 3 runs, the QNAP holds the only copy besides the node's own disks. A RAID5 volume survives one disk failure but not deletion, ransomware, a controller or QNAP failure, or a fire. That is still strictly better than a single SSD without any backup, and it is the same exposure as every other service on the cluster.
- The import of the dump and the media into the new instance is a manual runbook (`.okf/tandoor.md`), done with the application scaled to zero so `migrate` does not race the restore. The first restore is also the first test of the data path; the CloudNativePG base backup of `tandoor-db` should complete before the legacy instance is stopped.
- The legacy image tag is unknown (`latest`). The migration state of the legacy database must be read before the first restore, to confirm that the pinned 2.6.15 is the same version or newer.
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
