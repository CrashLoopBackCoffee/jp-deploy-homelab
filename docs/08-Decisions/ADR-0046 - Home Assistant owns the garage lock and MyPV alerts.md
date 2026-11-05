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

Accepted on 2026-11-03. Migration done on 2026-11-05 (step 5 on 2026-11-05, see below); the AC•THOR failure behaviour stays an open question.

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
- **Dashboards (done 2026-11-03):** `Warmwasser` (temperature and `power_act`, timeseries and gauges) and `Solax` are rewritten for the Home Assistant data and provisioned in the `Home & Energy` folder of the new Grafana (uids kept). They read `InfluxDB home_assistant` for the current schema (measurement per unit, tag `entity_id`, since 2026-03-26) and, for `Solax`, the old measurements `sensor.<entity>` (2023-10-04 to 2026-03-26) in the same query, so one panel spans both; `bkw_current_power` and `meter1` stay on `vzlogger`. `Warmwasser` starts with the Home Assistant sensors: Mimir has no `mypv_*` series (the legacy Prometheus backfill, ADR-0023 stage 2, has not run), so the legacy history is only in the legacy Prometheus until that backfill. `mypv_surplus` is dropped: the AC•THOR reports `surplus: null`, so jexporter always exported 0. Once ADR-0047 is built, the queries move to the archive datasource.
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
5. **Done 2026-11-05** (user: jexporter is replaced by other solutions; the service on `wireguard` had been stopped by the user since 2026-11-03 15:38Z): the legacy rules `ZweiradGarage` and `WarmWaterOutage` and the `jexporter` job were removed from the Ansible templates and from `/opt/monitoring/config` on `dockerhost` (backups `*.pre-jexporter-removal`, `promtool` valid, 16 rules, `SIGHUP`, reload ok). Replacements: the lock and hot-water alerts are Home Assistant automations (ADR-0046), the i4 itself is probed from k0s (ADR-0049), the only `mypv_*` series any dashboard or rule used (`mypv_temp1`, `mypv_power_act`; `mypv_surplus` was always 0) map to `sensor.mypv_water_temperature` and `sensor.mypv_power_act` in the archive, and `Warmwasser` was rebuilt on them. The other 100 or so `mypv_*` series (meters, fan, error state, boost flags) had no consumer and are not replaced; add Home Assistant `rest` sensors and archive them if one is wanted.

## Consequences

- Lock and hot-water alerts depend on HA and the Shelly integration; HA unavailability pages through LGTM instead.
- Open: what the AC•THOR does when `control.html?power=` updates stop (HA down). The my-PV "Documentation of Controls" (EN241205) describes the http control (`power`, `pid_power`, `boost`) but states no timeout or fallback, so it stays unverified; the water still reached about 48.6 °C a day without surplus on 2026-11-03 to 11-05.
- Retiring jexporter removed the last LAN consumer of the legacy Prometheus besides the dockerhost exporters; the `Target unreachable` alert for `192.168.178.171:9303` that fired since 2026-11-03 is gone.

## Related notes

- [[ADR-0023 - Retire the legacy dockerhost monitoring stack]]
- [[ADR-0032 - Emergency Pushover priority for critical alerts]]
- [[ADR-0045 - Home Assistant Mosquitto as the single MQTT broker]]
- [[ADR-0047 - Thanos archive for Home Assistant sensor history]]
