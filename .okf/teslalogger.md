---
type: Service
title: TeslaLogger (Pulumi, applied; cut over 2026-10-28)
description: TeslaLogger migration from dockerhost to k0s with a mariadb-operator database, what the stack creates, image and app facts that shaped the design, the import and cutover runbook, and rehearsal evidence (ADR-0039, ADR-0040).
timestamp: 2026-10-28T19:00:00Z
tags: [homelab, kubernetes, teslalogger, mariadb, mariadb-operator, longhorn, migration]
resource: https://app.pulumi.com/jaypee-solutions/teslalogger/prod
---

# State

Stack `jaypee-solutions/teslalogger/prod` (source `services/teslalogger`, branch `feature/teslalogger`), 25 resources, cut over on 2026-10-28. Final run: the legacy logger was stopped with the car parked, a fresh dump (identical counts to the rehearsal: nothing was logged in between) and the state files were imported, the `replicas` gate was removed and TeslaLogger runs on k0s. `systemctl disable --now tesla-logger` was run on `dockerhost` (the unit shows `failed` because the stopped logger exited with 137; containers are stopped, not deleted). Both Cloudflare A records (`tesla-logger.4jp.de`, `grafana.tesla-logger.4jp.de`) now point at `10.10.88.1` and are managed by the stack (imported with `import_`, then removed). The `observability` stack carries `teslalogger-down` and `mariadb-backup-stale`. **Pending:** Longhorn backups after 02:00 UTC, the first scheduled dump at 21:00 UTC, a `DAY-mysqldump*.gz` within a day, a newer `max(Datum)` after the car drives, stage-2 removal on `dockerhost` (needs approval).

# What the stack creates

Namespace `teslalogger`; MariaDB `database` (10.11.19, operator CR, Longhorn volume 5 Gi, `Europe/Berlin`, `utf8mb4_unicode_ci`, root password the literal `teslalogger`); `Database` `teslalogger`; `Backup` `database-mariadb-backup` (daily 21:00 UTC to `mariadb-backups/teslalogger-db/`, only the `teslalogger` schema); NetworkPolicy `database-access`; Secret `grafana-admin` (generated); PVC `teslalogger` (5 Gi, subPaths `tmp`, `data`, `backup`, `invoices`, `grafana`); Deployment `teslalogger` (`Recreate`; init container `prepare`; containers `teslalogger`, `webserver`, `grafana`); Services `teslalogger:5000`, `grafana:3000`, `webserver:80`; Certificate `grafana-certificate` (Let's Encrypt, DNS-01); IngressRoutes `webserver` (wildcard certificate) and `grafana`.

Grafana admin password: `kubectl -n teslalogger get secret grafana-admin -o jsonpath='{.data.password}' | base64 -d`.

# Facts that shaped the design

- The app, PHP panel and Grafana datasource hardcode host `database`, user `root`, password `teslalogger`, database `teslalogger`, and call `http://teslalogger:5000` and `http://grafana:3000`. Names and password are therefore fixed.
- Docker mode comes from `/tmp/teslalogger-DOCKER` and `/tmp/teslalogger-dockernet8`, written into the image's own `/tmp`; a volume on `/tmp` hides them, so the init container recreates them.
- On every start teslalogger copies the Grafana plugins and regenerates dashboards into `/var/lib/grafana`; Grafana loads plugins only at startup, so the init container copies the plugins first.
- The HTTP listener on 5000 opens only after DB connect and schema update: never start it on an empty database (hence `replicas`).
- Expected log noise: `Error getting Docker container image`, `Watchtower update error` (no `docker.sock`, no Watchtower).
- Grafana 13.2.4 in the upstream image refuses the Angular plugin `natel-discrete-panel`; `pr0ps-trackmap-panel` and `teslalogger-timeline-panel` load.
- The mariadb-operator's retention cannot parse the `%3A` in QuObjects object keys, so old dumps are not deleted (ADR-0039). The first smoke dump (1.1 MB, with the `mysql` schema) could not be deleted either.
- An upstream release newer than the pinned tag makes the in-app updater (`"update":"all"`) restart the process inside the container in a loop (pod restartCount stays 0; 7 restarts on 30–31.10 for 1.63.24.1 vs pinned 1.63.24.0). `Tools.CreateBackupForDocker()` needs 24 h uptime, so the `DAY-mysqldump*.gz` stopped (last 2026-10-29 20:08). Fix: bump `teslalogger.version` to the newest tag.

# Runbook: import and cutover

`ssh -o RemoteCommand=none -o RequestTTY=no dockerhost`; `sudo -n` works. Keep the files in `~/teslalogger-migration` on the workstation, outside the repository.

1. **Final run only:** the user stops the legacy logger, DB left running: `sudo docker stop tesla-logger-teslalogger-1`. Do it while the car is parked.
2. Dump on `dockerhost`: `mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers teslalogger | gzip` through `docker exec tesla-logger-database-1`, the four count queries (`pos`, `charging`, `drivestate`, `max(Datum)` of `pos`) into `counts.txt`, and copy `/opt/tesla-logger/TeslaLogger/bin/{settings.json,encryption.txt,geofence-private.csv}` plus `/var/lib/docker/volumes/tesla-logger_teslalogger-tmp/_data/nosharedata.txt` into `state/data` and `state/tmp`; `chown` to the login user; `scp -r` to the workstation (macOS `tar` adds `._*` files; delete `._nosharedata.txt` in `/tmp` afterwards).
3. Import with the Deployment at 0 replicas: `DROP DATABASE IF EXISTS teslalogger; CREATE DATABASE teslalogger CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci` in `database-0`, then `gunzip -c teslalogger.sql.gz | kubectl -n teslalogger exec -i database-0 -- mariadb -uroot -pteslalogger teslalogger`; compare the counts with `counts.txt`. State files: Pod `state-import` (`busybox:1.37`, PVC `teslalogger` at `/state`), `tar -C state -cf - data tmp | kubectl exec -i state-import -- tar -xf - -C /state`, compare `sha256sum`, delete the Pod. Run a `kubectl create job --from=cronjob/database-mariadb-backup` smoke job so the imported data is in the bucket.
4. Remove `replicas: 0` from `Pulumi.prod.yaml`, preview, `pulumi up`; wait for 3/3 Ready (schema update from 1.63.20.4 at start).
5. The user runs `sudo systemctl disable --now tesla-logger` on `dockerhost` (files and images stay). Rollback until stage 2: `replicas: 0`, `up`, `sudo systemctl enable --now tesla-logger`; drives logged on k0s meanwhile are not in the legacy database, and a token refreshed on k0s may force a new login on the legacy copy.
6. Apply the `observability` stack (alerts `teslalogger-down`, `mariadb-backup-stale`).
7. **DNS (ADR-0029):** the user changes both Cloudflare A records to `10.10.88.1`; read zone and record IDs with the service-account token, add `utils.cloudflare.create_a_record` for `tesla-logger` and `grafana.tesla-logger` with `import_`, preview (two imports, no diff), `up`, remove `import_`, preview shows no changes.
8. Stage 2 on `dockerhost` (role, `/opt/tesla-logger`, Traefik labels) needs the user's approval.

# Final-run evidence (2026-10-28)

Counts equal the fresh dump, state files equal by `sha256sum`, start log `Docker NET8: YES!`, `DB Version: 10.11.19-MariaDB-ubu2204`, `DBSchema Update finished`, `Restore Token OK`, car found; without `--resolve`, `https://tesla-logger.4jp.de/admin/` returns 200 and lists `OAL-FA1E`, Grafana health is `ok`, 42 dashboards; `dig` returns `10.10.88.1` for both names; previews of `teslalogger`, `kubernetes` and `observability` show no changes; Mimir shows 1 available replica and 1 ready StatefulSet replica, and `mariadb-backup-stale` evaluates to 0.

# Rehearsal evidence (2026-10-28, legacy logger running)

- Operator Pods Ready; `database-0` 1/1; `mariadb`, `database`, `backup` Ready; `select version()` `10.11.19-MariaDB-ubu2204`, `@@time_zone` `Europe/Berlin`, collation `utf8mb4_unicode_ci`.
- Dump 7.7 MB gz from 10.4.7; import without errors; counts equal to the legacy ones (175206 `pos`, 251479 `charging`, 6440 `drivestate`, newest `2026-10-28 18:40:25.933`); state files equal by `sha256sum`.
- Smoke backup after the import: 7.85 MB object under `mariadb-backups/teslalogger-db/`. The key reaches only that bucket (`cnpg-backups` returns `NoSuchBucket`).
- NetworkPolicy: a Pod in `default` times out on port 3306.
- Start: `Docker NET8: YES!`, `DB Version: 10.11.19-MariaDB-ubu2204`, `DBSchema Update finished`, `Restore Token OK`, car `Y SR (MIG BYD)`; admin panel HTTP 200 and lists `OAL-FA1E`; Grafana `/api/health` `database: ok` with a valid certificate; 42 dashboards.
- Mimir has series for `kube_cronjob_created`, `kube_cronjob_status_last_successful_time`, `kube_statefulset_status_replicas_ready` and `kube_deployment_status_replicas_available{namespace="teslalogger"}`.

# Still to verify

Verified 2026-10-31: newer `max(Datum)` after the car drove, Longhorn backups of the MariaDB PVC and `teslalogger`, the 21:00 UTC scheduled dump. Still open: a new `DAY-mysqldump*.gz` in `/etc/teslalogger/backup` and `Start backup for Docker` in Loki about 24–25 h after the 1.63.24.1 start (2026-10-31 evening) and no `New Version Detected`; keep `~/teslalogger-migration` and the stopped legacy until then.
