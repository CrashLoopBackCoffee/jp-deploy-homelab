---
type: Service
title: Tandoor (Pulumi, prepared, not deployed)
description: Migration of Tandoor Recipes from dockerhost to k0s with a dedicated CloudNativePG database, restic to the off-site Nextcloud, the prerequisites, and the data import and cutover runbook (ADR-0028).
timestamp: 2026-10-18T00:00:00Z
tags: [homelab, kubernetes, tandoor, cloudnativepg, backup, restic, nextcloud, migration]
resource: https://app.pulumi.com/jaypee-solutions/tandoor/prod
---

# State

Written on branch `feature/tandoor` (ADR-0028); the stack `jaypee-solutions/tandoor/prod` exists but is empty, and nothing is applied. A preview needs the 1Password item `Tandoor Backup` first. The legacy instance runs on `dockerhost` (`/opt/tandoor`: PostgreSQL 12, `vabene1111/recipes` untagged, a separate nginx) and is untouched.

# What the stack creates

Namespace `tandoor`; CloudNativePG cluster `tandoor-db` (PostgreSQL 17, owner and database `tandoor`, Barman plugin to `cnpg-backups/tandoor-db/`, 21:00 UTC); Secret `tandoor-config` (generated `SECRET_KEY`); Longhorn PVC `mediafiles` (10 Gi); Deployment `tandoor` (`Recreate`; the init container `migrate` runs `migrate` and `collectstatic`, static files live in an `emptyDir`); Service and IngressRoute for `tandoor.4jp.de`; CronJob `tandoor-backup` (01:30 UTC) with the Secret `tandoor-backup-secrets`.

Image facts that mattered: the Tandoor 2 image serves everything on port 80 (nginx plus gunicorn) and reads `TANDOOR_PORT`; the Service named `tandoor` would inject `TANDOOR_PORT=tcp://...`, so the Pod sets `enableServiceLinks: false` and `TANDOOR_PORT=80`. The readiness probe is a TCP probe because an HTTP probe sends the Pod IP as host and gets `DisallowedHost`.

# Backup

The CronJob runs an init container `pg_dump --format=custom` into an `emptyDir`, then restic backs up the dump and the read-only media volume to `rclone:nextcloud:tandoor` (same Nextcloud account as Paperless, restic password in `Tandoor Backup`), applies the retention and runs `restic check`. The Pod is pinned to the application Pod's node with a required pod affinity, because the media volume is ReadWriteOnce. The first run creates the repository.

# Prerequisites (user)

1. 1Password item `Tandoor Backup` in the `Homelab` vault with a generated password (this creates an item, so it needs the desktop app and approval; the service account is read-only). Without it the config cannot resolve.
2. Facts from `dockerhost` (read-only, in your own terminal because the agent cannot sign with the SSH agent), to decide the pinned version and the settings:
   - container names: `sudo docker ps --filter name=recipes --format '{{.Names}}  {{.Image}}'`
   - schema state: `sudo docker exec <web container> sh -c 'cd /opt/recipes && . venv/bin/activate && python manage.py showmigrations cookbook | tail -3'`
   - sizes: `sudo du -sh /opt/tandoor/mediafiles /opt/tandoor/postgresql`
   - non-secret preferences: `sudo grep -E '^(FRACTION_PREF_DEFAULT|COMMENT_PREF_DEFAULT|SHOPPING_MIN_AUTOSYNC_INTERVAL|ENABLE_PDF_EXPORT|ENABLE_METRICS|DEBUG|REVERSE_PROXY_AUTH|TIMEZONE)=' /opt/tandoor/.env` (never paste the file: it holds `SECRET_KEY` and the database password)

# Runbook: import and cutover

Rehearse first with the legacy instance running, then repeat after stopping it so that no recipe is lost.

1. Deploy with `pulumi up` (preview first). The first start migrates an empty database.
2. Scale the application to zero: `kubectl -n tandoor scale deploy/tandoor --replicas=0`.
3. Dump on `dockerhost`: `sudo docker exec <db container> sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > ~/tandoor.dump`, and pack the media: `sudo tar -C /opt/tandoor/mediafiles -cf ~/tandoor-media.tar .`. Copy both to the workstation.
4. Restore the database: copy the dump into the `tandoor-db-1` pod and run `pg_restore --clean --if-exists --no-owner --role=tandoor -d tandoor`.
5. Restore the media: start a short helper Pod that mounts the PVC `mediafiles`, unpack the tar into it, set the owner to the group `65534`, delete the Pod.
6. Scale the application back to one replica. The `migrate` init container brings the schema to the pinned version. Test with `curl --resolve tandoor.4jp.de:443:10.10.88.1 https://tandoor.4jp.de/` and by signing in (a browser needs a hosts entry for the test).
7. Prove the off-site copy: run `kubectl -n tandoor create job --from=cronjob/tandoor-backup tandoor-backup-first`, check that `restic check` is clean, then restore the latest snapshot into a scratch location and compare file counts and checksums of the media, and `pg_restore --list` the dump.
8. **Cutover** (a separate pull request): add the dnsmasq host record for `tandoor` pointing at the Traefik address, preview, apply, and check `dig tandoor.4jp.de` from a LAN client. Stop the legacy containers (do not delete them) and keep them for the agreed period.
9. Follow-ups: a `tandoor-backup-stale` alert next to `paperless-backup-stale` in `services/observability/observability/alert_rules.py` once the backup has succeeded once; remove the legacy role, `/opt/tandoor`, the Cloudflare record and the Traefik labels in stage 2 with approval.

# Open points

- The legacy schema version and image are unknown until the prerequisite commands have run.
- ENABLE_METRICS would expose Tandoor's `/metrics`; it is not wired. Decide after the preferences are known.

Related: ADR-0028, ADR-0020, ADR-0023, [Paperless](./paperless.md), [Retiring the legacy dockerhost monitoring stack](./legacy-monitoring-migration.md).
