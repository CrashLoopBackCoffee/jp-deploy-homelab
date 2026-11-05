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

Accepted and applied on 2026-11-05, amended the same day (isolation, AdGuard, NTP, static lease). Open: the host must renew its DHCP lease, then the temporary DNS rules 270 and 271 go; the user has not yet confirmed that the host reaches the internet.

## Context

A new host `zuul-rust-worker` (`10.40.83.75`, MAC `a8:a1:59:2a:41:fb`) on VLAN 40 (`GaST`, interface `opt8`, `10.40.0.0/16`) could not reach the internet. VLAN 40 is the guest network: it must be as restrictive as possible, with no traffic to any other VLAN, but it needs DNS and HTTPS and maybe HTTP. The user then added: client isolation, a static lease, SSH from PeRS to the host, NTP, and DNS through AdGuard so that malware and ads are blocked.

Findings on 2026-11-05:

- DHCP works. No DHCP option 6 was set for GaST, so dnsmasq handed out the router (`10.40.0.1`) as DNS.
- `opt8` had only the automatic DHCP rules and `pass any, GaST net -> GaST net` (sequence 261). Everything else hit the default deny, so the host had no internet.
- **Rule 261 was wider than it looks.** `GaST net` includes the firewall's own address `10.40.0.1`, so guests could reach every service the router offers on that address (DNS, and [INFERENCE] the web GUI, which listens on all interfaces). It did not give or prevent guest-to-guest traffic: hosts in one VLAN talk to each other at layer 2 through the switch or access point, not through the firewall.
- AdGuard `10.10.53.1` (LXC `adguard`, CoRE) answers and blocks (`doubleclick.net` returns `0.0.0.0`). PeRS already uses it through DHCP option 6 (ADR-0048). Its allowed-clients setting could not be read; GaST is expected to be allowed.
- PeRS has `pass in any` from `opt6` (rule 221), so PeRS can already open SSH to `10.40.83.75` through the firewall; the host's `sshd` answers on port 22 (checked from the workstation through CoRE). Replies are stateful.
- Outbound NAT is Hybrid with the automatic rule that includes `opt8`. HoME's egress rules (ADR-0008) are the pattern.

## Decision

Rules on `opt8` (in, IPv4, source `GaST net`), created through the OPNsense API and applied:

| Seq | Match | Note |
|-----|-------|------|
| 261 | removed | guests could reach `10.40.0.1` |
| 270 | UDP 53 to this firewall | **temporary**, see below |
| 271 | TCP 53 to this firewall | **temporary** |
| 272 | UDP 53 to `10.10.53.1` (AdGuard) | |
| 273 | TCP 53 to `10.10.53.1` | |
| 280 | TCP 443 to anything except `RFC1918` | |
| 281 | TCP 80 to anything except `RFC1918` | the user said "maybe" |
| 290 | UDP 123 to any | NTP, as on HoME |

- **DNS goes to AdGuard.** DHCP option 6 for `opt8` is `10.10.53.1` (description `GaST DNS: AdGuard (ADR-0053)`), like PeRS. Rules 270 and 271 stay only until the host has renewed its lease: it still holds `10.40.0.1` as DNS. After the renewal (`networkctl renew <interface>` or `dhclient`, or a reconnect), delete 270 and 271 so that guests cannot bypass AdGuard through the firewall.
- **Static lease:** dnsmasq host `zuul-rust-worker` = `10.40.83.75`, MAC `a8:a1:59:2a:41:fb`, `client_id` `01:a8:a1:59:2a:41:fb` (uuid `c6da0bad-099b-4b7b-ba5a-5a6ff6b4eb33`). The current address is kept; no scheme exists for VLAN 40 (ADR-0049 covers HoME).
- **SSH from PeRS needs no new rule** (rule 221 above). CoRE reaches the host the same way; HoME has no rule towards GaST.
- **Client isolation:** removing rule 261 closes the router address; guests still reach each other at layer 2, which OPNsense cannot filter. That needs port isolation on the switch port and client isolation on the guest SSID (UniFi) for VLAN 40; where the host is attached is not known.
- **No traffic to other VLANs:** private ranges are excluded from 80 and 443, DNS goes only to AdGuard (plus the temporary firewall rules), NTP goes to the internet; every other port, including ICMP and SSH out, stays denied.

## Rejected

- `GaST net -> any` or `-> any except RFC1918` on all ports: much wider than asked.
- A public resolver through DHCP (for example `9.9.9.9`): no ad or malware blocking.
- Creating the rules in `deploy-opnsense`: its model is a February export and is not applied to production (see `deploy-home-assistant` `.okf/systems/opnsense.md`).
- An explicit PeRS to GaST SSH rule: it would duplicate rule 221.

## Consequences

- Guests get AdGuard filtering, but DNS over HTTPS to a public resolver on 443 bypasses it; blocking that needs a DoH domain or address list.
- AdGuard forwards `4jp.de` to OPNsense, so a guest can resolve internal names but cannot connect to their addresses.
- AdGuard is one LXC: its outage is a DNS outage for GaST (and PeRS). The `probe-failing` rule only covers it if `tcp 10.10.53.1:53` is in `Monitoring Targets` (ADR-0048 asks for it; not checked here).
- `100.64.0.0/10` and `169.254.0.0/16` are not in `RFC1918`, so TCP 80 and 443 to them would pass if a route existed. None exists here today.
- NTP to any lets a guest query any time server; HoME does the same.
- The CoRE interface allows CoRE to reach GaST (the workstation reached the host), so VLAN 40 is not isolated from CoRE; restricting that is a separate change.
- The rules were not exercised from the guest itself; they were checked from the configuration, `dig` and a port check only.
- Rollback: delete the rules whose descriptions start with `GaST guests:` and the option `GaST DNS: AdGuard` through `firewall/filter/delRule/<uuid>`, `dnsmasq/settings/delOption/<uuid>` and `apply`; there is no savepoint. Rule 261 was `pass any, GaST net -> GaST net`.
- Related: ADR 0008 (dual NIC routing, the HoME egress rules) in `deploy-home-assistant`, [[ADR-0048 - Name resolution for 4jp.de on OPNsense]].
