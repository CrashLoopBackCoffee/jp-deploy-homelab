---
tags:
  - homelab
  - adr
  - kubernetes
  - backup
  - storage
type: adr
status: accepted
date: 2026-10-12
created: 2026-10-12
updated: 2026-10-12
adr: 16
---

# ADR-0016 - QuObjects backup target and encrypted offsite copy

## Status

Accepted on 2026-10-12 as the backup architecture. Bucket access, usable TLS identity, schedules, and restore checks must be verified before claiming protection for any workload.

## Context

Phase 1 has one k0s node. Longhorn runs with one replica and PostgreSQL uses node-local OpenEBS LVM; neither survives loss of its disk without an independent backup. The old MinIO workspace was removed in [[ADR-0015 - Remove MinIO and the s3 workspace]]. We considered local NFS, IDrive E2, and Hetzner Object Storage. NFS alone cannot serve CloudNativePG's supported Barman Cloud physical-backup and WAL-archive integration, and an external S3 provider would incur recurring cost and require a separate client-side encryption solution to meet the off-site requirement. The user identified QuObjects on the local QNAP and a second QNAP at another site.

## Decision

- Use the local QNAP's QuObjects S3-compatible service as the primary off-node backup target. The user approved the names `longhorn-backups` and `cnpg-backups` for two **private buckets**, with separate QNAP access keys stored as `QuObjects Longhorn Backup` and `QuObjects CNPG Backup` in the `Homelab` vault. These buckets and items are not created yet. Scope each key to its own storage space/bucket using QuObjects' actual permission controls and allow only the list/read/write/delete operations its client needs. Keep QuObjects and the NAS outside this Pulumi repository; configure the Kubernetes clients here. The user supplied `10.10.0.10:8010` as the current address; obtain the exact DNS name and install a trusted HTTPS certificate covering it before applying the stack. Never infer another NAS address from its inventory role or disable TLS verification in production.
- Use Longhorn's S3 backup target and recurring backup jobs for Longhorn volumes. Longhorn controls backup retention in its own backup store; do not set a bucket lifecycle policy that independently deletes its backup objects. A recurring job only protects volumes to which it is assigned, and a configured target alone is not evidence of a completed backup.
- Use the CloudNativePG Barman Cloud plugin for PostgreSQL physical base backups and continuous WAL archiving to its own QuObjects bucket. A volume snapshot or `pg_dump` is not a substitute for this recovery path. Restore a backup to a separate cluster and exercise point-in-time recovery before migrating durable application data.
- Use an HBS 3 backup job from the local QNAP's QuObjects storage to the second, off-site QNAP with **client-side encryption**. NAS-to-NAS HBS setup remains outside Pulumi. Confirm that the actual job/destination offers client-side encryption, retain its decryption password independently, avoid mirroring source-side deletions, and test a restore from the off-site copy. Until then, the second copy is a planned safeguard, not an established recovery guarantee.

## Consequences

- Both storage engines can use a compatible off-node backup interface without running an S3 server in the cluster. The primary QNAP remains a same-site failure domain until the encrypted off-site copy and its restore are verified.
- A read-only probe on 2026-10-12 reached QuObjects at `https://10.10.0.10:8010/` only with certificate validation disabled. Its self-signed certificate has subject `QNAP NAS` and no Subject Alternative Name; it cannot authenticate the supplied IP or any DNS name. The chosen remediation is a trusted certificate for a user-supplied DNS name, not an insecure-TLS exception; the name, DNS record, certificate, and verified HTTPS endpoint are pending. Buckets, scoped credentials, free capacity, backup schedules, off-site connectivity, and HBS encryption/restore status also remain implementation prerequisites; do not commit credentials.
- Losing the off-site encryption key makes that copy unrecoverable. Protect the key separately from the NAS systems. Test local restores as well as off-site restores; monitor both backup and HBS job results.

## Alternatives considered

- Local NFS: convenient for Longhorn, but not a supported direct Barman Cloud plugin destination for PostgreSQL WAL and physical backups.
- IDrive E2 or Hetzner S3: compatible object storage with an independent off-site failure domain, but extra recurring costs and an unmet client-side encryption requirement for direct Barman Cloud uploads. Hetzner SSE-C is server-side encryption, not encryption before upload.
- NFS plus Restic to Hetzner: Restic would encrypt the off-site copy, but PostgreSQL physical backup and WAL archiving to NFS would require additional custom plumbing. Superseded by the QuObjects option.

## Related notes

- [[ADR-0009 - LVM-backed local volumes for PostgreSQL]]
- [[ADR-0014 - Longhorn on a dedicated ext4 data disk]]
- [[ADR-0015 - Remove MinIO and the s3 workspace]]
- [[Open Questions]]

## References

- [Longhorn backup targets](https://longhorn.io/docs/1.13.0/snapshots-and-backups/backup-and-restore/set-backup-target/)
- [CloudNativePG backup methods](https://cloudnative-pg.io/docs/1.28/backup/)
- [Barman Cloud plugin S3-compatible providers](https://cloudnative-pg.io/plugin-barman-cloud/docs/object_stores/)
- [QuObjects setup](https://www.qnap.com/en-us/how-to/tutorial/article/quobjects-tutorial)
- [HBS 3 client-side encryption policy](https://docs.qnap.com/application/hybrid-backup-sync/3v21.x/en-us/creating-a-backup-job-753C8301.html)
