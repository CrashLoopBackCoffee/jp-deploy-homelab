---
tags:
  - homelab
  - adr
  - home-assistant
  - observability
  - migration
type: adr
status: accepted
date: 2026-11-03
created: 2026-11-03
updated: 2026-11-03
adr: 46
---

# ADR-0046 - Home Assistant owns the garage lock and MyPV alerts

## Status

Accepted on 2026-11-03. Migration not started; steps below.

## Context

`jexporter` (a small Prometheus exporter on the host `wireguard`, `192.168.178.171:9303`) polls two devices over HTTP and feeds the legacy Prometheus on `dockerhost`: the Shelly Plus i4 `zweiradgarage` (`Input.GetStatus?id=0` → `zweiradgarage_locked`) and the my-PV AC•THOR (`data.jsn` → about 100 `mypv_*` series). Only two series have an alert, both defined only on the legacy stack (ADR-0023): `ZweiradGarage` (`zweiradgarage_locked < 1` for 10 min, page) and `WarmWaterOutage` (`mypv_temp1 < 35` for 10 min, page). The dashboard `Warmwasser` uses `mypv_temp1`, `mypv_power_act`, `mypv_surplus`; `Solax` has one `mypv_power_act` panel.

Findings on 2026-11-03:

- Home Assistant already owns the MyPV data and control: `rest` sensors (`sensor.mypv_water_temperature`, `_load_nom`, `_power_act`, `_next_legionella_boost`, every 10 s), the setpoint (`number.mypv_power_control`, `rest_command.update_mypv_power`, automation every minute) and a Lovelace view. HA writes them to InfluxDB `home_assistant`.
- The garage lock input is not usable in HA: `binary_sensor.zweiradgarage_input` (Input 0, type `switch`, not inverted) is disabled by the Shelly integration.
- jexporter fails the whole scrape when either device is unreachable, so the series vanishes and neither alert can fire.
- k0s cannot reach `192.168.178.0/24`, so LGTM could never scrape jexporter; it ends with the legacy Prometheus.
- HA has the Pushover integration and four `mobile_app` notify targets; the `Monitoring Targets` probe list has no entry for HA.

## Decision

- **Home automation alerts live in HA.** `alert:` entries (native repeat and acknowledge) notify through Pushover:
  - `zweiradgarage_unlocked`: a template `binary_sensor` with device class `lock` (on = unlocked) on the enabled input; 10 min delay; Pushover **emergency** priority 2 (retry 60 s, expire 3600 s), repeating until acknowledged or relocked, as legacy and ADR-0032.
  - `warm_water_outage`: `sensor.mypv_water_temperature < 35` for 10 min, same priority.
  - Warning (priority 0) when the Shelly i4 or the MyPV sensors are `unavailable` for 15 min, closing the silent-failure gap.
- **LGTM only watches HA's availability:** a probe of `http://10.30.0.10:8123` in the `Monitoring Targets` note, covered by the critical `probe-failing` rule (emergency Pushover). No HA metrics go into Mimir (no Prometheus integration).
- **Dashboard:** `Warmwasser` is rebuilt in Grafana on the `InfluxDB home_assistant` datasource. The missing `mypv_surplus` becomes a new HA `rest` sensor. The history before the cutover stays in Mimir (backfilled `mypv_*`, 400 days retention). The `Solax` panel on `mypv_power_act` is decided with that dashboard's InfluxDB part.
- **jexporter is retired** after a parallel run: remove the two rules and the `jexporter` job from the legacy Prometheus, then stop the service on `wireguard` (the host stays). Other `jexporter` series (SwitchBot, coffee) already moved to HA (ADR-0023).

## Rejected

- HA → Prometheus integration → Grafana rules: thousands of series against the Mimir budget (ADR-0026), and alert ownership split between two systems.
- Porting jexporter to k0s: LAN-only devices, a second poller beside HA, same silent-failure mode.
- Alerts in HA without an LGTM probe: an HA or VM outage would silence the lock alert.

## Migration

1. Verify the lock semantics with the user (`state: true` = locked).
2. `deploy-home-assistant`: enable the Shelly input, add the template sensor, `surplus` sensor, the alerts and the offline warnings; `just deploy`.
3. This repo: add the HA probe to the `Monitoring Targets` note; preview and apply `observability`.
4. Parallel run with the legacy alerts; test unlock for 10 min (both Pushover messages) and an offline i4.
5. After the user accepts: remove the legacy rules and job, stop jexporter; rebuild `Warmwasser`; update ADR-0023 and the OKF notes.

## Consequences

- Lock and hot-water alerts depend on HA and the Shelly integration; HA unavailability pages through LGTM instead.
- Open: the AC•THOR's behaviour when `control.html?power=` updates stop (HA down) is unverified; check the my-PV documentation before step 5.
- Retiring jexporter removes the last LAN consumer of the legacy Prometheus besides dockerhost, node and QNAP exporters.

## Related notes

- [[ADR-0023 - Retire the legacy dockerhost monitoring stack]]
- [[ADR-0032 - Emergency Pushover priority for critical alerts]]
- [[ADR-0045 - Home Assistant Mosquitto as the single MQTT broker]]
