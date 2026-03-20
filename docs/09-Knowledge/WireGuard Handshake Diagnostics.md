---
tags:
  - homelab
  - knowledge
  - wireguard
type: knowledge
status: active
created: 2026-03-20
updated: 2026-03-20
---

# WireGuard Handshake Diagnostics

## Key insight

A successful site-to-site tunnel does not validate roaming client configuration.

## Explanation

The peer model, firewall policy, NAT expectations, endpoint selection, and allowed IP scope can differ materially between site-to-site peers and floating clients.

## Practical implication

Split troubleshooting by peer class first:
- site-to-site
- roaming client

## Common symptom

Repeated `Sending handshake initiation` messages followed by timeout and retry indicate that packets are not producing a valid response path.
