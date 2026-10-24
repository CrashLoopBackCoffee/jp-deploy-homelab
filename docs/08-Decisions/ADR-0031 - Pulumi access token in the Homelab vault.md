---
tags: [homelab, adr, security, pulumi]
type: adr
status: accepted
date: 2026-10-24
created: 2026-10-24
updated: 2026-10-24
adr: 31
---

# ADR-0031 - Pulumi access token in the Homelab vault

## Status

Accepted on 2026-10-24.

## Context

Inside this repository, `OP_SERVICE_ACCOUNT_TOKEN` makes `op` use the `pulumi-homelab` service account, which can read only the `Homelab` vault. The `pulumi` shell plugin's personal access token item was in `Hosting`, so `op plugin run -- pulumi` failed with 403 Forbidden. Pulumi itself still needs the service-account token because the Pulumi program uses `pulumi_onepassword`.

## Decision

The Pulumi Personal Access Token item lives in the `Homelab` vault, and the `op` shell plugin for `pulumi` reads it from there.

## Consequences

- Anyone holding the service-account token can now also use Pulumi Cloud as `jaypee-solutions`, including stack state and decrypting stack secrets because the stacks use the default service-managed secrets provider.
- The original item was moved and is recoverable from Recently Deleted.

## Related notes

- [[ADR-0013 - 1Password service account for Pulumi]]
