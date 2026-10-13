---
type: Runbook
title: PostgreSQL pilot recovery from QuObjects
description: CloudNativePG pilot backup settings, live recovery evidence, and safe follow-up operations.
timestamp: 2026-10-12T00:00:00Z
tags: [homelab, kubernetes, postgresql, cloudnativepg, backup, recovery]
resource: https://app.pulumi.com/jaypee-solutions/kubernetes/prod
---

# Pilot state

`postgres-pilot` is a single PostgreSQL 17.10 instance in namespace `postgres-pilot`, with a 2 GiB PVC on `openebs-lvm-postgres`. Pulumi owns the Cluster, Barman plugin, ObjectStore, backup Secret, and ScheduledBackup. The ObjectStore writes to `s3://cnpg-backups/postgres-pilot/` at `https://qnap.4jp.de:8443` using the `QuObjects CNPG Backup` item in the Homelab 1Password vault. It archives gzip-compressed WAL, schedules daily backups at `0 0 3 * * *`, and retains a 14-day recovery window. The first immediate backup failed; `postgres-pilot-backup-recovered` later completed with backup ID `20261012T183618`.

# Verified recovery (2026-10-12)

- QuObjects returned `InvalidDigest` for both `PutObject` WAL and base-backup uploads. Barman's documented S3-compatibility settings `AWS_REQUEST_CHECKSUM_CALCULATION=when_required` and `AWS_RESPONSE_CHECKSUM_VALIDATION=when_required` are set on the `ObjectStore` instance sidecar; TLS verification remains enabled. An `ObjectStore` update alone does **not** update an existing Pod's environment. After the previewed Pulumi update, a CNPG-managed `kubectl cnpg restart postgres-pilot -n postgres-pilot` replaced the pilot Pod and WAL archiving recovered. Do not delete the Pod directly just to refresh plugin settings.
- The completed Barman base backup contains `public.recovery_probe` row 1 (`qnap-cnpg-restore-20261012`). Row 2 (`qnap-cnpg-wal-restore-20261012`) was inserted **after** the backup; a WAL switch archived the segment containing it. The independent Cluster `postgres-pilot-restore-20261012` recovered the most recent backup plus WAL from the source ObjectStore and returned **both** rows. Its 2 GiB PVC was Bound on `openebs-lvm-postgres` during the test; the source Cluster and PVC remained unchanged.
- This proves latest-state base-backup + WAL recovery, not recovery to a specified point in time, retention after 14 days, or an encrypted off-site HBS copy. After explicit user approval and a server-side delete dry run, the temporary restore Cluster was deleted; its owned PVC and PV were reclaimed. The failed initial Backup CR is historical evidence, not a successful backup.

# Scheduled backup evidence (2026-10-13)

`postgres-pilot-backup-20261013030000` (ID `20261013T030000`) ran from the `ScheduledBackup` at 03:00 UTC and completed in about 4 s; the plugin log shows `barman-cloud-backup` start/complete, and the ObjectStore status reports `lastSuccessfulBackupTime` `2026-10-13T03:00:00Z` and `firstRecoverabilityPoint` `2026-10-12T18:36:24Z`. `pg_stat_archiver` shows continuous WAL archiving (last segment `...0A` at 03:05; the 21 failures are the pre-fix `InvalidDigest` period). The backup status records `startedAt`/`stoppedAt` to the second only, so use the plugin log for duration. The 14-day retention task runs every 30 minutes but nothing is old enough to prune yet.

Longhorn's `longhorn-daily-backup` RecurringJob (`0 2 * * *`, 14 retained) exists and the target is Available, but there are **no Longhorn volumes**, so the scheduled job has produced no backup; it is unverified until a real volume joins the `default` group.

# Verified time-targeted PITR (2026-10-13)

Rows 3 and 4 were written, then `T = 2026-10-13 17:47:43.010934+00` was read from `clock_timestamp()`, then row 5, then `pg_switch_wal()` and a confirmed archive of segment `…0D`. Cluster `postgres-pilot-pitr-20261013` with `bootstrap.recovery.recoveryTarget.targetTime: "<T>"` (source `externalClusters` plugin entry, no archiver plugin of its own) became Ready in about 50 s and held rows 1–4 and **not** row 5. A target later than the last archived WAL cannot be reached, so always switch and confirm archival before restoring. The PITR restore reuses the Operations manifest below with `recoveryTarget` added. Pass `-i` to `kubectl exec` when feeding psql via a heredoc; without it stdin is dropped and nothing runs, silently.

# Next verification

The encrypted off-site HBS restore (ADR-0018) is deferred by the user and unverified.

# Operations

Enter the repository through direnv (warn before commands that may request biometric approval). Use the explicit API group because Longhorn also defines a `Backup` kind:

```sh
kubectl -n postgres-pilot get backup.postgresql.cnpg.io,scheduledbackup.postgresql.cnpg.io,cluster.postgresql.cnpg.io
kubectl -n postgres-pilot get pvc
kubectl -n postgres-pilot exec postgres-pilot-1 -c postgres -- psql -U postgres -d postgres -Atc 'SELECT archived_count, last_archived_wal, failed_count FROM pg_stat_archiver'
```

For a new on-demand plugin backup, preview its manifest before creating it:

```sh
kubectl cnpg backup -n postgres-pilot postgres-pilot --method=plugin --plugin-name=barman-cloud.cloudnative-pg.io --backup-name=CHOSEN_NAME --dry-run
kubectl cnpg backup -n postgres-pilot postgres-pilot --method=plugin --plugin-name=barman-cloud.cloudnative-pg.io --backup-name=CHOSEN_NAME
kubectl -n postgres-pilot wait backup.postgresql.cnpg.io/CHOSEN_NAME --for=jsonpath='{.status.phase}'=completed --timeout=300s
```

A successful `Backup` CR alone is not a restore test. To restore independently, create a new `Cluster` with a different name and PVC, `bootstrap.recovery.source` naming an `externalClusters` entry whose `plugin` uses `barman-cloud.cloudnative-pg.io`, `barmanObjectName: postgres-pilot-store`, and `serverName: postgres-pilot`. Do not enable WAL archiving to the source prefix from the restored Cluster. Preview with `kubectl diff --server-side -f MANIFEST` before `kubectl apply -f MANIFEST`; check actual recovered rows before considering cleanup. See ADR-0017 and the [Barman plugin recovery example](https://cloudnative-pg.io/plugin-barman-cloud/docs/usage/).
