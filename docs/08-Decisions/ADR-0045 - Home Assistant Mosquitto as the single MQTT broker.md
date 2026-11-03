---
tags:
  - homelab
  - adr
  - mqtt
  - influxdb
  - home-assistant
type: adr
status: accepted
date: 2026-11-03
created: 2026-11-03
updated: 2026-11-03
adr: 45
---

# ADR-0045 - Home Assistant Mosquitto as the single MQTT broker

## Status

Accepted on 2026-11-03.

## Context

Two Mosquitto 2.1 brokers carried disjoint traffic:

- **`dockerhost`** (`192.168.178.125:1883`, anonymous): the Tasmota smart meter (`tele/tasmota_629634/*`), the Shelly devices (`bkw/*`, `shellies/*`, `shellyplus*`, `zweiradgarage`) and `mqtt2influxdb`, which writes the InfluxDB database `vzlogger` (the `Power` dashboard).
- **Home Assistant's `core_mosquitto` add-on** (`192.168.178.122:1883`, `10.30.0.10:1883`): only Home Assistant core and Zigbee2MQTT.

Home Assistant reads every Shelly through its local Shelly integration, so the Shelly MQTT feed serves only InfluxDB. The Tasmota meter already exists in Home Assistant (`sensor.tasmota_mt691_*`) but stayed `unavailable` because the meter publishes to the other broker. `services/iot`, the donor broker for k0s, was never deployed. A pre-flight check of the `dockerhost` broker log (90 days) found only the devices, `mqtt2influxdb` and a read-only inventory client; no other subscriber.

## Decision

- **The Home Assistant add-on is the only broker.** Devices connect to `192.168.178.122:1883` with the shared login `devices`. One login for all devices is enough on a broker reachable only from the LAN and HoME. Telegraf connects to `10.30.0.10:1883` with its own login `telegraf`. Both logins live in 1Password (`MQTT devices`, `MQTT telegraf`) and in the add-on options (set through the Supervisor API). No anonymous access.
- **Telegraf replaces `mqtt2influxdb`.** A Deployment `mqtt-bridge` in the `influxdb` stack (`services/influxdb/influxdb/mqtt_bridge.py`) writes the same five measurements to `vzlogger`: one field `value`, no tags, the existing field types, second-precision timestamps. The bridge sits next to InfluxDB because it is an InfluxDB writer using the in-cluster URL.
- **The `dockerhost` broker and `mqtt2influxdb` are stopped**, not removed. Removing the containers, images and `/opt/mosquitto`, `/opt/mqtt2influxdb` needs a separate approval.
- **`services/iot` is removed.**
- **Future MQTT clients** (for example TeslaLogger) get their own login on the same broker.

## Rejected

- **Mosquitto on k0s:** Zigbee and home control would depend on k0s and OPNsense; devices are NATed as `10.10.1.17`; it needs a HoME→CoRE rule for 1883.
- **Porting `mqtt2influxdb`:** needs a self-built image.
- **Home Assistant's InfluxDB integration only:** different schema, breaks the `Power` series since 2018.

## Consequences

- Power data depends on the Home Assistant VM and the CoRE→HoME path (k0s node `10.10.8.1` → `10.30.0.10:1883`, open without a rule, verified from a Pod on 2026-11-03). A restart of the add-on or Home Assistant causes a gap of seconds (QoS 0, no persistent session).
- Home Assistant's Tasmota meter entities become live, and Home Assistant's InfluxDB integration writes them to `home_assistant` as well.
- The broker configuration lives in the add-on; the snapshot is in `deploy-home-assistant` (ADR 0010 there), the passwords in 1Password.
- No MQTT monitoring yet.
- Battery devices (Shelly H&T `HTone`) can only be repointed while awake.

## Related notes

- [[ADR-0043 - InfluxDB 1.x on k0s for power and Home Assistant history]]
- [[ADR-0023 - Retire the legacy dockerhost monitoring stack]]
