---
tags:
  - homelab
  - service
  - unbound
type: service
status: active
created: 2026-03-20
updated: 2026-03-20
---

# Unbound

## Purpose

Recursive DNS resolver in the homelab DNS path.

## Current role

Unbound is part of the architecture discussion around how recursive resolution, local names, and filtering should be composed with dnsmasq and AdGuard.

## Open design topic

Determine whether Unbound should remain the recursive backend under AdGuard, whether it should integrate with dnsmasq for local records, and whether it can reduce the need for AdGuard in some use cases.
