---
tags:
  - homelab
  - adr
  - kubernetes
  - postgresql
  - backup
type: adr
status: accepted
date: 2026-10-12
created: 2026-10-12
updated: 2026-10-12
adr: 17
---

# ADR-0017 - First CloudNativePG cluster and QuObjects recovery

## Status

Accepted on 2026-10-12 for the first PostgreSQL pilot. Do not migrate durable application data until a base backup, WAL archive, and independent recovery have been verified.

## Context

The phase-1 k0s cluster has one controller+worker, `k0s0`. Its `postgres` LVM volume group has an OpenEBS LocalPV StorageClass, `openebs-lvm-postgres` ([[ADR-0009 - LVM-backed local volumes for PostgreSQL]]). The CloudNativePG 1.27.0 operator is running, but has no database clusters. The private QuObjects `cnpg-backups` bucket at `https://qnap.4jp.de:8443` is accessible using its dedicated 1Password credentials; cross-bucket listing now fails after the bucket was moved into a dedicated NAS storage space ([[ADR-0016 - QuObjects backup target and encrypted offsite copy]]).

## Decision

- Create one **pilot** CloudNativePG cluster `postgres-pilot` in its own namespace, with one PostgreSQL 17.10 instance and a 2 GiB data PVC on `openebs-lvm-postgres`. This is intentionally not HA: a single k0s node cannot host an independent standby, and an OpenEBS local PVC does not migrate to another host. Keep existing application databases unchanged.
- Install the official Barman Cloud CNPG-I plugin in `cnpg-system` alongside the operator, using the published `plugin-barman-cloud` Helm chart version 0.8.1. The native Barman backup fields in CloudNativePG 1.27 are deprecated; use a plugin `ObjectStore` in the pilot namespace, backed by a Kubernetes Secret populated from `QuObjects CNPG Backup` in the `Homelab` 1Password vault. Use the trusted S3 endpoint and a per-cluster prefix in `cnpg-backups`; never disable TLS verification.
- Enable continuous WAL archiving through the plugin and compress archived WAL with gzip. Schedule physical base backups daily at `0 0 3 * * *` (CloudNativePG's six-field cron expression), run the first backup immediately, and maintain a 14-day recovery window. A WAL archive alone is not restorable without a base backup.
- Set `AWS_REQUEST_CHECKSUM_CALCULATION=when_required` and `AWS_RESPONSE_CHECKSUM_VALIDATION=when_required` on the Barman instance sidecar: QuObjects rejects boto3's optional `PutObject` checksums with `InvalidDigest`. Keep TLS and mandatory integrity checks enabled. An `ObjectStore` update alone does not refresh an existing Pod's sidecar environment; use a CloudNativePG-managed rollout restart when changing these values.
- Verify a completed base backup, actual WAL objects, and restore into a **separate** test cluster before treating the pilot as a recoverable database. Test point-in-time recovery before migrating applications. Keep the test cluster and its data until its removal is explicitly approved.

## Consequences

- The PostgreSQL data PVC is on the dedicated WDC LVM-backed disk; the physical backup and WAL archives live off-node on the local QNAP. Loss of the single node interrupts service until recovery; the encrypted off-site HBS 3 copy remains a separate, unverified task in ADR-0016.
- The plugin adds a controller, CRD, and certificates to operate. The chart contains no Helm lifecycle hooks, so the Pulumi Helm Chart resource follows the existing operator pattern.
- The pilot consumes storage but has no application clients or migration cutover. Deleting its Cluster or PVC would be destructive and requires explicit approval; a Pulumi preview must precede any apply.
- On 2026-10-12, the first immediate backup and WAL archival failed with `InvalidDigest`; after applying the checksum settings and rolling the pilot Pod, WAL archival recovered. An on-demand base backup completed, and a separate 2 GiB cluster restored both a pre-backup marker and a post-backup marker via archived WAL. This verifies latest-state recovery, **not** a time-targeted PITR or the off-site HBS copy. After explicit user approval and a server-side deletion dry run, the temporary restore Cluster was deleted; its PVC and PV were reclaimed, while the pilot and successful backup remain.

## References

- [CloudNativePG 1.27 backups](https://cloudnative-pg.io/docs/1.27/backup/)
- [Barman Cloud plugin installation](https://cloudnative-pg.io/plugin-barman-cloud/docs/installation/)
- [Barman Cloud plugin usage and recovery](https://cloudnative-pg.io/plugin-barman-cloud/docs/usage/)
- [Barman Cloud plugin S3-compatible stores](https://cloudnative-pg.io/plugin-barman-cloud/docs/object_stores/)
