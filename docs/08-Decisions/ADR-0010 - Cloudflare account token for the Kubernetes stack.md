---
tags:
  - homelab
  - adr
  - kubernetes
  - cloudflare
type: adr
status: accepted
date: 2026-10-10
created: 2026-10-10
updated: 2026-10-10
adr: 10
---

# ADR-0010 - Cloudflare account token for the Kubernetes stack

## Status

Accepted on 2026-10-10 for the Kubernetes Pulumi stack only.

## Context

The Kubernetes stack inherited a Cloudflare setup that needs a global API key plus account email, uses them to create a scoped token for cert-manager, and registers the Let's Encrypt account with that email. The only Cloudflare credential in the `Homelab` vault for `4jp.de` is the 1Password item `Cloudflare [4jp.de]`: an account ID (username) and a 53-character account API token (password). The token is active and can read the `4jp.de` zone. It is not allowed to list or manage account tokens, so the stack could not create a scoped child token with it.

## Decision

- The stack's Cloudflare config is `api-token` (a 1Password ref) plus `zone`. The global API key, email, and Pulumi Cloudflare provider are removed from the stack.
- The token is stored in the cluster as the cert-manager DNS-01 secret. It needs Zone Read and DNS Edit on `4jp.de`; Zone Read is verified, DNS Edit is not.
- The ACME contact email is a separate `cert-manager.acme-email` setting.
- The shared `utils.model.CloudflareConfig` is unchanged; other stacks keep their current shape.
- The 1Password ref uses the item title, `op://Homelab/Cloudflare [4jp.de]/password`, because the Pulumi resolver looks items up by title. The `op` CLI rejects brackets in titles, so use the item ID there.

## Consequences

- The cluster holds a token that is not scoped down by Pulumi. Scope the token itself to DNS Edit and Zone Read on `4jp.de` in Cloudflare.
- Certificate issuance will fail if the token lacks DNS Edit; this is only discovered on the first apply.
- Other stacks still use `utils.model.CloudflareConfig` with a global key and need their own mapping.

## Related notes

- [[ADR-0008 - Phase 1 k0s API endpoint]]
- [[k0s]]
