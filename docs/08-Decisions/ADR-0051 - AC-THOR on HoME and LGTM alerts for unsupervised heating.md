---
tags:
  - homelab
  - adr
  - observability
  - home-assistant
  - network
type: adr
status: accepted
date: 2026-11-05
created: 2026-11-05
updated: 2026-11-05
adr: 51
---

# ADR-0051 - AC•THOR on HoME and LGTM alerts for unsupervised heating

## Status

Accepted on 2026-11-05. **Executed:** the dnsmasq reservation and the code. **Open:** the cable move (user), the Home Assistant URLs, the apply, the alert tests; steps below.

## Context

The my-PV AC•THOR (hot water heater, 3 kW, MAC `98:6d:35:c0:8b:ae`, firmware a0022702, control type `HTTP Control`) is steered by Home Assistant: `update_mypv_power` posts `control.html?power=<number.mypv_power_control>` every minute (ADR-0046). The user observed that the device **keeps the last value it was given** when the updates stop; my-PV's Documentation of Controls (EN241205) states no timeout. If Home Assistant stops while a high setpoint is active, the AC•THOR keeps heating at that power, at night too, and a Home Assistant automation cannot guard against Home Assistant's own outage. The user wants an LGTM-based alert.

Findings on 2026-11-05:

- LGTM already pages (critical, emergency Pushover) when the HA probe `https://home-assistant.4jp.de/manifest.json` fails for 10 minutes; `probe_success` was 99.9% over 7 days. That says HA is down, not what the heater does meanwhile.
- The AC•THOR sits on the legacy LAN (`192.168.178.123`, DHCP from the Fritz!Box, DNS `192.168.178.171`, wired) and k0s cannot reach that network (ADR-0023, ADR-0049).
- `data.jsn` has 126 keys; many are `null` (`surplus`, meters). A JSON exporter fails the whole probe on a `null` it is told to read, so only always-numeric fields are exported: `power_act`, `load_nom`, `temp1` (0.1 °C), `boostactive`, `error_state`. `uptime` is left out: it did not change over 20 minutes, so its unit is unknown. The exporter config was tested with the `json-exporter` v0.8.0 image against a captured `data.jsn` of the real device (HTTP 200, the five metrics, `power_act` 0, `temp1` 470).
- The device's `setup.jsn` holds `iip` `192.168.178.122` (the "Ctrl IP", the signal source shown on the display). In http control that is HA's legacy address; whether it matters for `control.html` is not documented, so it is set to HA's HoME address `10.30.0.10` during the move as a precaution.

## Decision

- **The AC•THOR moves to HoME**, like the Zweiradgarage i4 (ADR-0049): the user moves its cable to a VLAN 30 (HoME) untagged port; OPNsense dnsmasq has the reservation `acthor` = `10.30.0.11` (basement, the second device of place 0 after Home Assistant `10.30.0.10`; created 2026-11-05, uuid `2a25f59e-86fc-4d75-a86b-9774781fc0fa`). Home Assistant (`rest` sensors and `rest_command`) and the AC•THOR "Ctrl IP" follow.
- **Alloy reads the device directly** through a JSON exporter Deployment `acthor-exporter` (`prometheuscommunity/json-exporter`, module `acthor`) every 30 s as job `acthor`, instance `acthor`: `acthor_power_act_watts`, `acthor_load_nom_watts`, `acthor_temp1_decicelsius`, `acthor_boost_active`, `acthor_error_state`. The generic `target-down` rule (warning) covers an unreachable device.
- **Two Grafana rules on the Mimir datasource:**
  - `acthor-heating-while-ha-down` (**critical**, emergency Pushover, 10 min): `power_act` above 100 W while the HA probe fails. Listed in ADR-0032.
  - `acthor-heating-at-night` (warning, 30 min): `power_act` above 100 W between 20:00 and 03:00 UTC (always dark in Germany) while the boost backup is off. It also catches a bad setpoint from a running Home Assistant. The boost backup (heating from the grid on purpose, `boostactive`) is excluded, so a deliberate night boost does not alert.
- **No guard in Home Assistant:** an HA automation cannot cover an HA outage. Lowering the setpoint during the outage is a manual step on the device (the critical alert says so).

## Rejected

- An OPNsense rule from `k0s0` to `192.168.178.123`: the Fritz!Box behind OPNsense NATs the legacy LAN (ADR-0008), so CoRE to that network may not route at all, and it keeps a LAN exception for good.
- A Home Assistant watchdog that zeroes the setpoint: useless exactly when Home Assistant is down.
- A solar-production condition for the night rule: the PV series live in the Thanos archive, a different datasource than the rules use, and stop when HA stops. A fixed dark window is simple and independent.
- Scraping all 126 keys: nulls fail the probe, and nothing else is used.

## Migration

1. **Done 2026-11-05:** dnsmasq reservation `acthor` = `10.30.0.11`; exporter, Alloy scrape, config and both rules written (not applied).
2. The user moves the AC•THOR LAN cable to a HoME port. Check: the lease for `98:6d:35:c0:8b:ae` shows `10.30.0.11`, `http://10.30.0.11/data.jsn` answers, `control.html` still accepts a setpoint.
3. In `deploy-home-assistant`, in the same minute, change the three URLs to `10.30.0.11` (the `rest` resource and `rest_command`), deploy, verify `sensor.mypv_*` and the setpoint; the 15-minute `unavailable` warning bridges the gap. Set the device's Ctrl IP to `10.30.0.10`.
4. Preview and apply `observability` from `main`; verify `up{job="acthor"}` is 1 and the series exist; the new rules are `ok`/`inactive`.
5. Test: evaluate both expressions against live data (they must be 0 while HA is up and the heater is idle); a real test of the critical rule needs HA down and the heater on and is not done on purpose.

## Consequences

- AC•THOR data now exists in Mimir independently of Home Assistant (about 5 series every 30 s).
- The critical rule can only fire while HA is down and the heater is above 100 W, for example a sunny day with HA offline.
- If the HoME port or the reservation is wrong, `target-down` warns and the critical rule stays silent (no data), so the move must be verified before the apply.
- Related: [[ADR-0046 - Home Assistant owns the garage lock and MyPV alerts]], [[ADR-0049 - Home VLAN addressing and the Zweiradgarage lock on HoME]], [[ADR-0032 - Emergency Pushover priority for critical alerts]], [[ADR-0023 - Retire the legacy dockerhost monitoring stack]].
