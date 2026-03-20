---
tags:
  - homelab
  - network
  - dns
type: network
status: draft
created: 2026-03-20
updated: 2026-03-20
---

# DNS Resolution Flow

## Open design work

Finalize how queries traverse:

client -> AdGuard and/or dnsmasq -> Unbound -> upstream recursion

## Required decisions

- where local hostnames are authored
- where filtering occurs
- which component is authoritative for DHCP-derived names
