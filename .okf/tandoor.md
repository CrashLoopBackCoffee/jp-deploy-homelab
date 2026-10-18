---
type: Service
title: Tandoor (Pulumi, prepared, not deployed)
description: Migration of Tandoor Recipes from dockerhost to k0s with a dedicated CloudNativePG database and a Longhorn media volume, the prerequisites, and the data import and cutover runbook (ADR-0028).
timestamp: 2026-10-18T00:00:00Z
tags: [homelab, kubernetes, tandoor, cloudnativepg, longhorn, migration]
resource: https://app.pulumi.com/jaypee-solutions/tandoor/prod
---

# State

Written on branch `feature/tandoor` (ADR-0028). The stack `jaypee-solutions/tandoor/prod` exists; `pulumi preview` shows 16 resources to create and nothing is applied. It needs no new 1Password item. The legacy instance runs on `dockerhost` (`/opt/tandoor`: PostgreSQL 12, `vabene1111/recipes` untagged, a separate nginx) and is untouched. The motivation is in [dockerhost-services](./dockerhost-services.md): `dockerhost` has no backup, so moving the service is a gain by itself.

# What the stack creates

Namespace `tandoor`; CloudNativePG cluster `tandoor-db` (PostgreSQL 17, owner and database `tandoor`, Barman plugin to `cnpg-backups/tandoor-db/`, 21:00 UTC, covered by `cnpg-backup-stale`); Secret `tandoor-config` (generated `SECRET_KEY`); Longhorn PVC `mediafiles` (10 Gi, in the default recurring-job group, so backed up nightly at 02:00 UTC); Deployment `tandoor` (`Recreate`; the init container `migrate` runs `migrate` and `collectstatic`, static files live in an `emptyDir`); Service and IngressRoute for `tandoor.4jp.de`.

There is deliberately no own off-site copy (no restic, no Nextcloud): the QNAP copies from CloudNativePG and Longhorn are the backup, and the HBS 3 job will add the off-site copy for everything (ADR-0018, amended 2026-10-18).

Image facts that mattered: the Tandoor 2 image serves everything on port 80 (nginx plus gunicorn) and reads `TANDOOR_PORT`; the Service named `tandoor` would inject `TANDOOR_PORT=tcp://...`, so the Pod sets `enableServiceLinks: false` and `TANDOOR_PORT=80`. The readiness probe is a TCP probe because an HTTP probe sends the Pod IP as host and gets `DisallowedHost`.

# Prerequisites (user)

Facts from `dockerhost` (read-only, in your own terminal because the agent cannot sign with the SSH agent), to decide the pinned version and the settings:

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
5. Restore the media: start a short helper Pod that mounts the PVC `mediafiles`, unpack the tar into it, set the group to `65534`, delete the Pod.
6. Scale the application back to one replica. The `migrate` init container brings the schema to the pinned version. Test with `curl --resolve tandoor.4jp.de:443:10.10.88.1 https://tandoor.4jp.de/` and by signing in (a browser needs a hosts entry for the test).
7. Confirm the protection before the legacy instance is stopped: an on-demand or scheduled CloudNativePG backup of `tandoor-db` is `completed` after the import, and a Longhorn backup of `mediafiles` exists after the 02:00 UTC run. Keep the dump and tar files until then.
8. **Cutover** (a separate pull request): add the dnsmasq host record for `tandoor` pointing at the Traefik address, preview, apply, and check `dig tandoor.4jp.de` from a LAN client. Stop the legacy containers (do not delete them) and keep them for the agreed period.
9. Follow-up in stage 2, with approval: remove the legacy role, `/opt/tandoor`, the Cloudflare record and the Traefik labels.

# Open points

- The legacy schema version and image are unknown until the prerequisite commands have run.
- ENABLE_METRICS would expose Tandoor's `/metrics`; it is not wired. Decide after the preferences are known.
- A restore of `tandoor-db` from its QNAP backup has not been rehearsed for this cluster; the method is the verified one of ADR-0017 and ADR-0018.

Related: ADR-0028, ADR-0018, ADR-0023, [dockerhost-services](./dockerhost-services.md), [Paperless](./paperless.md), [Retiring the legacy dockerhost monitoring stack](./legacy-monitoring-migration.md).
