---
tags:
  - homelab
  - adr
  - network
  - home-assistant
  - observability
type: adr
status: accepted
date: 2026-11-05
created: 2026-11-05
updated: 2026-11-05
adr: 49
---

# ADR-0049 - Home VLAN addressing and the Zweiradgarage lock on HoME

## Status

Accepted on 2026-11-05. **Executed:** the dnsmasq reservation. **Open:** the Wi-Fi swap on the device (done by the user), then steps 3 to 6 of the migration.

## Context

The Shelly Plus i4 `zweiradgarage` (`shellyplusi4-083af2012e48`, MAC `08:3a:f2:01:2e:48`, firmware 1.5.1, no auth) reports whether the bike storage is locked (input 0, `on` = locked). Home Assistant alerts on it (`Alert bike storage unlocked`, ADR-0046). It still sits on the legacy Fritz!Box Wi-Fi `ada30_24` at `192.168.178.222`, at -78 dBm, and the k0s cluster cannot reach `192.168.178.0/24` (ADR-0023, probes timed out again on 2026-11-05). The legacy `blackbox-slow` probe of `http://192.168.178.222/` is therefore the last LAN check of a security-critical device that the new stack cannot take over.

Read-only findings on 2026-11-05:

- `Wifi.GetConfig`: `sta` = `ada30_24`, `sta1` = `ADA30_HoME`, both enabled. A Shelly Gen2 only uses `sta1` when `sta` is not available (or the roaming threshold of -80 dBm is crossed), so it stays on the legacy network.
- MQTT is on (`192.168.178.122:1883`, topic prefix `zweiradgarage`); the outbound WebSocket is off. Home Assistant polls the device by host (config entry `Zweiradgarage`, source `zeroconf`).
- Pods on k0s reach HoME devices (`10.30.2.7:80`, `10.30.1.10:80`, `10.30.0.10:443` and `:1883` open), so a probe of an address on HoME works without a new firewall rule.
- Dynamic leases on HoME are rare; the existing HoME devices (`Washing`, `SLZB-06P10`, Home Assistant) have hand-made dnsmasq reservations with `client_id` `01:<mac>`.

## Decision

- **The lock moves to the HoME VLAN (30).** Wi-Fi 1 on the device becomes `ADA30_HoME`, Wi-Fi 2 stays `ada30_24` as a fallback, so an HoME Wi-Fi problem does not silence the lock alarm. The user changes this in the Shelly web UI; the passphrase is not handled by an agent.
- **Addressing scheme on HoME: `10.30.<place>.<device>`.** The second octet is the VLAN tag. The third octet is the place: `0` basement, `1` first floor, `2` second floor, `3` attic (existing), and for outdoors `100 + compass bearing / 10`: north `100`, east `109`, south `118`, west `127`. The fourth octet starts at `10` for the first device of a place (Home Assistant `10.30.0.10`, `Washing` `10.30.1.10`). Existing exceptions (`SLZB-06P10` `10.30.2.7`) stay.
- **The Zweiradgarage is outside north: `10.30.100.0`.** The i4 gets the reservation `zweiradgarage` = `10.30.100.10` (dnsmasq, MAC `08:3a:f2:01:2e:48`, created 2026-11-05 through the API, uuid `58c80a00-ad1a-41f5-89df-95b5e32c4f7f`; first set to `10.30.118.10` by mistake and corrected the same day). The garden (south, `118`) and any other place get their own devices later; nothing else is reserved.
- **Scraping:** after the move the k0s Alloy probes the device itself, independent of Home Assistant: group `http`, target `http://10.30.100.10/rpc/Shelly.GetDeviceInfo`, so the critical `probe-failing` rule (emergency Pushover) fires when the device is unreachable. Home Assistant stays the owner of the unlocked alert (ADR-0046); the archive keeps `binary_sensor.bike_storage_unlocked`. The legacy `blackbox-slow` probe is not carried over.

## Rejected

- Plain DHCP lease: the probe target would change with the lease, which is not acceptable for a lock alarm.
- A third-octet scheme in pure degrees: north `0` is taken by the basement and `360` does not fit an octet.
- Disabling `ada30_24` and no fallback: the signal on HoME at that spot is unknown.
- An OPNsense rule or route from k0s to `192.168.178.0/24` for this device only: it would keep the device on the weaker network and keep a LAN exception for good.

## Migration

1. **Done 2026-11-05:** dnsmasq reservation `zweiradgarage` = `10.30.100.10`. Read the device first: its address, MAC and Wi-Fi settings.
2. The user swaps the Wi-Fi on the device (HoME first, `ada30_24` second). Check: the lease for the MAC appears with `10.30.100.10`, `Wifi.GetStatus` shows `ADA30_HoME`, the RSSI is better than -70 dBm.
3. In `deploy-home-assistant`: reconfigure the `Zweiradgarage` Shelly entry to `10.30.100.10` (it is `zeroconf`; the host changes by itself only when mDNS reaches HA on `enp0s19`, so set it explicitly) and set the device's MQTT server to `10.30.0.10:1883` (the legacy `192.168.178.122` is not reachable from HoME). Verify `binary_sensor.zweiradgarage_input` is available and `binary_sensor.bike_storage_unlocked` follows a lock toggle. Record the reservation in that repo's `.okf/systems/opnsense.md`.
4. Add the probe line to the Secure Note `Monitoring Targets` and apply `observability` from `main`; verify `probe_success` is `1`. Test the alert path once by unplugging or disabling the device Wi-Fi for longer than the rule's `for`.
5. Remove the `blackbox-slow` target `http://192.168.178.222/` (and its `ServiceDownSlow` coverage) from the legacy Prometheus; update ADR-0023 and the OKF notes.

## Consequences

- The last unmigrated LAN target of a security-critical device is gone; the Fritz!Box `192.168.178.1` ICMP probe, the Fritz!Box exporter and the QNAP node exporter (reachable through `qnap.4jp.de`) remain for ADR-0023.
- A device on HoME depends on the HoME Wi-Fi and OPNsense; the probe from k0s covers both.
- Related: [[ADR-0046 - Home Assistant owns the garage lock and MyPV alerts]], [[ADR-0023 - Retire the legacy dockerhost monitoring stack]], [[ADR-0048 - Name resolution for 4jp.de on OPNsense]].
