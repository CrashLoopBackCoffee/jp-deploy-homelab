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

- **Home automation alerts live in HA** as automations through Pushover (`alert:` would send its "done" message with the same emergency priority, which nags again):
  - `Alert bike storage unlocked`: a template `binary_sensor.bike_storage_unlocked` (device class `lock`, on = unlocked) over the enabled Shelly input 0 (`on` = locked, verified by toggling the lock on 2026-11-03); 10 min delay; Pushover **emergency** priority 2 (retry 60 s, expire 3600 s), as legacy and ADR-0032. A priority-0 "locked again" note follows after an alert-length unlock.
  - `Alert warm water outage`: template `binary_sensor.warm_water_low` (`sensor.mypv_water_temperature < 35`), 10 min delay, same priority. A state trigger on a template sensor survives an unknown entity at start-up, which a `numeric_state` trigger did not.
  - Warning (priority 0) when the Shelly i4 input or the MyPV temperature is `unavailable` for 15 min, closing the silent-failure gap.
- **LGTM only watches HA's availability:** the probe `http https://home-assistant.4jp.de/manifest.json` in the `Monitoring Targets` note (HA serves HTTPS on 443 only, 8123 is closed), covered by the critical `probe-failing` rule (emergency Pushover). Pods cannot resolve the name: public DNS answers `10.30.0.10`, but OPNsense answers NXDOMAIN for every `4jp.de` name without a dnsmasq record (verified 2026-11-03 on `10.10.0.1:53`, Unbound, and `:53053`, dnsmasq; `influx.4jp.de` and `tandoor.4jp.de`, which exist only in Cloudflare, fail the same way). Unbound's rebinding protection additionally drops private answers for other public names (`10-30-0-10.sslip.io`). So `observability` creates a dnsmasq host record. The cause is inferred from behaviour; Unbound's settings are not readable with the API user.
- **Dashboard:** `Warmwasser` is rebuilt in Grafana on the archive datasource of ADR-0047 (temperature, `power_act`). `mypv_surplus` is dropped: the AC•THOR reports `surplus: null`, so jexporter always exported 0. The history before the cutover stays in Mimir (backfilled `mypv_*`, 400 days retention). The `Solax` panel on `mypv_power_act` is decided with that dashboard's InfluxDB part.
- **jexporter is retired** after a parallel run: remove the two rules and the `jexporter` job from the legacy Prometheus, then stop the service on `wireguard` (the host stays). Other `jexporter` series (SwitchBot, coffee) already moved to HA (ADR-0023).

## Rejected

- Grafana alert rules on HA metrics: alert ownership split between two systems. The archive is for history, not alerting.
- Porting jexporter to k0s: LAN-only devices, a second poller beside HA, same silent-failure mode.
- Alerts in HA without an LGTM probe: an HA or VM outage would silence the lock alert.

## Migration

1. Verify the lock semantics with the user (`state: true` = locked).
2. `deploy-home-assistant` (done 2026-11-03, commits 8828a1f, db74767): enabled the Shelly input, template sensors, alert automations, offline warnings.
3. This repo (PR #122): HA record and probe target; apply `observability` after the merge.
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
- [[ADR-0047 - Thanos archive for Home Assistant sensor history]]
