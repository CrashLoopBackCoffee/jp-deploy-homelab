---
tags:
  - homelab
  - adr
  - network
  - opnsense
  - security
type: adr
status: accepted
date: 2026-11-05
created: 2026-11-05
updated: 2026-11-05
adr: 53
---

# ADR-0053 - GaST guest VLAN egress rules

## Status

Accepted and applied on 2026-11-05. The user has not yet confirmed that the new host reaches the internet; see Verification.

## Context

A new host `zuul-rust-worker` (`10.40.83.75`, MAC `a8:a1:59:2a:41:fb`, dnsmasq lease on `GaST`) could not reach the internet. VLAN 40 (`GaST`, interface `opt8`, `10.40.0.0/16`) is the guest network: it must be as restrictive as possible, with no traffic to any other VLAN, but it needs DNS and HTTPS and maybe HTTP.

Read-only findings on 2026-11-05:

- DHCP works: the host has a lease from the GaST range (`10.40.0.2` to `10.40.255.254`, domain `gast.4jp.de`). No DHCP option 6 is set for GaST, so dnsmasq hands out the router itself (`10.40.0.1`) as DNS.
- `opt8` had only the automatic DHCP rules and one rule, `pass any opt8 net -> opt8 net` (sequence 261, same-VLAN only). Everything else hits the default deny, so the host had **no DNS and no internet**. This is a missing allow, not a fault.
- Unbound listens on `opt8` and its access list default is Allow, so it answers on `10.40.0.1` (checked with `dig example.com @10.40.0.1` from the workstation).
- Outbound NAT is Hybrid with the automatic rule that includes `opt8`, so allowed traffic leaves NATed.
- HoME's egress rules (ADR-0008) are the pattern: DNS to `(self)`, TCP 443 and 80 to "not alias `RFC1918`". The alias `RFC1918` is `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`.

## Decision

Four pass rules on `opt8` (in, IPv4, source `GaST net`), created through the OPNsense API and applied:

| Seq | Match |
|-----|-------|
| 270 | UDP 53 to this firewall (`(self)`) |
| 271 | TCP 53 to this firewall |
| 280 | TCP 443 to anything except `RFC1918` |
| 281 | TCP 80 to anything except `RFC1918` |

- **No traffic to other VLANs:** the private ranges are excluded from 80/443 and DNS goes only to the firewall; every other port stays denied by default, including SSH, ICMP and NTP.
- **The firewall itself offers only DNS:** the GUI (443), SSH and every other service on the router are reached through RFC1918 addresses, so they stay blocked.
- **HTTP is allowed** (the user said "maybe"); remove rule 281 if it is not needed.
- **Rule 261 (guest to guest inside VLAN 40) was left as it was.** It is not "another VLAN", but it means guests can reach each other. Remove or narrow it for client isolation.

## Rejected

- `GaST net -> any` or `-> any except RFC1918` on all ports: much wider than asked.
- A DNS server other than the firewall (for example `9.9.9.9` through DHCP option 6): the guest would then need a rule to a public resolver and could resolve outside the controlled path. The firewall's Unbound is already authoritative for the local names.
- Creating the rules in `deploy-opnsense`: its model is a February export and is not applied to production; the live configuration is ahead of that repository (see `deploy-home-assistant` `.okf/systems/opnsense.md`).

## Consequences

- A guest can resolve internal `4jp.de` names through Unbound (Private Domains and overrides) but cannot connect to the addresses. Point DHCP option 6 for GaST at a public resolver and allow only that if this leak matters.
- `100.64.0.0/10` (CGNAT, also used by some VPNs) and `169.254.0.0/16` are not in `RFC1918`, so TCP 80 and 443 to them would pass if a route existed. None exists here today.
- No NTP: a guest with a wrong clock will fail TLS. Add UDP 123 to any (as HoME has) if it happens.
- The rules were not exercised from the guest itself; the traffic path and NAT were checked from the configuration only.
- Rollback: delete the four rules (descriptions start with `GaST guests:`) through `firewall/filter/delRule/<uuid>` and `apply`; there is no savepoint.
- Related: ADR 0008 (dual NIC routing, the HoME egress rules) in `deploy-home-assistant`, [[ADR-0048 - Name resolution for 4jp.de on OPNsense]].
