---
tags:
  - homelab
  - runbook
  - lxc
  - proxmox
type: runbook
status: active
created: 2026-03-20
updated: 2026-03-20
---

# Runbook - LXC Network Debugging

## Goal

Diagnose container connectivity and DHCP failures on VLAN-backed bridges.

## Checks

1. Verify VLAN membership on the container veth.
2. Verify VLAN membership on the physical uplink bridge member.
3. Inspect `bridge vlan show` output for expected tagged and untagged behavior.
4. Confirm DHCP broadcasts are visible on the expected VLAN.
5. Only after Layer 2 validation, inspect DHCP server behavior.

## Key lesson

A DHCP symptom can still be a bridge VLAN tagging problem.
