---
tags:
  - homelab
  - foundation
  - dns
  - ipam
type: foundation
status: active
created: 2026-03-20
updated: 2026-03-20
---

# Addressing and Domains

## Known facts

- Public connectivity includes static IPv4.
- IPv6 delegation is a `/56`.
- `4jp.de` is the homelab domain baseline for locally hosted services.

## Implications

- Stable public addressing simplifies inbound access, DNS records, VPN endpoints, and allow lists.
- The `/56` provides enough space for clean IPv6 subnet allocation per VLAN.
- Using a single owned domain improves consistency across internal and externally reachable services.

## To document further

- VLAN-to-subnet mapping
- Internal vs external DNS naming scheme
- Split-horizon behavior, if used
- Reverse DNS conventions for internal records
