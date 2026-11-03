---
tags:
  - homelab
  - adr
  - dns
  - opnsense
type: adr
status: accepted
date: 2026-10-10
created: 2026-10-10
updated: 2026-10-10
adr: 12
---

# ADR-0012 - Local DNS records through dnsmasq on OPNsense

## Status

Accepted on 2026-10-10. **Narrowed on 2026-10-19:** new service names are Cloudflare A records ([[ADR-0029 - Service names as Cloudflare A records]]); the existing dnsmasq records (`paperless`, `g`, `syslog`, `k8s-ingress-prod`) stay until the user decides to move them. **Superseded in part on 2026-11-03 by [[ADR-0048 - Name resolution for 4jp.de on OPNsense]]:** Unbound no longer forwards `4jp.de` to dnsmasq, so dnsmasq records below the apex are not queried. The Pulumi `Host` records for `paperless`, `g`, `k8s-ingress-prod` and `home-assistant` are removed (Cloudflare serves them); `syslog` is an Unbound host override (`utils.opnsense.unbound.host.Host`). dnsmasq stays the DHCP server and holds the VLAN subdomains (`<host>.<vlan>.4jp.de`); `utils.opnsense.dnsmasq.host.Host` remains only for the undeployed `n8n` stack.

## Context

[[ADR-0001 - Use dnsmasq instead of Kea on OPNsense]] makes dnsmasq the DNS and DHCP service on OPNsense. The inherited Pulumi helper created local DNS records as Unbound host overrides, which are not served by dnsmasq. It was written for a setup where Unbound is the resolver.

## Decision

- Pulumi creates local DNS records as dnsmasq host records through the OPNsense API (`/api/dnsmasq/settings/{addHost,setHost,delHost}` and `/api/dnsmasq/service/reconfigure`), using `utils.opnsense.dnsmasq.host.Host`.
- The Unbound helper is removed. All callers (kubernetes, paperless, n8n, iot, monitoring) use the dnsmasq helper; it takes host, domain, and IP, and the A/AAAA type follows from the address.
- The OPNsense API user needs the privilege **Services: Dnsmasq DNS/DHCP: Settings**, which covers `api/dnsmasq/*`, including the service reconfigure call. It does not need any Unbound privilege.
- Credentials are the `OPNsense` item in the `Homelab` vault (username is the API key, password is the API secret); the endpoint is `https://router.4jp.de`.

## Consequences

- The Traefik host record `k8s-ingress-prod.4jp.de` and similar records appear in dnsmasq, not Unbound.
- An earlier trial grant of **Services: Unbound** to the API user is no longer needed and should be removed.
- Records are created through the API without checking for duplicates; a record that already exists in dnsmasq makes the create call fail with a validation error.

## Related notes

- [[ADR-0001 - Use dnsmasq instead of Kea on OPNsense]]
- [[ADR-0011 - LAN-first ingress and service cleanup]]
