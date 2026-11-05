---
tags:
  - homelab
  - adr
  - netbox
  - inventory
type: adr
status: accepted
date: 2026-11-05
created: 2026-11-05
updated: 2026-11-05
adr: 52
---

# ADR-0052 - NetBox device inventory from Home Assistant, OPNsense and Proxmox

## Status

Accepted and executed on 2026-11-05.

## Context

NetBox (`netbox.4jp.de`, 4.7) held 13 devices (switches, patch panel, sockets, k0s0, `pve`, the DSL modem) and 49 `192.168.178.x/32` addresses auto-discovered by the nmap scanner, none of them assigned to a device. Every device moved or added in this session (AC•THOR, the Zweiradgarage i4) was undocumented, and the user asked to add the devices the agent knows.

## Decision

- **Sources, in order of trust:** live probes (`/shelly` returns MAC, model and firmware of every reachable Shelly), the OPNsense dnsmasq reservations and leases, the Home Assistant device registry snapshot (`deploy-home-assistant`, names, models, areas, addresses, MACs) and the Proxmox guest list. Values that could not be confirmed live say so in the device comment (sleeping Flood sensors, the Wall Display, `ChargerVickysiPad`, `Licht Office`).
- **In scope (13 devices before, 53 now including the AC•THOR of ADR-0051, plus 4 VMs):** network and infrastructure devices with a known model or role (Fritz!Box 7590, the OPNsense router, the QNAP, the other Netgear and JetKVM devices, `dockerhost`, `wireguard`), the energy chain (SolaX inverter, RS485 gateway, wallbox, Tasmota meter), the Zigbee coordinator, all Shelly devices Home Assistant manages (new roles `Relay`, `Smart Plug`, `Sensor`), the AV and printer devices with an address, and four Proxmox guests (`haos12.3`, `netbird-exit`, `forgejo-runner-ax41`, `adguard`) in a new cluster `pve`.
- **Out of scope:** personal clients (phones, tablets, laptops, watches, the roughly 100 devices the Fritz!Box tracks), the ESP32 Bluetooth proxies and the Zigbee end devices (IKEA, Aqara, SwitchBot; MAC or no address only), Apple TV, virtual Home Assistant devices (WashData, add-ons), and Proxmox guests of unknown state (`test-kali`, `desinfect`, `Zorin`, the k0s0 VM) and the `unifi` and `unifi-os-server` VMs that are not in the Proxmox export. They can follow when someone needs them.
- **Conventions:** device name is the Home Assistant name (duplicates get a place suffix: `Licht Dach`, `Licht Office`); one interface per physical port (`wifi0`, `eth0`, `lan`/`wan`), MAC as a separate object (4.7), IPv4 as `/24` on the legacy LAN, `/16` on the VLAN prefixes, `/32` on `10.1.x` (that prefix is not modelled, so no mask is claimed); the first address is the primary IPv4. Non-rack devices use `u_height` 0. Locations follow the Home Assistant area where a NetBox location exists; other areas (Bedroom, Garden, Dachboden) stay empty and are named in the comment.
- **Unknown hardware is said so, not guessed:** the OPNsense router, the QNAP, `dockerhost`, `wireguard` and the RS485 gateway have device types named `... (hardware not recorded)` / `(model not recorded)`. The dnsmasq host `sodola` (`10.1.0.12`, MAC `1c:2a:a3:1e:e6:b5`) is the existing `SL-SWTGW2C48NS` device: the user confirmed there is only one Sodola switch, so its management interface, MAC and address were added to that device (76 IPs, 43 MACs in total).
- **The scanner addresses are reused:** 22 existing `192.168.178.x/32` records were assigned to their devices, the mask corrected to `/24` and the `autodiscovered` description replaced. 26 IP addresses stay without an interface; `192.168.178.123` (old AC•THOR) and `192.168.178.222` (old i4) are among them and are stale.
- **NetBox stays the desired state:** where a device moved this session, NetBox shows the new address (`10.30.0.11`, `10.30.100.10`).

## Consequences

- IPAM and DCIM can answer "what is on this address / port" for the energy chain, the Shelly fleet and the infrastructure; the Fritz!Box-tracked clients remain undocumented on purpose.
- The Fritz!Box lists `192.168.178.97` for the dishwasher plug while the plug and Home Assistant say `.199`; NetBox follows the live answer.
- Open follow-ups: record the real hardware models, model cabling for more ports (only the AC•THOR is cabled to the Main Switch), add the `10.1.0.0/16` prefix and VLAN modes once its meaning is confirmed, and clean the stale scanner addresses.
- Related: [[ADR-0049 - Home VLAN addressing and the Zweiradgarage lock on HoME]], [[ADR-0051 - AC-THOR on HoME and LGTM alerts for unsupervised heating]], [[ADR-0030 - Migrate NetBox to k0s]].
