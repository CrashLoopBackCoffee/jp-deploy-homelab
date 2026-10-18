---
type: Service
title: Tandoor (Pulumi, prepared, not deployed)
description: Migration of Tandoor Recipes from dockerhost to k0s with a dedicated CloudNativePG database and a Longhorn media volume, the prerequisites, and the data import and cutover runbook (ADR-0028).
timestamp: 2026-10-18T00:00:00Z
tags: [homelab, kubernetes, tandoor, cloudnativepg, longhorn, migration]
resource: https://app.pulumi.com/jaypee-solutions/tandoor/prod
---

# State

Written on branch `feature/tandoor` (ADR-0028). The stack `jaypee-solutions/tandoor/prod` exists; `pulumi preview` shows 16 resources to create and nothing is applied. It needs no new 1Password item. The legacy instance runs on `dockerhost` (`/opt/tandoor`) as `tandoor_db_recipes_1` (`postgres:17-alpine`), `tandoor_web_recipes_1` (`ghcr.io/tandoorrecipes/recipes:latest`) and `tandoor_adminer_recipes_1` (`adminer:latest`) and is untouched. The Ansible role in the repository (PostgreSQL 12, `vabene1111/recipes`, separate nginx) is out of date, so trust the host, not the role. The motivation is in [dockerhost-services](./dockerhost-services.md): `dockerhost` has no backup, so moving the service is a gain by itself.

# What the stack creates

Namespace `tandoor`; CloudNativePG cluster `tandoor-db` (PostgreSQL 17, owner and database `tandoor`, Barman plugin to `cnpg-backups/tandoor-db/`, 21:00 UTC, covered by `cnpg-backup-stale`); Secret `tandoor-config` (generated `SECRET_KEY`); Longhorn PVC `mediafiles` (10 Gi, in the default recurring-job group, so backed up nightly at 02:00 UTC); Deployment `tandoor` (`Recreate`; the init container `migrate` runs `migrate` and `collectstatic`, static files live in an `emptyDir`); Service and IngressRoute for `tandoor.4jp.de`.

There is deliberately no own off-site copy (no restic, no Nextcloud): the QNAP copies from CloudNativePG and Longhorn are the backup, and the HBS 3 job will add the off-site copy for everything (ADR-0018, amended 2026-10-18).

Image facts that mattered: the Tandoor 2 image serves everything on port 80 (nginx plus gunicorn) and reads `TANDOOR_PORT`; the Service named `tandoor` would inject `TANDOOR_PORT=tcp://...`, so the Pod sets `enableServiceLinks: false` and `TANDOOR_PORT=80`. The readiness probe is a TCP probe because an HTTP probe sends the Pod IP as host and gets `DisallowedHost`.

# Prerequisites (user)

Facts from `dockerhost`, read on 2026-10-18 (see the results below). Read-only, in your own terminal because the agent cannot sign with the SSH agent. Container names are known (`tandoor_web_recipes_1`, `tandoor_db_recipes_1`); the host paths are not known in advance, because the host drifted from its Ansible role, so the script reads them from the mounts. It prints no secret: the preference list is a fixed allow-list.

```bash
W=tandoor_web_recipes_1; D=tandoor_db_recipes_1
echo "== image"; sudo docker image inspect ghcr.io/tandoorrecipes/recipes:latest --format '{{.Created}} {{index .RepoDigests 0}}'
echo "== version"; sudo docker exec $W sh -c 'cat /opt/recipes/recipes/version.py 2>/dev/null || find /opt/recipes -maxdepth 2 -name version.py'
echo "== migrations"; sudo docker exec $W sh -c 'cd /opt/recipes && . venv/bin/activate && python manage.py showmigrations cookbook | tail -3'
echo "== mounts"; sudo docker inspect -f '{{.Name}}{{"\n"}}{{range .Mounts}}  {{.Type}} {{.Source}} -> {{.Destination}}{{"\n"}}{{end}}' $W $D
echo "== sizes"; for s in $(sudo docker inspect -f '{{range .Mounts}}{{.Source}} {{end}}' $W $D); do sudo du -sh "$s"; done
echo "== database"; sudo docker exec $D sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "select version(); select pg_size_pretty(pg_database_size(current_database()));"'
echo "== preferences"; sudo docker exec $W printenv | grep -E '^(FRACTION_PREF_DEFAULT|COMMENT_PREF_DEFAULT|SHOPPING_MIN_AUTOSYNC_INTERVAL|ENABLE_PDF_EXPORT|ENABLE_METRICS|DEBUG|REVERSE_PROXY_AUTH|TIMEZONE|TZ|ALLOWED_HOSTS|GUNICORN_MEDIA|CSRF_TRUSTED_ORIGINS)='
```

Results (2026-10-18): image `ghcr.io/tandoorrecipes/recipes:latest` built 2026-09-07 (the 2.6.15 release date); newest applied migration `cookbook 0242_space_household_setup_completed` (the newest in the 2.6.15 source, so no schema upgrade); PostgreSQL 17.11, database 16 MB; media `/opt/tandoor/mediafiles` 988 KB, database directory `/opt/tandoor/postgresql` 71 MB, the static files volume is rebuilt by `collectstatic` and is not migrated; preferences `FRACTION_PREF_DEFAULT=0`, `COMMENT_PREF_DEFAULT=1`, `SHOPPING_MIN_AUTOSYNC_INTERVAL=5`, `ENABLE_PDF_EXPORT=1`, `ENABLE_METRICS=1`, `DEBUG=0`, `TZ=Europe/Berlin`, `GUNICORN_MEDIA=0`, `ALLOWED_HOSTS=*`. All are in the stack config except `DEBUG`, `TZ`, `GUNICORN_MEDIA` (the stack sets them) and `ALLOWED_HOSTS` (the stack sets the hostname and the scrape name).

# Runbook: import and cutover

Rehearse first with the legacy instance running, then repeat after stopping it so that no recipe is lost.

1. Deploy with `pulumi up` (preview first). The first start migrates an empty database.
2. Scale the application to zero: `kubectl -n tandoor scale deploy/tandoor --replicas=0`.
3. Dump on `dockerhost`: `sudo docker exec tandoor_db_recipes_1 sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > ~/tandoor.dump`, and pack the media: `sudo tar -C /opt/tandoor/mediafiles -cf ~/tandoor-media.tar .`. Copy both to the workstation (together about 17 MB).
4. Restore the database: copy the dump into the `tandoor-db-1` pod and run `pg_restore --clean --if-exists --no-owner --role=tandoor -d tandoor`.
5. Restore the media: start a short helper Pod that mounts the PVC `mediafiles`, unpack the tar into it, set the group to `65534`, delete the Pod.
6. Scale the application back to one replica. The `migrate` init container brings the schema to the pinned version. Test with `curl --resolve tandoor.4jp.de:443:10.10.88.1 https://tandoor.4jp.de/` and by signing in (a browser needs a hosts entry for the test).
7. Confirm the protection before the legacy instance is stopped: an on-demand or scheduled CloudNativePG backup of `tandoor-db` is `completed` after the import, and a Longhorn backup of `mediafiles` exists after the 02:00 UTC run. Keep the dump and tar files until then.
8. **Cutover** (a separate pull request): add the dnsmasq host record for `tandoor` pointing at the Traefik address, preview, apply, and check `dig tandoor.4jp.de` from a LAN client. Stop the legacy containers (do not delete them) and keep them for the agreed period.
9. Follow-up in stage 2, with approval: remove the legacy role, `/opt/tandoor`, the Cloudflare record and the Traefik labels.

# Open points

- PDF export (`ENABLE_PDF_EXPORT=1`) may need more than the 1 Gi memory limit; check the first export and raise the limit if the pod is killed.
- **Metrics** (ADR-0028): `ENABLE_METRICS=1`; Alloy scrapes `tandoor.tandoor.svc:80/metrics` (job `tandoor`, `services/observability/assets/alloy/config.alloy`); the IngressRoute does not route `/metrics`. Apply the observability change only after the import, otherwise `Scrape target down` fires while the application is scaled to zero. Verify afterwards: `up{job="tandoor"} == 1`, `django_http_requests_total_by_method_total` has samples, and `curl --resolve tandoor.4jp.de:443:10.10.88.1 https://tandoor.4jp.de/metrics` returns 404.
- A restore of `tandoor-db` from its QNAP backup has not been rehearsed for this cluster; the method is the verified one of ADR-0017 and ADR-0018.

Related: ADR-0028, ADR-0018, ADR-0023, [dockerhost-services](./dockerhost-services.md), [Paperless](./paperless.md), [Retiring the legacy dockerhost monitoring stack](./legacy-monitoring-migration.md).
