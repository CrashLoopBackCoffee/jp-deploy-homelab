---
tags:
  - homelab
  - platform
  - hardware
type: platform
status: active
created: 2026-03-20
updated: 2026-03-20
---

# Host Hardware Notes

## OPNsense Platform Hardware

- N305-based firewall platform
- Two 10G SFP+ ports available

> WAN configuration and ISP facts: see [[Addressing and Domains]]
> Full device inventory: see [[Hardware Inventory]]

## 10GbE and Connectivity Strategy

10 GbE is a recurring design theme across the lab: firewall, switch core, NAS, workstation endpoints, and Mac connectivity.

### Media Direction

There is a strong pull toward SFP+ in the core. Reasons:

- Lower power draw in many scenarios
- Lower heat than 10GBase-T in many scenarios
- Better fit with existing SFP+ firewall interfaces
- Cleaner scale-out for switching

### Practical Constraint

Do not assume 10GBase-T will reliably negotiate 10G just because both endpoints nominally support it. Factors that matter:

- Cable quality and length
- PHY compatibility
- Thermals
- Host adapter implementation

### Working Design Principle

Prefer SFP+ where the endpoint and cabling path make it practical. Use RJ45 10G where compatibility or convenience outweighs efficiency concerns.

### Mac Connectivity

For the MacBook, Thunderbolt-to-SFP+ is aligned with the broader design if the switching core is primarily SFP+. Relevant adapters: Sonnet Solo10G-TB3, OWC alternatives.

### Open Standardization Topic

Still unresolved: where SFP+ should be mandatory, where RJ45 10G is acceptable, and which links should use DAC, fiber, or copper.

## Linux NIC Driver Diagnostics

A failed bind to `r8169` with `No such device` indicates the need to verify:

- Actual PCI address
- Current driver binding
- Whether the device still exists at that path
- Interface renaming or mapping mistakes

## QNAP 10G Module Loading

A missing or unloaded module such as `ixgbe` can fully explain an apparently unsupported 10G card. Verify module is loaded before assuming hardware failure.
