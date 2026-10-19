---
tags:
  - homelab
  - adr
  - dns
  - cloudflare
type: adr
status: accepted
date: 2026-10-19
created: 2026-10-19
updated: 2026-10-19
adr: 29
---

# ADR-0029 - Service names as Cloudflare A records

## Status

Accepted on 2026-10-19. Applied to Tandoor; the existing dnsmasq records are unchanged (see Consequences).

## Context

[[ADR-0012 - Local DNS records through dnsmasq on OPNsense]] put every service name into dnsmasq on OPNsense, and `paperless`, `g`, `syslog` and `k8s-ingress-prod` are there. When the user moved Tandoor on 2026-10-18 they did not add a dnsmasq record: they changed the existing Cloudflare A record `tandoor.4jp.de` to Traefik's address `10.10.88.1`. It worked at once, from the LAN resolver and from `1.1.1.1` alike. The workstation's resolver could never resolve the dnsmasq-only names (`g.4jp.de`, `paperless.4jp.de`), which cost time in several sessions (see the gotchas in `HANDOFF.md`). Cloudflare already serves `4jp.de`, and a scoped token with DNS Edit exists for cert-manager ([[ADR-0010 - Cloudflare account token for the Kubernetes stack]]).

## Decision

- **A service name is a Cloudflare A record in the public zone `4jp.de` that points at the private Traefik address, not a dnsmasq host record.** The user decided this on 2026-10-19: DNS stays in Cloudflare and is the default for new services.
- **Pulumi manages the record** with `utils.cloudflare.create_a_record` (never proxied, TTL automatic) and the scoped account token `op://Homelab/Cloudflare [4jp.de]/password`, the one cert-manager uses. The address is read from Traefik's Service, so the record follows a change of the load balancer address.
- **A record that the user created by hand is adopted once with Pulumi's `import_`** (`<zone id>/<record id>`), then the option is removed again. Tandoor's record was imported this way on 2026-10-19; the following preview showed no changes.
- dnsmasq host records stay possible for names that must not appear in public DNS, but nothing needs that today.

## Consequences

- The names and the private address `10.10.88.1` are public information. The address is not routable from outside and the repository already names it, but the list of service names (`tandoor`, `paperless`, `g`) is visible in public DNS. Customer-facing or sensitive names should not use this pattern.
- Every client that can reach `10.10.88.1` resolves the names, also through a resolver that does not know dnsmasq. This removes the gotcha that the workstation resolver cannot resolve LAN-only records, for the names that move.
- Resolvers with DNS rebinding protection can drop a public answer that carries a private address. It did not happen on the LAN resolver or on `1.1.1.1` (both returned `10.10.88.1` for `tandoor.4jp.de`); a client behind such a resolver would need an exception.
- A Cloudflare outage or a revoked token affects changes to the records, not resolution of existing ones (TTL 300 s at most for resolvers that cached them).
- **Not decided: moving the existing names.** `paperless.4jp.de`, `g.4jp.de`, `syslog.4jp.de` and `k8s-ingress-prod.4jp.de` still use dnsmasq. Moving them is a small change per stack (replace the `Host` resource with `create_a_record` and import the records created in Cloudflare), but `grafana.4jp.de` and `g.4jp.de` are tied to the phase 5 cut-over of [[ADR-0023 - Retire the legacy dockerhost monitoring stack]]. The user decides when.
- The token is not scoped down by Pulumi; scope it in Cloudflare to DNS Edit and Zone Read on `4jp.de` (ADR-0010).

## Alternatives considered

- Keep dnsmasq host records for every name (ADR-0012): LAN-only and private, but the workstation resolver and any client with its own resolver cannot resolve them.
- A wildcard record `*.4jp.de` to `10.10.88.1`: fewer records, but it would also answer for names that do not exist and hide typos.
- External-DNS in the cluster: automatic records from Ingress objects, but one more controller and a different resource model (the stacks use Traefik `IngressRoute`).

## Related notes

- [[ADR-0010 - Cloudflare account token for the Kubernetes stack]]
- [[ADR-0011 - LAN-first ingress and service cleanup]]
- [[ADR-0012 - Local DNS records through dnsmasq on OPNsense]]
- [[ADR-0028 - Migrate Tandoor to k0s]]
