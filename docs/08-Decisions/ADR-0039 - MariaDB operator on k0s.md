---
tags:
  - homelab
  - adr
  - kubernetes
  - mariadb
  - backup
type: adr
status: accepted
date: 2026-10-28
created: 2026-10-28
updated: 2026-10-28
adr: 39
---

# ADR-0039 - MariaDB operator on k0s

## Status

Accepted on 2026-10-28. The operator runs in the `kubernetes` stack; its first user is TeslaLogger ([[ADR-0040 - Migrate TeslaLogger to k0s]]).

## Context

TeslaLogger needs MariaDB. PostgreSQL has a shared helper (`utils.cnpg`) on CloudNativePG; MariaDB had nothing, and a hand-written Deployment would have no declarative backups or health status. The user chose an operator.

## Decision

- **mariadb-operator 26.10.2** in the `kubernetes` stack, cluster-wide, namespace `mariadb-operator`, as two Helm charts (`mariadb-operator-crds`, then `mariadb-operator`) with default values (own cert-controller for the webhook, no CPU limits).
- **`utils.mariadb.create_mariadb_database` is the one way to get a MariaDB**, as `utils.cnpg` is for PostgreSQL. It creates the root Secret, a single-instance `MariaDB`, a `Database`, a `Backup`, and a NetworkPolicy.
- **Storage on the default StorageClass (Longhorn)**, so the volume joins the nightly Longhorn backup too.
- **Daily logical dumps** (`Backup` CR, 21:00 UTC like the CloudNativePG backups, gzip) to the bucket `mariadb-backups` with its own QuObjects key (`QuObjects MariaDB Backup`), one prefix per database. Logical, not physical: a dump restores across MariaDB major versions, and the databases are small. Only the application database is dumped (`databases: [<name>]`); without it the operator also dumps the `mysql` system schema.
- **Access policy:** a NetworkPolicy admits port 3306 only from pods in the same namespace and from the operator namespace. TLS is off: clients are inside the namespace behind that policy, and TLS adds negotiation differences between client libraries.
- **`Database` has `cleanupPolicy: Skip`:** deleting the resource never drops data.
- **Alert `mariadb-backup-stale`** (critical) selects every CronJob named `*-mariadb-backup`, so each new database is covered without a new rule.

## Consequences

- **Retention is not enforced on QuObjects.** The operator's cleanup (`maxRetention`) parses the date from the object key; QuObjects stores or returns the key as `backup.2026-10-28T18%3A43%3A27Z.sql.gz`, the parse fails ("error parsing backup date. Skipping") and nothing is deleted. Uploads work (verified, 7.8 MB for the TeslaLogger database). Dumps are small, so growth is a few MB a day; the setting is kept so retention starts working if the key handling is fixed upstream. Follow-up: a lifecycle rule on the bucket, or a periodic delete by the user.
- The operator's `mariadb` image tags follow the upstream MariaDB versions; Renovate is capped per database (TeslaLogger: below 10.12).
- A restore is a manual `Restore` CR or `mariadb < dump`; no restore rehearsal exists yet beyond the import of the legacy dump (follow-up before the legacy data is deleted).

## Alternatives considered

- Plain MariaDB Deployment: no backup or status handling, the user preferred the operator.
- Physical backups (`PhysicalBackup`): tied to the MariaDB version, larger, not needed for 80 MB.
- Backups to a PVC: kept as the fallback if QuObjects rejected the S3 uploads; it did not.
- TLS required: more moving parts with MySql.Data, PHP mysqli and Grafana for no gain inside one namespace.

## Related notes

- [[ADR-0017 - First CloudNativePG cluster and QuObjects recovery]]
- [[ADR-0022 - CloudNativePG base backups at 21:00 UTC]]
