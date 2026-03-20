---
tags:
  - homelab
  - runbook
  - wireguard
type: runbook
status: active
created: 2026-03-20
updated: 2026-03-20
---

# Runbook - WireGuard Troubleshooting

## Goal

Triage handshake and connectivity issues for site-to-site and roaming clients.

## Checks

1. Separate the failing path: site-to-site vs roaming client.
2. Inspect OPNsense kernel log for repeated handshake initiation and timeout messages.
3. Validate peer endpoint, reachability, and allowed IP configuration.
4. Validate firewall and NAT policy for the specific peer type.
5. Confirm post-tunnel routing and DNS reachability.

## Validation

- Successful handshake
- Bidirectional traffic
- Expected routes installed
- DNS and application reachability over tunnel
