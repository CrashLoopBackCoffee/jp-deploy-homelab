---
tags:
  - homelab
  - adr
  - kubernetes
  - postgresql
  - backup
type: adr
status: accepted
date: 2026-10-16
created: 2026-10-16
updated: 2026-10-24
adr: 22
---

# ADR-0022 - CloudNativePG base backups at 21:00 UTC

## Status

Accepted on 2026-10-16.

## Context

The nightly base backups of `postgres-pilot` and `paperless-db` ran at 03:00 UTC ([[ADR-0017 - First CloudNativePG cluster and QuObjects recovery]], [[ADR-0020 - Paperless fresh install with Nextcloud off-site backup]]). On 2026-10-16 both failed at about 03:04 UTC with `NoSuchUpload ... The specified bucket does not exist`, and WAL archiving of `paperless-db` failed from 01:43 UTC. The bucket worked again later, and Mimir and Longhorn, which use other buckets, saw no errors. The user suspects the QNAP's HBS sync.

## Decision

- Run the ScheduledBackups at **21:00 UTC year-round**; the user chose to keep the UTC time across DST changes.
- Only the two CloudNativePG schedules move. The Paperless restic job (02:00 UTC) writes to Nextcloud, not the QNAP, and Longhorn's 02:00 job is unchanged.
- The schedule stays in the stack configuration (`database.backup.schedule`); the code defaults stay at 03:00 and are always overridden.

## Consequences

- In winter, 21:00 UTC is one hour before the QNAP's 23:00-local `DataVol1` snapshot. From 2027-03-28, CEST makes the backup and snapshot coincide again; revisit the schedule then.
- The QNAP's scheduled `DataVol1` snapshot normally takes about 45 seconds at 21:00 UTC. On 2026-10-22 it ran from 21:00:01 to 21:34:05, overlapping the CloudNativePG backups. That backup, `paperless-db-backup-20261022210000`, failed at 21:04:39 with `NoSuchUpload ... CompleteMultipartUpload: The specified bucket does not exist`; about 50 WAL archiving errors followed between 21:30 and 02:00 UTC, then recovered. Current state is `ContinuousArchiving=True` and `LastBackupSucceeded=True`.
- QNAP syslog shows RAID group 1 scrubbing from 2026-10-22 20:00:03 UTC until 2026-10-23 06:04:52 UTC, with 0 blocks repaired. This is the likely cause of the overload and backup failure; the HBS sync window is not the likely cause. The same Thursday 20:00 start coincides with the 2026-10-15 overload associated with the 10-16 outage, but that remains uncertain because the syslog receiver was not deployed then.
- Any nightly base-backup slot overlaps the weekly RAID scrub. A failed base backup self-heals at the next night's run; `cnpg-backup-stale` covers the 36-hour interval.
