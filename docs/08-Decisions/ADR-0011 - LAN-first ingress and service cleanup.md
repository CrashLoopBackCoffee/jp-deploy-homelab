---
tags:
  - homelab
  - adr
  - kubernetes
  - ingress
type: adr
status: accepted
date: 2026-10-10
created: 2026-10-10
updated: 2026-10-10
adr: 11
---

# ADR-0011 - LAN-first ingress and service cleanup

## Status

Accepted on 2026-10-10.

## Context

The inherited stacks assumed public exposure through Cloudflare tunnels (`cloudflared`). The homelab has a static IPv4 address and OPNsense, and the first goal is a working LAN-only cluster. Several inherited workspaces are not wanted.

## Decision

- Do not use Cloudflare for ingress. Remove the `ingress` workspace (Cloudflared tunnels).
- Cloudflare stays as the DNS provider for `4jp.de`, used for cert-manager DNS-01 challenges ([[ADR-0010 - Cloudflare account token for the Kubernetes stack]]).
- For now, LAN clients route directly to the cluster (MetalLB address, Traefik, local DNS overrides on OPNsense) with certificates issued in-cluster by DNS-01.
- Later, public exposure goes through the static IPv4 and Caddy on OPNsense. If Caddy can run the DNS challenge, certificates stay in the cluster; otherwise TLS terminates in Caddy.
- Remove the `svn`, `obsidian`, and `ollama` workspaces.
- Keep the `s3` (MinIO, remote Docker) workspace for now. Whether Longhorn backups use S3, NFS, or another target is decided when backups are designed.

## Consequences

- The repository now contains `backup`, `iot`, `k0s`, `kubernetes`, `monitoring`, `n8n`, `paperless`, and `s3`.
- The `paperless`, `n8n`, and legacy `monitoring` stacks still carry Cloudflare configuration inherited from the donor. It is used mainly for the zone name; each needs its own mapping before it is deployed.
- `services/` was not tracked by git when these workspaces were deleted, so they can only be recovered from the donor repositories.
- Supersedes the part of [[ADR-0004 - Bare-metal k0s and external infrastructure scope]] that retained the Obsidian workspace.

## Related notes

- [[ADR-0010 - Cloudflare account token for the Kubernetes stack]]
- [[ADR-0008 - Phase 1 k0s API endpoint]]
- [[k0s]]
