---
tags:
  - homelab
  - architecture
  - remote-access
  - vpn
type: architecture
status: draft
created: 2026-03-20
updated: 2026-03-20
---

# Ingress and Remote Access

## Current understanding

- Static IPv4 provides a stable ingress baseline.
- WireGuard is used for at least site-to-site and roaming client access.
- Site-to-site connectivity is known to work.
- Roaming or floating clients had connectivity issues associated with incomplete handshakes.

## Implications

- Site-to-site and roaming client designs should be treated as separate operational paths.
- A working site-to-site tunnel does not validate the full remote access design for roaming clients.
