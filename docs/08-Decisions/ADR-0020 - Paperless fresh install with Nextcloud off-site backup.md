---
tags:
  - homelab
  - adr
  - kubernetes
  - paperless
  - backup
type: adr
status: accepted
date: 2026-10-15
created: 2026-10-15
updated: 2026-10-15
adr: 20
---

# ADR-0020 - Paperless fresh install with Nextcloud off-site backup

## Status

Accepted on 2026-10-15 for preparing Paperless on k0s. **Preparing** is not **deploying**: nothing is applied until the go-live gate below passes. Supersedes the Paperless-related parts of the donor workspace (Bitnami PostgreSQL, SSO, Google Drive and IDrive backups).

## Context

`services/paperless` is the donor's (TH) stack copied unchanged: it deploys a Bitnami PostgreSQL release, signs users in with the donor's Entra ID tenant and Google OAuth clients, reads Gmail, mounts a Synology NFS share for scanner intake, and backs up with restic to Google Drive and IDrive E2. None of those values or services exist in JP. The user confirmed there is **no existing Paperless data** to migrate. [[ADR-0018 - PostgreSQL PITR and off-site recovery acceptance]] forbids moving application data in before the HBS 3 off-site copy is verified, but the remote NAS is offline. The user has an off-site Nextcloud.

## Decision

- **Fresh install.** Nothing is migrated or restored into the new instance. The backlog item about migrating from a Bitnami release is closed.
- **Local accounts only.** Remove the Entra ID, Google OAuth and Gmail configuration, the allauth provider apps and the OIDC default group. An `admin` user is created with a generated password (exported as a Pulumi secret).
- **Database: a dedicated CloudNativePG cluster** `paperless-db` in the `paperless` namespace, replacing the Bitnami release: one instance on `openebs-lvm-postgres`, Barman plugin base backups and WAL archiving to its own prefix `paperless-db/` in the existing `cnpg-backups` bucket, same checksum workaround, daily 03:00 backup, 14-day recovery window ([[ADR-0017 - First CloudNativePG cluster and QuObjects recovery]]). Paperless reads the CNPG-generated `paperless-db-app` Secret, so Pulumi never handles the password. The cluster builder is a shared helper in `utils` rather than a copy of the pilot's code.
- **Scanner intake** is a share on the QNAP mounted through the existing NFS CSI driver at `/usr/src/paperless/consume`. The user creates the share and its NFS export for `k0s0` (outside Pulumi).
- **Application volumes** (`data`, `media`, `export`) are Longhorn volumes with sizes in the stack config. They join Longhorn's nightly backup group, which gives a local recovery path in addition to the restic copy.
- **Backups: restic over rclone WebDAV to the user's off-site Nextcloud**, replacing Google Drive and IDrive E2. One repository, client-side encrypted by restic; the restic password and the Nextcloud app password live in the `Homelab` vault. The `document_exporter` output (originals and manifest, no archives or thumbnails) is what is backed up, and restore uses `document_importer`. Retention 7 daily, 4 weekly, 6 monthly.
- **Go-live gate (Paperless-specific).** Paperless may go live **before** the HBS 3 test passes, because it has its own independent off-site copy, but only after all of these pass: (1) a backup completes to Nextcloud and `restic check` reports no errors; (2) a test document uploaded to Paperless is exported, backed up, deleted from Paperless, restored with the restore job and reappears; (3) the first CloudNativePG scheduled or on-demand backup for `paperless-db` completes. The HBS 3 rule of ADR-0018 still applies to every other application.

## Consequences

- A single off-site target means one failure is enough to lose the off-site copy; the Longhorn and Barman copies on the QNAP remain, and the HBS 3 copy will add the QNAP's own off-site later. Monitor the backup job: after go-live add an alert for the CronJob not succeeding for 36 hours, and the existing `cnpg-backup-stale` rule already covers `paperless-db`.
- Disk use: `export` holds a full copy of the original documents, so `media` and `export` need similar sizes. Volumes can be expanded (needs a pod restart).
- Prerequisites outside Pulumi, created by the user: 1Password items `Nextcloud Paperless Backup` (the website URL, the username and a custom field `app-password`; the item's own `password` is the account password, which Nextcloud rejects over WebDAV) and `Paperless Backup` (restic password), and the QNAP NFS share. The Pulumi 1Password resolver treats only `password`, `username`, `title`, `url` and `notes` as standard fields, so the config reads the URL from `url` and the app password from the custom field.
- On 2026-10-15 the stack `jaypee-solutions/paperless/prod` was created (empty) and a preview showed 29 resources to create, none applied. The Nextcloud app password passed a WebDAV create, upload, download and delete cycle. The QNAP share first failed with `mount.nfs: access denied by server`; after the user exported it for `k0s0` it passed mount, write, read, delete, mkdir and rmdir as uid 1000 (the NAS squashes all users to `nobody`; the share is world-writable).

## Alternatives considered

- Keep Google Drive and IDrive E2: working design, but third-party cloud accounts the user no longer wants to depend on.
- QuObjects plus HBS 3 only: consistent with ADR-0016, but there would be no off-site copy until the remote NAS is back.
- Keep SSO: would need new Entra ID or Google OAuth clients and secrets for JP; not wanted.
- Reuse `postgres-pilot` for Paperless: mixes the pilot's lifecycle with application data and ties PITR and backup prefixes to one cluster.

## Related notes

- [[ADR-0009 - LVM-backed local volumes for PostgreSQL]]
- [[ADR-0016 - QuObjects backup target and encrypted offsite copy]]
- [[ADR-0017 - First CloudNativePG cluster and QuObjects recovery]]
- [[ADR-0018 - PostgreSQL PITR and off-site recovery acceptance]]

## References

- [Paperless-ngx document exporter](https://docs.paperless-ngx.com/administration/#document-exporter)
- [rclone WebDAV backend (Nextcloud)](https://rclone.org/webdav/)
- [restic with rclone](https://restic.readthedocs.io/en/stable/030_preparing_a_new_repo.html#other-services-via-rclone)
