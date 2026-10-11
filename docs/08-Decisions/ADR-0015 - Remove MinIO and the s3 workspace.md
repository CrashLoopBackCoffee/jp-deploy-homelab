---
tags:
  - homelab
  - adr
  - storage
  - cleanup
type: adr
status: accepted
date: 2026-10-11
created: 2026-10-11
updated: 2026-10-11
adr: 15
---

# ADR-0015 - Remove MinIO and the s3 workspace

## Status

Accepted on 2026-10-11. This supersedes the "keep `s3` for now" decision in [[ADR-0011 - LAN-first ingress and service cleanup]] and the retention of the S3/MinIO workspace in [[ADR-0004 - Bare-metal k0s and external infrastructure scope]].

## Context

The `s3` workspace deployed MinIO as a Docker container on a remote host, with a versioned `pulumi` bucket. It still carried donor values (`synology.tobiash.net`, `tobiash.net`) and had no Pulumi stack in Pulumi Cloud, so it was never deployed for this homelab. MinIO is deprecated, and the QNAP, which hosts the always-on services, is deployed from its own repository. Pulumi state lives in Pulumi Cloud (`jaypee-solutions`), not in MinIO.

The legacy `dev` monitoring stack used MinIO as the only storage of its Mimir container and read the MinIO credentials from the `s3` stack.

## Decision

- Delete `services/s3` and the `pulumi-minio` dependency, including the workspace entry and the config-model registration in the root `pyproject.toml`.
- Delete the legacy Mimir pieces of the monitoring stack that cannot work without MinIO: `mimir_legacy.py`, `assets/mimir/config.yaml`, `MimirConfig`, the `mimir` block in `services/monitoring/Pulumi.dev.yaml`, and the `StackReference` to the `s3` stack. The rest of the legacy monitoring stack (cadvisor, alloy) stays.
- Longhorn and PostgreSQL backups need a target chosen when backups are designed. Candidates are an S3-compatible service (the `backup` and `paperless` stacks already use IDrive E2), NFS, or another target; none is decided here.

## Consequences

- No self-hosted S3 service remains in this repository. Anything that needs object storage uses an external service or the QNAP's own deployment.
- The legacy `dev` monitoring stack no longer runs Mimir; metrics from its alloy collector have no local long-term store until a replacement is chosen. The `prod` monitoring stack was not affected.
- The deleted code remains in git history before the removal commit.

## Related notes

- [[ADR-0003 - Pet vs Cattle and IaC tooling]]
- [[ADR-0011 - LAN-first ingress and service cleanup]]
- [[Open Questions]]
