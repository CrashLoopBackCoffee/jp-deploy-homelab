---
tags:
  - homelab
  - adr
  - dns
  - opnsense
  - cloudflare
type: adr
status: accepted
date: 2026-11-03
created: 2026-11-03
updated: 2026-11-03
adr: 48
---

# ADR-0048 - Name resolution for 4jp.de on OPNsense

## Status

Accepted on 2026-11-03. **Executed on 2026-11-03:** steps 1 (forward swap), 2 (Private Domains `4jp.de`), 3 (overrides, see below), 7 (conditional upstreams in both AdGuards, applied by the user) and 8 (PeRS DHCP option). Open: the cleanup of the superseded dnsmasq apex records and Pulumi `Host` resources, and decision 4 (CNAME aliases), which does not work as written (see Executed). Supersedes the "records live in dnsmasq" part of [[ADR-0012 - Local DNS records through dnsmasq on OPNsense]] and refines [[ADR-0029 - Service names as Cloudflare A records]].

## Context

`4jp.de` grew into a zone that mixes device names, internal service names and public names. A pod could not resolve `home-assistant.4jp.de` (found while adding the probe of [[ADR-0046 - Home Assistant owns the garage lock and MyPV alerts]]).

Findings (2026-11-03, OPNsense Unbound 1.26.1 on `:53`, dnsmasq on `:53053`):

- **Cause.** Unbound Query Forwarding has `4jp.de` → `127.0.0.1:53053` ("Forward local domain to dnsmasq"). Every name below `4jp.de` goes to dnsmasq, which answers NXDOMAIN for what it does not hold. Verified as failing on OPNsense: every Cloudflare-only name (`influx`, `netbox`, `tandoor`, `home-assistant`, `pve`) **and the names with public IPs** (`id` 46.224.230.244, `wg` and `home` 93.240.83.68). Only dnsmasq records work (`g`, `paperless`, `syslog`, `k8s-ingress-prod`, `qnap`, `usw`, `sodola`) plus one Unbound host override (`router.4jp.de`, one address per interface).
- **Rebinding protection is active** and Private Domains is empty: private answers for public names are dropped (`10-30-0-10.sslip.io` returns no address). It has not mattered for `4jp.de` yet because nothing reaches Unbound's recursion. It will once the forward is removed.
- **A second forward exists for reverse lookups** (`10.10.in-addr.arpa` → dnsmasq) and must stay.
- **DHCP domains per VLAN already exist** in dnsmasq: `core.`, `home.`, `lan.`, `pers.`, `prox.`, `gast.`, `back.4jp.de`. The HoME VLAN's `home.4jp.de` collides with the public record `home.4jp.de` → 93.240.83.68.
- **Cloudflare holds 30 records.** 14 point to private addresses (`10.10.88.1` for `g`, `influx`, `netbox`, `paperless`, `tandoor`, `tesla-logger`, `grafana.tesla-logger`, `wazuh`, `k8s-ingress-prod`; `10.10.88.3` `wazuh-manager`; `10.10.8.1` `k0s0`; `10.10.0.10` `qnap`; `10.30.0.10` `home-assistant`; `10.1.0.1` `router`) and 11 to the legacy dockerhost `192.168.178.125` (about to be retired). `g`, `paperless`, `k8s-ingress-prod` and `qnap` also exist in dnsmasq. `syslog`, `usw` and `sodola` exist only in dnsmasq.
- **Two AdGuard Home instances filter ads:** `192.168.178.171` for the legacy `192.168.178.0/24` (the Fritz!Box DHCP hands it out; it is also `dockerhost`'s resolver) and `10.10.53.1` (LXC `adguard`, CoRE) for PeRS (`10.20.0.0/16`). Both resolve Cloudflare names (public and private answers; AdGuard does not drop rebinding answers) and block ads (`doubleclick.net` → `0.0.0.0`). Neither resolves the dnsmasq-only names (`usw`, `syslog`) or the VLAN subdomains (`home-assistant.home.4jp.de`, PTR), so their clients see only Cloudflare.
- **OPNsense DHCP does not point PeRS at AdGuard.** The dnsmasq DHCP options are empty, so every OPNsense-served VLAN, PeRS included, gets the router as DNS. Pods, CoRE, HoME, PROX, back and guest clients use OPNsense by design. The workstation uses `1.1.1.1`/`9.9.9.9` directly, and Home Assistant gets DNS from DHCP on both NICs. The repository's own sketch (`DNS Resolution Flow`) says "client → AdGuard and/or dnsmasq → Unbound"; the composition was never settled.

## Decision (proposed)

1. **Replace the `4jp.de` forward with one forward per VLAN subdomain** (`core.`, `home.`, `lan.`, `pers.`, `prox.`, `gast.`, `back.4jp.de`) to dnsmasq; keep the reverse forward. Names under the apex then resolve like any other public name.
2. **Add `4jp.de` to Unbound's Private Domains** so Cloudflare answers with private addresses are not dropped.
3. **Three classes of names:**
   - **Devices:** `<host>.<vlan>.4jp.de`, from DHCP and dnsmasq, never in Cloudflare.
   - **Services:** `<service>.4jp.de`, Cloudflare is the source of truth (ADR-0029). Public names keep their public addresses.
   - **Internal-only infrastructure** (`usw`, `sodola`, `syslog`, `router`): Unbound host overrides, no public record. These replace the dnsmasq apex records.
4. **Optional, per name: CNAME instead of a private A record.** `service.4jp.de` becomes a Cloudflare CNAME to an internal canonical name such as `home-assistant.home.4jp.de` or `k8s-ingress-prod.core.4jp.de`, so no private address is public. Only for names whose consumers all use OPNsense DNS; names used by other resolvers (workstation, `dockerhost`, Home Assistant for `influx.4jp.de`) keep the A record. Not adopted globally: 14 private-address records are already public (ADR-0029) and the CNAME form breaks clients that do not use OPNsense DNS.
5. **Resolve two collisions** before the forward change: `home.4jp.de` (public WAN address vs HoME VLAN domain; an Unbound host override keeps the public address, or the VLAN domain is renamed) and the stale `router.4jp.de` (Cloudflare `10.1.0.1`, Unbound override per interface).
6. **Staging:** (a) create the Unbound overrides for the infra names and verify; (b) swap the forward and add the Private Domain in one step; (c) test with a throwaway Cloudflare record (A and CNAME) from a pod and the workstation, with the old forward ready for an instant rollback; (d) remove the superseded dnsmasq apex records; (e) switch the Pulumi helper for internal-only names back to the Unbound API.
7. **AdGuard asks OPNsense for local names (conditional upstreams, chosen by the user on 2026-11-03).** Only after the Unbound fixes (steps 1 to 6) are verified. The variants considered:
   - **Conditional upstreams (chosen):** `[/4jp.de/]10.10.0.1` and the private reverse zones; all other queries keep `1.1.1.1`/`9.9.9.9` and the filtering. An OPNsense outage then only affects `4jp.de` names.
   - **Whole upstream (the user's proposal):** upstream `10.10.0.1` for everything, with the public resolvers as AdGuard's fallback servers (used only when OPNsense does not answer). One path for all names and OPNsense's DNSBL on top, but rebinding protection then applies to every name, and an OPNsense outage is a DNS outage for those clients. Do not keep `1.1.1.1` as a parallel upstream: the fastest answer would win and internal-only names would flap between NXDOMAIN and the real answer.
   Unbound becomes the single authority for local names (VLAN subdomains, infra overrides, CNAME targets, PTR). Reachability of `10.10.0.1:53` from `192.168.178.171` was verified from the legacy LAN. **Changing the AdGuard upstream before the Unbound fix breaks names:** measured 2026-11-03, `influx`, `home-assistant`, `netbox`, `tandoor`, `id`, `pve`, `home` and `wg` resolve through AdGuard today and return NXDOMAIN on OPNsense.
8. **PeRS uses AdGuard `10.10.53.1` through DHCP** (independent of steps 1 to 7, can go first):
   - **Setting:** a dnsmasq DHCP option on the PeRS interface: type `set`, interface `opt6`, option `6` (DNS server), value `10.10.53.1`, no `force`, description `PeRS DNS: AdGuard (ADR-0048)`; then reconfigure dnsmasq (`/api/dnsmasq/settings/add_option`, `/api/dnsmasq/service/reconfigure`). The token's dnsmasq privilege covers it. One server only, so every query is filtered; no secondary (a second server such as the router would let clients bypass the filter).
   - **Preconditions:** PeRS has `pass in any` from `opt6` (rule 221), so `10.10.53.1:53` is reachable; to confirm from a PeRS device before the change: `dig @10.10.53.1 adguard.4jp.de` returns `127.0.1.1` (a rewrite only AdGuard answers, so it also proves the path later) and AdGuard's allowed-clients setting does not exclude `10.20.0.0/16`.
   - **Effect on names:** PeRS moves from OPNsense to AdGuard. Cloudflare-only names (`influx`, `home-assistant`, `netbox`, `tandoor`, `id`, `pve`, `home`, `wg`) start to resolve; they return NXDOMAIN on OPNsense today. Names that only dnsmasq holds (`usw`, `sodola`, `syslog`, `<host>.<vlan>.4jp.de`, short names, PTR) stop resolving for PeRS until step 7.
   - **Rollout:** clients take the new server at their next renewal (half the lease) or reconnect; the range uses the default lease time. Check per device: DNS server `10.10.53.1`, the `adguard.4jp.de` fingerprint, and the device in AdGuard's query log.
   - **Rollback:** delete the option and reconfigure dnsmasq; clients return to the router on renewal.
   - **Availability:** AdGuard is one LXC (`adguard`, vmid 153); its outage is a DNS outage for PeRS. Add a probe `tcp 10.10.53.1:53` in the `Monitoring Targets` note (the existing critical `probe-failing` rule).
   - **Bypass, optional later:** clients with hardcoded or encrypted DNS (DoH, Android Private DNS, iCloud Private Relay) ignore DHCP. A port 53 redirect on `opt6` for destinations other than `10.10.53.1` stops plain-DNS bypass only; not part of this step.

## Rejected

- **Everything in Cloudflare, including infra (`usw`, `sodola`, `qnap`).** Puts more internal addresses into public DNS.
- **A new internal zone (`int.4jp.de`) with renamed services.** Cleanest, but renames every service and replaces the wildcard certificate. The VLAN subdomains and CNAMEs cover most of the benefit.
- **A dnsmasq domain override or the `local` flag.** All host records already have `local: 0`; the NXDOMAIN comes from the Unbound forward and dnsmasq's local zone, not from a host flag.

## Consequences

- Every OPNsense-served network is affected by the forward change; the reverse zone and the VLAN subdomains are not.
- Public names and Cloudflare-only names start to resolve on OPNsense-served networks.
- Clients that do not use OPNsense DNS never see Unbound overrides or the CNAME targets. Infra names then stay unresolvable for them, as today.
- AdGuard clients depend on OPNsense DNS for every `4jp.de` name after step 7; today they resolve the apex names through the public path even when OPNsense is down.
- Unbound's Private Domains must contain `4jp.de` before step 7, because AdGuard then reaches Cloudflare's private answers through Unbound.
- The OPNsense API user needs Unbound write privileges for step 1, 2 and 3 (read works since 2026-11-03).
- The probe record of PR #122 becomes unnecessary once the forward is replaced (`home-assistant.4jp.de` resolves through Cloudflare), and can be dropped.

## Open

- Cleanup (separate PR): drop the dnsmasq apex records that Pulumi creates (`syslog` in `observability`, `home-assistant` from PR #122, and the `g`, `paperless` and `k8s-ingress-prod` hosts in their stacks) now that the `4jp.de` forward is gone, and move internal-only names (`syslog`) to an Unbound host override managed through the Unbound API (decision 3).
- Whether `id.4jp.de` and `home.4jp.de`/`wg.4jp.de` are used from the LAN and need an explicit decision.
- The `192.168.178.171` AdGuard's upstreams and rewrites; `10.10.53.1` uses `1.1.1.1`/`9.9.9.9` and has the rewrite `adguard.4jp.de` → `127.0.1.1` (user, 2026-11-03). Their credentials are not in the Homelab vault.
- `10.10.53.1` lies inside the CoRE DHCP pool (`10.10.0.10` to `10.10.53.250`); a reservation or an excluded range avoids a future lease clash.

## Executed (2026-11-03)

- **Unbound, through the API:** Private Domains `4jp.de`; host overrides `usw` 10.1.0.24, `sodola` 10.1.0.12, `syslog` 10.10.88.2 and `home` 93.240.83.68 (all `4jp.de`, description `ADR-0048 internal-only`); seven forwards `core.`, `home.`, `lan.`, `pers.`, `prox.`, `gast.`, `back.4jp.de` → `127.0.0.1:53053`; the forward `4jp.de` (uuid `32f3ddc3-a6f9-41f3-88f0-cd83cde95bbf`) deleted; the reverse forward `10.10.in-addr.arpa` kept; Unbound reconfigured. Rollback: re-add the `4jp.de` forward (`127.0.0.1:53053`, forward first off) and reconfigure.
- **Verified from OPNsense, both AdGuards and a pod:** `influx`, `home-assistant`, `netbox`, `tandoor`, `id`, `pve`, `wg`, `home`, `g`, `paperless`, `qnap`, `usw`, `syslog` and `home-assistant.home.4jp.de` resolve; PTR of `10.10.53.1` answers `adguard.`; `doubleclick.net` stays `0.0.0.0` on AdGuard; the Home Assistant and AdGuard probes stay up and no probe fails. A throwaway Cloudflare A record resolved through every path.
- **Before the swap** AdGuard's new conditional upstream already sent `4jp.de` to OPNsense, so `influx` and `id` failed for PeRS and the legacy LAN until the forward was replaced (minutes).
- **CNAME aliases to `<host>.<vlan>.4jp.de` do not work.** A throwaway Cloudflare CNAME `zz-dns-test-c.4jp.de` → `home-assistant.home.4jp.de` returned NXDOMAIN on Unbound, on `1.1.1.1` and on AdGuard: Cloudflare is authoritative for `4jp.de`, follows the in-zone CNAME itself and answers NXDOMAIN, so the resolver never asks the internal forward. Decision 4 therefore does not apply while the target lies in the Cloudflare-hosted zone. Alternatives: a CNAME to a name outside that zone, an A record (status quo), or an Unbound host override with no public record. Test records were deleted.

## Related notes

- [[ADR-0012 - Local DNS records through dnsmasq on OPNsense]]
- [[ADR-0029 - Service names as Cloudflare A records]]
- [[ADR-0046 - Home Assistant owns the garage lock and MyPV alerts]]
