---
tags:
  - homelab
  - adr
  - security
  - pulumi
type: adr
status: accepted
date: 2026-10-10
created: 2026-10-10
updated: 2026-10-24
adr: 13
---

# ADR-0013 - 1Password service account for Pulumi

## Status

Accepted on 2026-10-10. Supersedes the `OP_ACCOUNT` desktop-app approach used earlier the same day.

## Context

Pulumi resolves `op://` references through the 1Password provider. With the desktop-app integration (`OP_ACCOUNT`), every Pulumi run asks for a biometric approval, and an unanswered prompt fails the run with `authorization timeout`.

## Decision

- A 1Password service account `pulumi-homelab` has read-only access (`read_items`) to the `Homelab` vault. Its token is stored in the `Homelab` item `Pulumi Service Account` (field `credential`).
- `.envrc` exports `OP_SERVICE_ACCOUNT_TOKEN` from that item when entering the repository, which costs one biometric approval, and then loads the OPNsense API key and secret into `OPNSENSE_API_KEY`, `OPNSENSE_API_SECRET`, and `OPNSENSE_ENDPOINT` with `op inject`. After that, Pulumi and `op` run without prompts.
- The token has no expiry. Rotate it by creating a new service account and updating the item.

## Consequences

- A holder of the token can read every item in `Homelab` (verified: reads succeed, writes are refused). The token sits in the same vault it unlocks, so reading it still needs the interactive account.
- Pulumi stacks must only read secrets from 1Password. Anything that writes items, such as publishing the kubeconfig, uses the interactive `op` session.
- Items must be in the `Homelab` vault; the service account cannot see other vaults. This includes the Pulumi PAT used by the `op` shell plugin ([[ADR-0031 - Pulumi access token in the Homelab vault]]).

## Related notes

- [[ADR-0010 - Cloudflare account token for the Kubernetes stack]]
- [[ADR-0012 - Local DNS records through dnsmasq on OPNsense]]
