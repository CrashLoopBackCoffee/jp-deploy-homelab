---
type: Service
title: Tandoor (Pulumi, applied; current image 2.7.1)
description: Tandoor Recipes migration from dockerhost to k0s, including its CloudNativePG database, Longhorn media volume, import/cutover, successful 2.7.1 upgrade after superuser email conflict remediation, and the metrics-auth incident, decision and session-cookie scrape with its re-mint runbook (ADR-0028, ADR-0033, ADR-0034, ADR-0035).
timestamp: 2026-10-25T11:30:00Z
tags: [homelab, kubernetes, tandoor, cloudnativepg, longhorn, migration]
resource: https://app.pulumi.com/jaypee-solutions/tandoor/prod
---

# State

Applied on 2026-10-18 from branch `feature/tandoor` (PR #31, ADR-0028): stack `jaypee-solutions/tandoor/prod`, 16 resources, CloudNativePG database and Longhorn media volume. The user imported the recipes and media, stopped the legacy service, pointed Cloudflare at k0s, and confirmed login and content. On 2026-10-24, the initial 2.7.1 rollout failed in migration `0243_auto_20261018_1149` because superuser 1 had a primary unverified email; it was rolled back to 2.6.15. After a fresh plugin backup, the existing address was retained as unverified/non-primary and the migration's verified fallback was added (ADR-0033). PR #70 then deployed 2.7.1 successfully; migration 0243 is recorded, the database is healthy, the login page returns HTTP 200, and a raw database query found 10 recipes (IDs 1–10), matching the recorded import count. The post-apply Pulumi preview reports 18 unchanged. Details are in the update log.

**Import used for the 2026-10-18 cutover:** the 18:16 UTC rehearsal dump (taken before the legacy service was stopped) was restored; media copied and checksum-verified. Counts: 10 recipes (4 with images, all four files present), 3 users (`uli`, `viktoria`, superuser `alten`), 74 foods, 1 space `Default`, 100 tables all owned by `tandoor`, last migration `0242`; the `migrate` init container reported "No migrations to apply". The post-import backup completed (`20261018T170549`). No fresh post-shutdown dump was imported; the user confirmed all recipes and images are present.

**Cutover done by the user on 2026-10-18:** the legacy containers are stopped and the service disabled on `dockerhost`, and the Cloudflare A record `tandoor.4jp.de` now points at `10.10.88.1`. The user confirmed that the login works and that all recipes and images are present. The data is the rehearsal import of 18:16 UTC. The initial 2.7.1 attempt failed and was rolled back; the upgrade later succeeded after account remediation (see the 2026-10-24 update log and ADR-0033). Dashboards `Tandoor` and `Docker containers` exist ([Observability stack](./observability-stack.md)). **DNS (2026-10-19, ADR-0029):** the record is kept in Cloudflare and is now managed by the `tandoor` stack (`utils.cloudflare.create_a_record`, token `op://Homelab/Cloudflare [4jp.de]/password`); it was imported once with `import_` and the next preview showed no changes. Alerts: `tandoor-down` and `tandoor-server-errors`; backups are covered by `cnpg-backup-stale` and `longhorn-volume-backup-stale`. Open: the legacy clean-up in stage 2 with approval.

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
3. Dump on `dockerhost`: `sudo docker exec tandoor_db_recipes_1 sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > ~/tandoor.dump`, and pack the media: `sudo tar -C /opt/tandoor/mediafiles -cf ~/tandoor-media.tar .`. The files are root-owned, so `chown` them before `scp`. Copy both to the workstation (together about 1.5 MB) and keep them outside the repository (untracked files in it can block commits).
4. Restore the database. **`pg_restore --clean --if-exists` does not work** on the schema that the init container already created (`cannot drop constraint cookbook_recipe_pkey ... other objects depend on it`; with `--single-transaction` it rolls back and changes nothing). Instead recreate the empty database and restore without `--clean`: `psql -c 'DROP DATABASE tandoor' -c 'CREATE DATABASE tandoor OWNER tandoor'` and `pg_restore --no-owner --role=tandoor --single-transaction --exit-on-error -d tandoor < tandoor.dump`, both with `kubectl -n tandoor exec -i tandoor-db-1 -c postgres --`. The dump creates the extensions `pg_trgm` and `unaccent` itself. Check that the database was empty and has no connections first.
5. Restore the media: apply a short Pod `media-import` (`busybox`, `sleep 600`) that mounts the PVC `mediafiles` at `/data`, stream the tar in with `kubectl exec -i media-import -- tar -xf - -C /data < tandoor-media.tar`, compare `sha256sum` of the files with those in the tar, delete the Pod. The application runs as root, so no `chown` is needed (the volume has `fsGroup` 65534).
6. Scale the application back to one replica. The `migrate` init container brings the schema to the pinned version. Test with `curl --resolve tandoor.4jp.de:443:10.10.88.1 https://tandoor.4jp.de/` and by signing in (a browser needs a hosts entry for the test).
7. Confirm the protection before the legacy instance is stopped: an on-demand CloudNativePG backup of `tandoor-db` is `completed` after the import (it takes about 2 minutes), and a Longhorn backup of `mediafiles` exists after the 02:00 UTC run. Keep the dump and tar files until then.
8. **Cutover:** point the name at Traefik's address (an A record in Cloudflare, managed by the stack, ADR-0029) and check `dig tandoor.4jp.de` from a LAN client. Stop the legacy containers (do not delete them) and keep them for the agreed period.
9. Stage 2 (done 2026-10-28, approved by the user): removed the legacy role, `/opt/tandoor` and the Traefik labels on `dockerhost` (the Cloudflare record stays; it is the live one now).

# Runbook: re-mint the metrics session (ADR-0035)

Do this at least yearly (the session expires 2027-10-25), or whenever `tandoor-down` fires with Alloy logging HTTP 302 for job `tandoor`. The user runs it, so the key never enters an agent transcript; the admin `alten` cannot add users (staff without that permission), so `manage.py shell` is the way. The container has a 1 Gi limit and was OOMKilled once by `manage.py check`; the pod restarts by itself if killed, check that it is 1/1 Ready afterwards.

1. If the user `tandoor-metrics` is missing, create it: non-staff, non-superuser, no groups, no space, `set_unusable_password()`. Never give it a space or staff rights.
2. Save this as `/tmp/mint-session.py`, then run the pipe from the repo root; the key lands in the clipboard and is never printed:

   ```python
   from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
   from django.contrib.auth.models import User
   from django.contrib.sessions.backends.db import SessionStore

   u = User.objects.get(username="tandoor-metrics")
   s = SessionStore()
   s[SESSION_KEY] = str(u.pk)
   s[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
   s[HASH_SESSION_KEY] = u.get_session_auth_hash()
   s.create()
   print("SESSIONKEY=" + s.session_key)
   ```

   ```bash
   direnv exec . kubectl -n tandoor exec -i deploy/tandoor -c tandoor -- sh -c "cd /opt/recipes && . venv/bin/activate && python manage.py shell" < /tmp/mint-session.py | grep SESSIONKEY= | cut -d= -f2 | pbcopy
   ```

3. Paste it as the password of the 1Password Login `Homelab/Tandoor Metrics Scrape` (username `tandoor-metrics`), update the expiry date in its notes. The service account is read-only, so edit it in the 1Password app.
4. Prove it with a port-forward (`svc/tandoor` 18080:80): `curl -H "Host: tandoor.tandoor.svc" -H "Cookie: sessionid=$(op read "op://Homelab/Tandoor Metrics Scrape/password")" http://127.0.0.1:18080/metrics` must return 200; without the cookie it returns 302.
5. `pulumi up` in `services/observability` (preview first): the value is resolved at deploy time, so the `alloy-targets` Secret must be refreshed. Check `up{job="tandoor"} == 1` in Mimir.
6. Never change the password of `tandoor-metrics` and never log that session out; either invalidates it.

# Open points

- **Metrics** (ADR-0028, ADR-0034, ADR-0035): `ENABLE_METRICS=1`; the IngressRoute does not route `/metrics`. Since 2.7.1, `ScopeMiddleware` redirects every unauthenticated non-`/api/` path to login, so a scrape needs a Django session. Alloy scrapes `tandoor.tandoor.svc:80/metrics` (job `tandoor`, `services/observability/assets/alloy/config.alloy`) with the `sessionid` cookie of the space-less, non-staff user `tandoor-metrics`, `follow_redirects = false`. The key is the password of 1Password `Homelab/Tandoor Metrics Scrape`; Pulumi puts `sessionid=<key>` into the `alloy-targets` Secret (`tandoor-cookie`). Verified 2026-10-25: `up{job="tandoor"} == 1`, 697 series (261 before 2.7.1), `tandoor-down`, `Scrape target down` and `tandoor-server-errors` inactive. `tandoor-down` is also the expiry signal (365 days, a password change or a logout invalidates the session). Monitor upstream issue TandoorRecipes/recipes#4888; when `/metrics` is exempted, remove the cookie, the `tandoor-session` config field and the user.
- PDF export (`ENABLE_PDF_EXPORT=1`) may need more than the 1 Gi memory limit; check the first export and raise the limit if the pod is killed.
- A post-upgrade `manage.py check` diagnostic exited 137; the app container recorded one `OOMKilled` restart. It returned to 1/1 Ready and `/accounts/login/` returned HTTP 200 afterwards. No resource settings were changed; monitor memory before running further diagnostics inside this container.
- A restore of `tandoor-db` from its QNAP backup has not been rehearsed for this cluster; the method is the verified one of ADR-0017 and ADR-0018.

Related: ADR-0028, ADR-0034, ADR-0035, ADR-0018, ADR-0023, [dockerhost-services](./dockerhost-services.md), [Paperless](./paperless.md), [Retiring the legacy dockerhost monitoring stack](./legacy-monitoring-migration.md).
