---
tags:
  - homelab
  - service
  - fritzbox
type: service
status: active
created: 2026-03-20
updated: 2026-03-20
---

# FritzBox

## Purpose

VoIP support and legacy client connectivity in one VLAN.

## Why it matters

This is an architectural exception that influences DHCP and DNS design boundaries but does not by itself determine the dnsmasq vs Kea decision.

## Design note

Treat the Fritz!Box VLAN as a special-case segment with explicit documentation of traffic expectations and ownership of services.
