---
type: Service
title: Paperless (Pulumi, prepared, not deployed)
description: Fresh-install Paperless-ngx on k0s with a dedicated CloudNativePG database, restic to an off-site Nextcloud, QNAP NFS intake, the prerequisites, and the go-live gate runbook.
timestamp: 2026-10-15T00:00:00Z
tags: [homelab, kubernetes, paperless, cloudnativepg, backup, restic, nextcloud]
resource: https://app.pulumi.com/jaypee-solutions/paperless/prod
---

# State

Prepared on 2026-10-15, **not applied**. The empty stack `jaypee-solutions/paperless/prod` exists and its preview shows 29 resources to create. Verified so far: both 1Password items resolve in the preview; the Nextcloud app password logs in and survived a WebDAV create, upload, download and delete cycle (quota unlimited); the QNAP NFS share mounts from `k0s0` and accepts write, read, delete, mkdir and rmdir as uid 1000. All prerequisites are met, so the next step is the apply (needs user approval) and then the go-live gate. Decisions and the gate are in ADR-0020. The workspace `services/paperless` was the donor's stack; this session replaced everything donor-specific.

What it will deploy into namespace `paperless`: a StatefulSet `paperless` (Paperless-ngx plus a `restic` sidecar, three Longhorn volumes `data`, `media`, `export`, the QNAP NFS share as `consume`, a shared scratch `restore` emptyDir), Redis, Tika and Gotenberg, a dedicated CloudNativePG cluster `paperless-db` (one instance on `openebs-lvm-postgres`, Barman plugin backups to prefix `paperless-db/` in `cnpg-backups`), a nightly backup CronJob, an IngressRoute for `https://paperless.4jp.de` and the dnsmasq record. Local accounts only; the `admin` password is generated and exported as a Pulumi secret (also in the Secret `paperless-config`).

# What changed from the donor

- Bitnami PostgreSQL and the `pulumi_postgresql` role and database are replaced by `utils.cnpg.create_cnpg_database`, a shared helper that builds the Cluster, ObjectStore (with the QuObjects checksum workaround), credentials Secret and ScheduledBackup. The Cluster carries `pulumi.com/waitFor: condition=Ready` so Paperless starts after the database. Paperless reads the CloudNativePG-generated `paperless-db-app` Secret for its password. The pilot in the kubernetes stack still has its own copy of this code; consolidating it is optional.
- Entra ID, Google OAuth, Gmail, allauth apps, the OIDC group, the Cloudflare key and the Google Drive and IDrive backups are removed.
- The restic sidecar uses `rclone:nextcloud:paperless` over WebDAV. rclone only accepts an obscured password, so an init container writes `rclone.conf` with `rclone obscure` at pod start from the Secret `paperless-backup-secrets` (`NEXTCLOUD_URL` is the base URL, the WebDAV path is derived). Checked by running the generated shell with a stub: URL, user, special characters in the password and mode 0600 are right.
- The backup job now also runs `restic check` each night, so a damaged off-site repository fails the job.
- The donor's restore script had two bugs that would have broken a real restore, both fixed in `restore.py` but not yet exercised on a live system: the restic sidecar and the Paperless container have separate `/tmp`, so a shared emptyDir `/restore` was added; and `restic restore` recreates the absolute snapshot path, so it now restores `SNAPSHOT:/usr/src/paperless/export`.

# Prerequisites (user, outside Pulumi)

1. 1Password item `Nextcloud Paperless Backup` in `Homelab`: the website (read as `url`) is the Nextcloud base URL, `username` the account, and a custom field `app-password` an app password (Nextcloud Settings, Security). The item's own `password` is the account password, which Nextcloud rejects over WebDAV (`401 PasswordLoginForbidden`, because 2FA is on). The Pulumi resolver treats only `password`, `username`, `title`, `url` and `notes` as standard fields; every other label is looked up as a custom field, so `website` would fail.
2. 1Password item `Paperless Backup` in `Homelab`: `password` is the restic repository password. Keep a copy outside the cluster: losing it makes the off-site copy unreadable.
3. A share on the QNAP, `/paperless-consume`, exported over NFS to `k0s0` (`10.10.8.1`), writable by uid 1000 (Paperless deletes consumed files). The server name `qnap.4jp.de` resolves to `10.10.0.10` through the Unbound override. Verified 2026-10-15 with a throwaway pod using the same CSI driver and options as the StatefulSet: mount, write, read, delete, mkdir and rmdir as uid 1000 all succeed, and the volume is 17.0 TB with 6.9 TB free. The NAS squashes all users to `nobody` (files created from Kubernetes show uid 65534) and the share is `drwxrwxrwx`, so Paperless can read, write and delete regardless of the file owner. Before the share worked the mount failed with `mount.nfs: access denied by server`; the QNAP NFS host access list for the share must include `10.10.8.1` with read/write.

Then: `(cd services/paperless && direnv exec ../.. pulumi stack init jaypee-solutions/prod)`, preview, review, apply.

# Go-live gate (ADR-0020)

Paperless may go live before the HBS 3 test passes if all of this passes first, with only a test document in the instance:

1. `kubectl -n paperless get cluster.postgresql.cnpg.io paperless-db` is healthy, and `kubectl -n paperless get backup.postgresql.cnpg.io` shows the first backup `completed`.
2. Sign in at `https://paperless.4jp.de` as `admin` (`kubectl -n paperless get secret paperless-config -o jsonpath='{.data.PAPERLESS_ADMIN_PASSWORD}' | base64 -d`), upload a test document.
3. Run the backup now: `kubectl -n paperless create job --from=cronjob/paperless-backup paperless-backup-manual` and read its log. It must end with `Backup process completed successfully.`, which includes `restic check`.
4. Delete the test document in Paperless (also empty the trash).
5. Restore it (the same steps as the unwired restore Job in `restore.py`):

```sh
kubectl -n paperless exec paperless-0 -c restic -- restic restore latest:/usr/src/paperless/export --target /restore/paperless-restore
kubectl -n paperless exec paperless-0 -c paperless -- document_importer /restore/paperless-restore --no-progress-bar
kubectl -n paperless exec paperless-0 -c paperless -- rm -rf /restore/paperless-restore
```

6. The test document is back, and opens. Archives and thumbnails are not exported, so they regenerate: `document_thumbnails`, `document_archiver`, `document_index reindex`.

# After go-live

- Add a Grafana alert for the `paperless-backup` CronJob not succeeding for 36 hours (kube-state-metrics `kube_cronjob_status_last_successful_time`); it was left out because it would fire while Paperless is not deployed. `cnpg-backup-stale` already covers `paperless-db`.
- The three application volumes join Longhorn's nightly backup group in addition to the restic copy.
- Volumes can be expanded in the stack config (needs a pod restart); `export` needs about the size of `media`.

Related: [Observability stack](./observability-stack.md), [PostgreSQL pilot recovery](./postgres-pilot-recovery.md), ADR-0020.
