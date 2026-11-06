---
tags:
  - homelab
  - adr
  - backup
  - dockerhost
  - qnap
type: adr
status: accepted
date: 2026-11-06
created: 2026-11-06
updated: 2026-11-06
adr: 57
---

# ADR-0057 - No off-site copy of the dockerhost archive and Mimir history

## Status

Accepted on 2026-11-06.

## Context

[[ADR-0054 - Decommission dockerhost]] left the archive (`/backups/dockerhost`: `host/`, `workstation-legacy/`, `ansible/`, about 51 GB, plaintext secrets), the raw TSDB tarball and the backfilled Mimir history on one QNAP, with no off-site copy. The follow-up plan was an encrypted one-off copy to Nextcloud (`rclone crypt`, folder `offsite-dockerhost/`) before the Mimir retention reaches the oldest backfilled days on 2026-12-04.

The plan needed a new 1Password item `Dockerhost Offsite Crypt` (the workstation `op` cannot create items: error 101, no permission). Asked to create it, the user declined: dockerhost was a single host without a backup of its own, so an off-site copy of its leftovers is not wanted.

## Decision

- No off-site copy of the dockerhost archive.
- No off-site copy of the Mimir `mimir-metrics` bucket either: it holds the backfilled dockerhost history, covered by the same reasoning, and the raw TSDB tarball in the archive is the authoritative source if the history is ever needed again.
- No Nextcloud folder, rclone remote or crypt key is created.

## Consequences

- The user reported the dockerhost disk wipe on 2026-11-06 (done or under way), so the QNAP is the only copy. RAID5 does not protect against deletion, ransomware, a QNAP failure or fire (see `.okf/dockerhost-services.md` "Risks").
- Mimir retention deletes the oldest backfilled days from 2026-12-04; the raw TSDB tarball can re-create them with the ADR-0054 backfill procedure.
- Revisit if HBS 3 or another general QNAP off-site job exists: the archive then comes along with it, without an own plan.

## Reopening

The prepared approach: Nextcloud `https://cloud.jaypee.solutions` (account `Nextcloud Paperless Backup`, WebDAV, app password), `rclone copy` (never `sync`) into a `crypt` remote over `nc:offsite-dockerhost`, `rclone cryptcheck` afterwards, and a restore test of `ansible/` against its manifest. The free quota is unknown (`rclone about` shows no limit); at least 170 GB are needed for archive plus bucket (51 GB + 104 GB).

## Related

- [[ADR-0054 - Decommission dockerhost]]
- [[ADR-0056 - No-compact marks for Mimir blocks with checksum mismatches]]
