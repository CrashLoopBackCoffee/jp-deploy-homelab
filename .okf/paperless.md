---
type: Service
title: Paperless (Pulumi, prepared, not deployed)
description: Fresh-install Paperless-ngx on k0s with a dedicated CloudNativePG database, restic to an off-site Nextcloud, QNAP NFS intake, the prerequisites, and the go-live gate runbook.
timestamp: 2026-10-15T00:00:00Z
tags: [homelab, kubernetes, paperless, cloudnativepg, backup, restic, nextcloud]
resource: https://app.pulumi.com/jaypee-solutions/paperless/prod
---

# State

Deployed on 2026-10-15 from branch `feature/paperless-prep` (29 resources, stack `jaypee-solutions/paperless/prod`) at `https://paperless.4jp.de`, then **upgraded the same evening to Paperless 3.3.1** (ADR-0021; the stack previews clean). The go-live gate (ADR-0020) passed on 2.18.4: the `paperless-db` cluster is healthy and backed up, the backup job created the restic repository on the Nextcloud and `restic check` is clean, and a test document survived upload, backup, deletion including the trash, restore from the off-site repository and import with an identical SHA-256. After the v3 upgrade the backup, the consumer and form login were re-verified and the restore was re-proven as a disaster-recovery import into a throwaway v3 instance (see below). Paperless holds one real document (see After go-live). Single sign-on through the shared Authentik at `https://id.jaypee.solutions` is decided (ADR-0021) but not yet applied. The restore procedure had three bugs in the donor's version (separate `/tmp`, absolute restic paths, directory ownership), all fixed. The workspace `services/paperless` was the donor's stack; this session replaced everything donor-specific.

What is running in namespace `paperless`: a StatefulSet `paperless` (Paperless-ngx plus a `restic` sidecar, three Longhorn volumes `data`, `media`, `export`, the QNAP NFS share as `consume` (mounted, 17 TB, 7.0 TB free), a shared scratch `restore` emptyDir), Redis, Tika and Gotenberg, a dedicated CloudNativePG cluster `paperless-db` (one instance on `openebs-lvm-postgres`, Barman plugin backups to prefix `paperless-db/` in `cnpg-backups`), a nightly 02:00 backup CronJob, an IngressRoute for `https://paperless.4jp.de` and the dnsmasq record. Local accounts only; the `admin` password is generated and exported as a Pulumi secret (also in the Secret `paperless-config-<hash>`; Pulumi appends a suffix to generated Secret names).

# What changed from the donor

- Bitnami PostgreSQL and the `pulumi_postgresql` role and database are replaced by `utils.cnpg.create_cnpg_database`, a shared helper that builds the Cluster, ObjectStore (with the QuObjects checksum workaround), credentials Secret and ScheduledBackup. The Cluster carries `pulumi.com/waitFor: condition=Ready` so Paperless starts after the database. Paperless reads the CloudNativePG-generated `paperless-db-app` Secret for its password. The pilot in the kubernetes stack still has its own copy of this code; consolidating it is optional.
- Entra ID, Google OAuth, Gmail, allauth apps, the OIDC group, the Cloudflare key and the Google Drive and IDrive backups are removed.
- The restic sidecar uses `rclone:nextcloud:paperless` over WebDAV. rclone only accepts an obscured password, so an init container writes `rclone.conf` with `rclone obscure` at pod start from the Secret `paperless-backup-secrets` (`NEXTCLOUD_URL` is the base URL, the WebDAV path is derived). Checked by running the generated shell with a stub: URL, user, special characters in the password and mode 0600 are right.
- The backup job now also runs `restic check` each night, so a damaged off-site repository fails the job.
- The donor's restore script had three bugs that would have broken a real restore. Two were fixed up front: the restic sidecar and the Paperless container have separate `/tmp`, so a shared emptyDir `/restore` was added; and `restic restore` recreates the absolute snapshot path, so it now restores `SNAPSHOT:/usr/src/paperless/export`. The third only showed in the live test: the restored directory is `0700 root`, unreadable for the importer (uid 1000), so a `chown -R 1000:1000` step was added. All three are now exercised and work.

# Prerequisites (user, outside Pulumi)

1. 1Password item `Nextcloud Paperless Backup` in `Homelab`: the website (read as `url`) is the Nextcloud base URL, `username` the account, and a custom field `app-password` an app password (Nextcloud Settings, Security). The item's own `password` is the account password, which Nextcloud rejects over WebDAV (`401 PasswordLoginForbidden`, because 2FA is on). The Pulumi resolver treats only `password`, `username`, `title`, `url` and `notes` as standard fields; every other label is looked up as a custom field, so `website` would fail.
2. 1Password item `Paperless Backup` in `Homelab`: `password` is the restic repository password. Keep a copy outside the cluster: losing it makes the off-site copy unreadable.
3. A share on the QNAP, `/paperless-consume`, exported over NFS to `k0s0` (`10.10.8.1`), writable by uid 1000 (Paperless deletes consumed files). The server name `qnap.4jp.de` resolves to `10.10.0.10` through the Unbound override. Verified 2026-10-15 with a throwaway pod using the same CSI driver and options as the StatefulSet: mount, write, read, delete, mkdir and rmdir as uid 1000 all succeed, and the volume is 17.0 TB with 6.9 TB free. The NAS squashes all users to `nobody` (files created from Kubernetes show uid 65534) and the share is `drwxrwxrwx`, so Paperless can read, write and delete regardless of the file owner. Before the share worked the mount failed with `mount.nfs: access denied by server`; the QNAP NFS host access list for the share must include `10.10.8.1` with read/write.

Then: `(cd services/paperless && direnv exec ../.. pulumi stack init jaypee-solutions/prod)`, preview, review, apply.

# Go-live gate (ADR-0020)

Paperless may go live before the HBS 3 test passes if all of this passes first, with only a test document in the instance:

1. `kubectl -n paperless get cluster.postgresql.cnpg.io paperless-db` is healthy, and `kubectl -n paperless get backup.postgresql.cnpg.io` shows the first backup `completed`.
2. Sign in at `https://paperless.4jp.de` as `admin`, or use the REST API. Pulumi generates the Secret names with a suffix (`paperless-config-<hash>`), so look it up: `SECRET=$(kubectl -n paperless get secret -o name | grep '^secret/paperless-config')` and `kubectl -n paperless get "$SECRET" -o jsonpath='{.data.PAPERLESS_ADMIN_PASSWORD}' | base64 -d`. Upload a test document (UI, or `POST /api/documents/post_document/` with a token from `POST /api/token/`).
3. Run the backup now: `kubectl -n paperless create job --from=cronjob/paperless-backup paperless-backup-manual` and read its log. It must end with `Backup process completed successfully.`, which includes `restic check`. `restic ls latest` should list the document's original and manifest.
4. Delete the test document in Paperless and empty the trash (`POST /api/trash/` with `{"action":"empty"}`); the count must be 0.
5. Restore it from the **latest snapshot, before any further backup** (the next export run deletes the document from the export directory). These are the steps of the unwired restore Job in `restore.py`:

```sh
kubectl -n paperless exec paperless-0 -c restic -- restic restore latest:/usr/src/paperless/export --target /restore/paperless-restore
kubectl -n paperless exec paperless-0 -c restic -- chown -R 1000:1000 /restore/paperless-restore
kubectl -n paperless exec paperless-0 -c paperless -- document_importer /restore/paperless-restore --no-progress-bar
kubectl -n paperless exec paperless-0 -c paperless -- rm -rf /restore/paperless-restore
```

   The `chown` is required: the importer wrapper runs as uid 1000, but restic (root) restores the target directory as `drwx------ root`, which gave `CommandError: That path doesn't appear to be readable`.
6. The test document is back with an identical SHA-256. Archives and thumbnails are not exported, so they regenerate: `document_thumbnails`, `document_archiver`, `document_index reindex`.

**Passed on 2026-10-15** (see State). Clean up afterwards: delete the test document, empty the trash, delete the API token (`manage.py shell`, `Token.objects.all().delete()`; `DELETE /api/token/` is not supported) and the manual backup jobs.

# After go-live

- Paperless now holds real data: a scanned document arrived through the QNAP intake on the evening of 2026-10-15 (document id 2). The live delete-and-restore gate above was only safe while the instance was empty; with real documents use the scratch-instance test below instead.
- The Grafana alert `paperless-backup-stale` (kube-state-metrics `kube_cronjob_status_last_successful_time` older than 36 hours, or missing) exists since 2026-10-17 (PR #22). `cnpg-backup-stale` already covers `paperless-db`. The media volume was also restored from a scheduled Longhorn backup on 2026-10-17 with an identical checksum.
- The three application volumes join Longhorn's nightly backup group in addition to the restic copy.
- Volumes can be expanded in the stack config (needs a pod restart); `export` needs about the size of `media`.
- The startup log shows `chown ... Operation not permitted` for the NFS consume folder (the NAS squashes users); harmless.
- The 2026-10-15 upgrade was staged 2.18.4, 2.20.15, 3.3.1 (the v3 migration guide allows v3 only from 2.20.15) after a restic snapshot and a database backup (`paperless-db-pre-v3`). Roll back by restoring the database backup and the previous image, not by downgrading in place.

# Paperless 3.x settings

Taken from the migration guide and checked against TH's working deployment: `PAPERLESS_CONSUMER_POLLING_INTERVAL` (renamed from `CONSUMER_POLLING`; NFS has no change notifications), `PAPERLESS_CONSUMER_STABILITY_DELAY` (replaces `POLLING_DELAY` and `POLLING_RETRY_COUNT`), `PAPERLESS_CONSUMER_IGNORE_PATTERNS` (now regular expressions against file names only, added to the defaults), `PAPERLESS_CONSUMER_IGNORE_DIRS` (new, directory names) and `PAPERLESS_DBENGINE` (required). `PAPERLESS_CONSUMER_BARCODE_SCANNER` is gone and `PAPERLESS_SECRET_KEY` is required (already generated by Pulumi). The QNAP share contains `@Recycle` and `@Recently-Snapshot`, which the recursive consumer would otherwise pick up (files deleted by Paperless would be consumed again), so they are in `IGNORE_DIRS`. Verified live: a file in the intake root was consumed, a file in `@Recycle` was ignored. Form login through Traefik works; v3's possible `403` from login rate limiting behind a reverse proxy did not occur, so `PAPERLESS_TRUSTED_PROXIES` is not set. If OIDC later fails with `invalid_client`, add `token_auth_method` to the provider settings (migration guide).

# Single sign-on (Authentik)

Code in `paperless.py` and `OidcConfig` (stack config `paperless:oidc`); decision in ADR-0021. Client id and secret come from the 1Password item `Paperless OIDC` (`username`, `password`) into the config Secret as `PAPERLESS_SOCIALACCOUNT_PROVIDERS` (allauth `openid_connect`, provider id `authentik`, `server_url` the Authentik issuer without `.well-known`). Plain settings: `PAPERLESS_APPS`, `PAPERLESS_SOCIAL_AUTO_SIGNUP`, `PAPERLESS_SOCIAL_ACCOUNT_SYNC_GROUPS` and `PAPERLESS_SOCIAL_ACCOUNT_SYNC_SUPERUSER_GROUP=paperless-admins`. Local login stays (neither `DISABLE_REGULAR_LOGIN` nor `REDIRECT_LOGIN_TO_SSO` is set).

Read from the 3.3.1 source (`src/paperless/signals.py`), not the docs: at every SSO login the user's groups are **replaced** (`groups.set(..., clear=True)`) by the Paperless groups whose names appear in the `groups` claim, so only groups that already exist in Paperless can be joined; the group `paperless` must be created in Paperless (Settings, Users & Groups) before the first login, and its permissions are set there. `paperless-admins` need not exist in Paperless: membership only toggles `is_superuser` (and `is_staff`). A user who is in neither Authentik group is stopped by the application bindings in Authentik before reaching Paperless.

Check before applying: `https://id.jaypee.solutions/application/o/paperless/.well-known/openid-configuration` must return 200. A 404 behaves like a nonexistent slug: the application slug differs from `paperless`, or the OAuth2 provider is not assigned to the application (compare the known-good `tuweka`). The sign-in itself needs Paperless restarted, which the apply does (the config Secret is replaced).

# Disaster-recovery test on a scratch instance

Use this instead of delete-and-restore once real documents exist. It proves that the off-site backup restores into a clean instance without touching live data. Run on 2026-10-15 for Paperless 3.3.1: the real document came back with an identical checksum.

1. Run the backup (`kubectl -n paperless create job --from=cronjob/paperless-backup NAME`), then restore the latest snapshot into the live pod's scratch volume: `kubectl -n paperless exec paperless-0 -c restic -- restic restore latest:/usr/src/paperless/export --target /restore/dr-test` and `chown -R 1000:1000` it.
2. Start a throwaway pod `paperless-scratch` in the namespace with two containers: `redis` and `paperless` (same version as live, `PAPERLESS_REDIS=redis://localhost:6379`, a throwaway `PAPERLESS_SECRET_KEY`, SQLite). It must have its **own** Redis (a shared one would let the scratch worker steal live tasks) and must not mount the NFS share or the live volumes.
3. Stream the restore into it: `kubectl exec paperless-0 -c paperless -- tar -C /restore/dr-test -cf - . | kubectl exec -i paperless-scratch -c paperless -- tar -C /tmp/dr-restore -xf -`, `chown -R 1000:1000 /tmp/dr-restore` there, then `document_importer /tmp/dr-restore --no-progress-bar`.
4. Compare documents, titles and checksums with the live instance, then delete the pod, `/restore/dr-test` and the manual jobs.

Related: [Observability stack](./observability-stack.md), [PostgreSQL pilot recovery](./postgres-pilot-recovery.md), ADR-0020.
