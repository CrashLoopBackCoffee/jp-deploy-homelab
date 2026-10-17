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
updated: 2026-10-16
adr: 22
---

# ADR-0022 - CloudNativePG base backups at 21:00 UTC

## Status

Accepted on 2026-10-16.

## Context

The nightly base backups of `postgres-pilot` and `paperless-db` ran at 03:00 UTC ([[ADR-0017 - First CloudNativePG cluster and QuObjects recovery]], [[ADR-0020 - Paperless fresh install with Nextcloud off-site backup]]). On 2026-10-16 both failed at about 03:04 UTC with `NoSuchUpload ... The specified bucket does not exist`, and WAL archiving of `paperless-db` failed from 01:43 UTC. The bucket worked again later, and Mimir and Longhorn, which use other buckets, saw no errors. The user suspects the QNAP's HBS sync.

## Decision

- Run both ScheduledBackups at **21:00 UTC** (23:00 CEST), chosen by the user to stay clear of the HBS sync window.
- Only the two CloudNativePG schedules move. The Paperless restic job (02:00 UTC) writes to Nextcloud, not the QNAP, and Longhorn's 02:00 job is unchanged.
- The schedule stays in the stack configuration (`database.backup.schedule`); the code defaults stay at 03:00 and are always overridden.

## Consequences

- CloudNativePG cron runs in UTC. When DST ends on 2026-10-25, 21:00 UTC becomes 22:00 CET; change the value to `0 0 22 * * *` to keep 23:00 local, or accept the shift.
- WAL archiving continues all day, so the schedule only decides when the base backup happens. A base backup that fails still raises `cnpg-backup-stale` after 36 hours.
- The cause of the 2026-10-16 outage is unconfirmed. If the new window also fails, the problem is not the HBS schedule; check the QNAP's QuObjects logs.
- Verified 2026-10-17: the first backups in the new window, `postgres-pilot-backup-20261016210000` and `paperless-db-backup-20261016210000`, are `completed`. One clean night does not show the 03:00 failure was the HBS window; keep watching `cnpg-backup-stale`.
