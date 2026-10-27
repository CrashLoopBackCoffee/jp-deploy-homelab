---
tags:
  - homelab
  - service
  - opnsense
type: service
status: active
created: 2026-03-20
updated: 2026-10-27
---

# OPNsense

## Purpose

Edge firewall, router, and likely the main network service integration point.

## Current role

- Routing and policy enforcement
- DHCP/DNS integration decisions
- WireGuard endpoint hosting

## Relevant topics observed

- Migration away from deprecated ISC DHCP
- Decision pressure between Kea and dnsmasq
- Interaction with Unbound and AdGuard
- WireGuard troubleshooting for roaming clients

## Known issues

- WireGuard floating clients experienced handshake completion failures.
- DHCP/DNS architecture is still being refined.

## Related notes

- [[dnsmasq]]
- [[Unbound]]
- [[AdGuard]]
- [[WireGuard]]
- [[ADR-0001 - Use dnsmasq instead of Kea on OPNsense]]

## Observability

Decision: [[ADR-0038 - OPNsense metrics and syslog into the LGTM stack]]. Metrics: Mimir jobs `opnsense` (API exporter in k8s) and `opnsense-node` (plugin). Logs: Loki `{job="opnsense-syslog"}`. Dashboards `OPNsense` and `OPNsense logs` in Grafana.

Manual setup on the firewall:

1. **Plugin:** System, Firmware, Plugins: install `os-node_exporter`. Enabled, listen address `10.10.0.1`, port `9100`. Collectors on: `cpu, exec, filesystem, loadavg, meminfo, netdev, time, devstat`; off: `interrupts, ntp`; `zfs` only if the install uses ZFS.
2. **API user:** System, Access, Users: `metrics-exporter`, scrambled password, no shell. Effective privileges exactly: `Diagnostics: ARP Table`, `Diagnostics: Firewall statistics`, `Diagnostics: Netstat`, `Reporting: Traffic`, `Status: Services`, `System: Firmware`, `System: Gateways`, `System: Settings: Cron`, `System: Status`, `VPN: WireGuard`, `Lobby: Dashboard`. Create an API key and store it in 1Password, vault Homelab, Login `OPNsense Metrics Exporter`: `username` = key, `password` = secret.
3. **Firewall rule:** alias `k0s_nodes` = `10.10.8.1`; on the CoRE interface pass TCP from `k0s_nodes` to `This Firewall`, ports `9100` and `443`, description `k0s scrapes OPNsense (ADR-0038)`.
4. **Remote logging** (after the receiver exists): System, Settings, Logging, Remote, Add. Enabled, transport `TCP(4)`, applications empty (all), levels `info` to `emerg` (no debug), facilities empty, hostname `10.10.88.2` (an IP, so syslog-ng does not depend on DNS at boot), port `1516`, `rfc5424` checked, description `Loki via Alloy on k0s (ADR-0038)`.
5. **Gateway monitoring:** System, Gateways, Configuration, `WAN_GW`: monitoring enabled (not disabled) with monitor IP `9.9.9.9`. The PPPoE peer address does not answer ICMP; without monitoring the exporter emits no gateway metrics and the gateway alert cannot fire.

If syslog arrives from another address than `10.10.0.1`, widen `alloy.syslog.allowed-sources` in the observability stack config. If TCP delivery fails, switch the destination to `UDP(4)`; the listener exists.
