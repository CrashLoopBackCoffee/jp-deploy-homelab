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

- Use the local QNAP's QuObjects S3-compatible service as the primary off-node backup target. The user approved two **private buckets**, `longhorn-backups` and `cnpg-backups`, with separate QNAP access keys stored as `QuObjects Longhorn Backup` and `QuObjects CNPG Backup` in the `Homelab` vault. The user moved `cnpg-backups` into a dedicated storage space. Authenticated list requests now succeed for each key's own bucket and fail with `NoSuchBucket` for the other bucket; separate keys alone did not provide isolation before the move. Keep access scoped to each destination with QuObjects' actual NAS-user/storage-space permission controls and allow only the operations its client needs. Keep QuObjects and the NAS outside this Pulumi repository; configure the Kubernetes clients here. The chosen S3 endpoint is `https://qnap.4jp.de:8443`, not the earlier QNAP administration port `10.10.0.10:8010`. Never infer another NAS address from its inventory role or disable TLS verification in production.
- On QTS 5.2, manage the NAS server certificate at **Control Panel → System → Security → SSL Certificate & Private Key → Server Certificate → Replace Certificate → Import certificate**, not in QuObjects Server Settings. Import a trusted X.509 PEM certificate, its matching private key, and any intermediate chain for the chosen DNS name. This may affect other NAS HTTPS services; retain local admin recovery access and verify that QuObjects actually presents the replacement certificate on its S3 port (`8443` for `qnap.4jp.de`) before configuring Kubernetes clients. Prefer separately issued DNS-01 credentials over exporting the cluster's wildcard private key. Plan renewal of the imported certificate.
- Use Longhorn's S3 backup target and recurring backup jobs for Longhorn volumes. Longhorn controls backup retention in its own backup store; do not set a bucket lifecycle policy that independently deletes its backup objects. A recurring job only protects volumes to which it is assigned, and a configured target alone is not evidence of a completed backup.
- Use the CloudNativePG Barman Cloud plugin for PostgreSQL physical base backups and continuous WAL archiving to its own QuObjects bucket. A volume snapshot or `pg_dump` is not a substitute for this recovery path. Restore a backup to a separate cluster and exercise point-in-time recovery before migrating durable application data.
- Use an HBS 3 backup job from the local QNAP's QuObjects storage to the second, off-site QNAP with **client-side encryption**. NAS-to-NAS HBS setup remains outside Pulumi. Confirm that the actual job/destination offers client-side encryption, retain its decryption password independently, avoid mirroring source-side deletions, and test a restore from the off-site copy. Until then, the second copy is a planned safeguard, not an established recovery guarantee.

## Consequences

- Both storage engines can use a compatible off-node backup interface without running an S3 server in the cluster. The primary QNAP remains a same-site failure domain until the encrypted off-site copy and its restore are verified.
- The original read-only probe of `https://10.10.0.10:8010/` encountered the QNAP's self-signed certificate without a SAN. The user supplied `https://qnap.4jp.de:8443` instead; its certificate passes workstation hostname and chain verification, and authenticated read-only probes reach both buckets. Both QNAP NICs have separate static DHCP reservations and advertise `qnap`, so the router initially returned the wrong NIC (`10.10.0.6`, no S3 listener). The user applied an Unbound host override for `qnap.4jp.de` → `10.10.0.10` in OPNsense UI; direct queries to both router DNS ports then returned `.10`, and Longhorn reported its backup target Available without restarting CoreDNS.
- The Kubernetes Pulumi stack has applied the Longhorn S3 target, credential Secret, and daily recurring backup job (14 retained, `02:00` cron, `default` group). A 256 MiB disposable Longhorn PVC was written, backed up to QuObjects (`Completed`, 100%), restored into a separate volume, and read through a separate PVC with the original marker intact. The test resources, their Longhorn backup volume, and the test S3 volume prefix were removed afterward. The test confirms the local S3 recovery path, not protection for a production workload or the scheduled job's first run. Both keys now fail to list the other backup bucket; write/delete permissions and an application workload restore remain untested. The second NAS's off-site connectivity, HBS client-side encryption, and restore remain unverified; do not commit credentials.
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
- [QTS 5.2 server certificate replacement](https://docs.qnap.com/operating-system/qts/5.2.x/en-us/replacing-the-server-certificate-8E7C1926.html)
