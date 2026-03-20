---
tags:
  - homelab
  - service
  - opnsense
type: service
status: active
created: 2026-03-20
updated: 2026-03-20
---

# OPNsense

## Purpose

Edge firewall, router, and likely the main network service integration point.

## Current role

- Routing and policy enforcement
- DHCP/DNS integration decisions
- WireGuard endpoint hosting

## Relevant topics observed

- Migration away from deprecated ISC DHCP
- Decision pressure between Kea and dnsmasq
- Interaction with Unbound and AdGuard
- WireGuard troubleshooting for roaming clients

## Known issues

- WireGuard floating clients experienced handshake completion failures.
- DHCP/DNS architecture is still being refined.

## Related notes

- [[dnsmasq]]
- [[Unbound]]
- [[AdGuard]]
- [[WireGuard]]
- [[ADR-0001 - Use dnsmasq instead of Kea on OPNsense]]
