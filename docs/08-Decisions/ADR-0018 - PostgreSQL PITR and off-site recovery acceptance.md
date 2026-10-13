---
tags:
  - homelab
  - adr
  - kubernetes
  - postgresql
  - backup
type: adr
status: proposed
date: 2026-10-13
created: 2026-10-13
updated: 2026-10-13
adr: 18
---

# ADR-0018 - PostgreSQL PITR and off-site recovery acceptance

## Status

Proposed on 2026-10-13. Becomes accepted when the user approves the test procedure; becomes *verified* only when each acceptance check below has been observed. No application database migrates before both checks pass.

## Context

[[ADR-0017 - First CloudNativePG cluster and QuObjects recovery]] verified latest-state recovery (base backup plus archived WAL) into a separate cluster. On 2026-10-13 the first **scheduled** CloudNativePG backup (`postgres-pilot-backup-20261013030000`, ID `20261013T030000`) completed and the ObjectStore reports `lastSuccessfulBackupTime` `2026-10-13T03:00:00Z`; continuous archiving is healthy. The Longhorn `longhorn-daily-backup` job exists, but the cluster has **no Longhorn volumes** (all PVCs are on `openebs-lvm-postgres` or not yet created), so its scheduled run has had nothing to back up and remains unverified. Time-targeted recovery and the encrypted off-site copy of [[ADR-0016 - QuObjects backup target and encrypted offsite copy]] are untested.

## Decision

### Time-targeted PITR (cluster-internal)

1. Use the pilot's `public.recovery_probe` table (database `postgres`). Insert a marker row, wait, insert a second, record the database clock (`clock_timestamp()` in UTC) as the target `T`, wait, insert a third. Every row must be written **after** the 03:00 base backup finished so that `T` lies inside the base-backup-to-WAL range.
2. Force `pg_switch_wal()` after the third row and confirm `pg_stat_archiver` archived the segment; a target later than the last archived WAL cannot be reached.
3. Create a separate temporary Cluster with its own PVC whose `bootstrap.recovery` uses `recoveryTarget.targetTime = T` against the existing `postgres-pilot-store` ObjectStore (`serverName: postgres-pilot`). It MUST NOT archive WAL into the source prefix. Preview with `kubectl diff --server-side` before apply.
4. Accept when the restored database contains the first two rows and **not** the third, and the Cluster is promoted and healthy.
5. Delete the temporary Cluster only after explicit user approval and a server-side dry run, as in ADR-0017.

### Encrypted off-site copy (HBS 3, outside this repository)

- The user configures and runs the HBS 3 job; the agent cannot reach the QNAPs' management UIs. Acceptance requires all of: (a) the job source covers the `cnpg-backups` storage space, (b) client-side encryption is enabled and the destination NAS stores only ciphertext, (c) destination retention/versioning means a source-side deletion or ransomware cannot erase the only good copy, (d) the decryption password is held outside both NAS systems, (e) job success is observable (notification or log).
- Restore proof: HBS restores the off-site copy into a **new** bucket on the local QNAP (never over `cnpg-backups`). A temporary ObjectStore pointing at that bucket (with its own scoped credentials and `serverName: postgres-pilot`) feeds a temporary recovery Cluster; accept when the probe rows come back as in the PITR test.
- Longhorn's bucket gets the same job after the PostgreSQL path passes, and is accepted by restoring a disposable volume from the off-site copy.

## Consequences

- The PITR test mutates the pilot only by inserting three tiny rows. The restore Cluster costs one 2 GiB LVM volume while it exists.
- The off-site test needs user actions on the QNAP side (new restore bucket, scoped key stored in the `Homelab` vault, HBS job runs). These cannot be previewed with Pulumi; each is described to the user before it is needed.
- Until both checks pass, the pilot is recoverable from a same-site failure only in the sense of ADR-0017; loss of the QNAP loses all backups.

## References

- [CloudNativePG recovery target options](https://cloudnative-pg.io/documentation/current/recovery/)
- [Barman Cloud plugin recovery](https://cloudnative-pg.io/plugin-barman-cloud/docs/usage/)
- [HBS 3 client-side encryption policy](https://docs.qnap.com/application/hybrid-backup-sync/3v21.x/en-us/creating-a-backup-job-753C8301.html)
