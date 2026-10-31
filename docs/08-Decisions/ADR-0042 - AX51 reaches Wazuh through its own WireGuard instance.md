---
tags:
  - homelab
  - adr
  - security
  - wazuh
  - wireguard
type: adr
status: accepted
date: 2026-10-31
created: 2026-10-31
updated: 2026-10-31
adr: 42
---

# ADR-0042 - AX51 reaches Wazuh through its own WireGuard instance

## Status

Accepted on 2026-10-31 and applied the same day.

## Context

AX51 is a remote Docker host at a hosting provider (public address, no VPN to the LAN). The Wazuh manager's agent endpoint `10.10.88.3` is LAN-only with a source allowlist ([[ADR-0037 - Wazuh security monitoring on k0s]] decisions 8 and 20). OPNsense already runs two WireGuard instances: `Wireguard` for roaming clients (UDP 51822, `10.50.0.0/24`) and `site2site-tobi`. The user chose a WireGuard tunnel over a public port forward.

## Decision

- **A dedicated instance `ax51-wazuh`** on OPNsense (UDP 51820, tunnel `10.60.0.0/30`) with a single peer, instead of adding AX51 to the roaming instance. A separate instance has its own key, port and address, so a compromise or a rule mistake on one cannot widen the other, and the roaming peers are untouched. UDP 51820 is already covered by the existing WAN rule `Wireguard` (51820-51822), so no WAN rule changed.
- **One narrow rule** on the `WireGuard (Group)`: pass TCP 1514-1515 from `10.60.0.2/32` to `10.10.88.3/32`; everything else from the peer stays denied by default.
- **AX51 routes only what it needs**: `AllowedIPs = 10.60.0.1/32, 10.10.88.3/32`, so the host's other traffic never enters the tunnel; the tunnel is enabled at boot.
- **Manager allowlist** gets `10.60.0.2/32` through the single `agent-source-ranges` config list, now used by both the Service and the NetworkPolicy (the policy had a duplicate literal list before).
- **A preshared key** is added on top of the keypair; the private and preshared keys exist only on AX51 and in OPNsense.

## Consequences

- OPNsense WireGuard and firewall objects are created through the API with a token whose scope was widened by the user (WireGuard, firewall rules). `firewall/filter/savepoint` is not available on this OPNsense, so rule changes apply without automatic rollback. The objects are not in Pulumi (OPNsense is a pet, [[ADR-0003 - Pet vs Cattle and IaC tooling]]); they are recorded in [[WireGuard Topology]].
- Enrollment still does not verify the manager certificate (accepted in ADR-0037); the tunnel narrows who can reach the enrollment port.
- Every further remote host needs its own peer (or its own instance) and rule; add them to the allowlist individually as `/32`.
- The roaming tunnel range `10.50.0.0/24` overlaps the planned VoIP VLAN `10.50.0.0/16`; this change avoids the overlap with `10.60.0.0/30` and does not resolve the old one.

## Alternatives considered

- Public port forward of 1514/1515 limited to AX51's address: exposes the enrollment port to the internet and depends on source filtering alone.
- Peer on the existing roaming instance: simplest, but shares an interface, port and any broad rules with roaming clients.
- No agent on AX51: leaves a public Docker host without inventory or vulnerability reporting.

## Related notes

[[ADR-0037 - Wazuh security monitoring on k0s]], [[ADR-0029 - Service names as Cloudflare A records]]
