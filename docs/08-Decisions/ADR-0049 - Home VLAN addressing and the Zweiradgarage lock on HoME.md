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

Accepted on 2026-11-05. **Executed on 2026-11-05:** steps 1 to 5. **Open:** the weak signal (-82 dBm, below the device's roaming threshold of -80 dBm) and the end-to-end test of the probe alert.

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
2. **Done 2026-11-05:** the user moved the device (`Wifi.GetStatus`: `ADA30_HoME`, `10.30.100.10`, static lease). Deviation: Wi-Fi 1 and 2 both name `ADA30_HoME` and the legacy `ada30_24` is no longer configured, so there is no fallback; the RSSI is **-82 dBm**, worse than the -78 dBm on `ada30_24`.
3. **Done 2026-11-05:** in `deploy-home-assistant` the Shelly integration followed by itself (log `Connected to 10.30.100.10`, device `configuration_url` `http://10.30.100.10:80`, `binary_sensor.zweiradgarage_input` available). The device MQTT server was set to `10.30.0.10:1883` over RPC (`Mqtt.SetConfig`, then a reboot; `Mqtt.GetStatus` `connected: true`). The reservation is recorded in that repo's `.okf/systems/opnsense.md`. Not tested: a physical lock toggle against `binary_sensor.bike_storage_unlocked`.
4. **Done 2026-11-05:** the line `http http://10.30.100.10/rpc/Shelly.GetDeviceInfo` is in the Secure Note `Monitoring Targets`, `observability` was applied from `main` (1 Secret replaced). `probe_success{job="blackbox"}` is `1`, HTTP 200 in 23 ms. Not tested: the alert itself (device Wi-Fi off for longer than 10 minutes).
5. **Done 2026-11-05:** the legacy `blackbox-slow` job (its only target was `http://192.168.178.222/`, `ServiceDownSlow` was already pending) was removed from the template and from `/opt/monitoring/config/prometheus/prometheus.yml` on `dockerhost` (backup `prometheus.yml.pre-i4-move`, `promtool` valid, `SIGHUP`, reload successful, alert gone). The rule `ServiceDownSlow` stays in place without data.

## Consequences

- The last unmigrated LAN target of a security-critical device is gone; the Fritz!Box `192.168.178.1` ICMP probe, the Fritz!Box exporter and the QNAP node exporter (reachable through `qnap.4jp.de`) remain for ADR-0023.
- A device on HoME depends on the HoME Wi-Fi and OPNsense; the probe from k0s covers both.
- Related: [[ADR-0046 - Home Assistant owns the garage lock and MyPV alerts]], [[ADR-0023 - Retire the legacy dockerhost monitoring stack]], [[ADR-0048 - Name resolution for 4jp.de on OPNsense]].
