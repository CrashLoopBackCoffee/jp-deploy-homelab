---
tags:
  - homelab
  - incident
  - wireguard
type: incident
status: documented
date: 2026-03-16
severity: medium
---

# INC-2026-03-16 - WireGuard floating clients handshake failure

## Summary

Floating clients could not connect reliably although the site-to-site tunnel was working.

## Symptoms

OPNsense kernel logs showed repeated handshake initiation and timeout behavior, including retries and eventual give-up messages.

## Key context

- Site-to-site tunnel was working correctly.
- The problem scope was limited to floating clients.

## Root cause

Final root cause was not fully captured in the preserved project context.

## Durable lesson

Do not generalize from a working site-to-site tunnel to roaming client health. Treat them as separate troubleshooting domains.
