---
tags:
  - homelab
  - network
  - wireguard
type: network
status: active
created: 2026-03-20
updated: 2026-03-20
---

# WireGuard Topology

## Known topology elements

- Site-to-site tunnel exists and works.
- Floating or roaming clients use a distinct access path and are not yet equivalent operationally to site-to-site peers.
- Instance `Wireguard` (`wg0`, UDP 51822, `10.50.0.1`) serves roaming peers (`JPlovesUli` `10.50.0.16`, `MUDI7` `10.50.0.7`); instance `site2site-tobi` (`wg1`, UDP 51821) is the site-to-site tunnel. The WAN rule `Wireguard` passes UDP 51820-51822 to the firewall.
- Instance `ax51-wazuh` (UDP 51820, `10.60.0.0/30`) connects the AX51 server for Wazuh agent traffic only (2026-10-31): one peer, one rule on the WireGuard group (TCP 1514-1515 from `10.60.0.2` to `10.10.88.3`). See [[Wazuh Security Monitoring]].
- The roaming range `10.50.0.0/24` overlaps the planned VoIP VLAN `10.50.0.0/16` in [[VLANs]]; unresolved.

## Design note

Document site-to-site peers and roaming peers separately, including:
- endpoint reachability
- allowed IPs
- NAT expectations
- firewall rules
- DNS reachability after tunnel establishment
