---
tags:
  - homelab
  - adr
  - observability
  - loki
  - ax51
type: adr
status: accepted
date: 2026-11-05
created: 2026-11-05
updated: 2026-11-05
adr: 55
---

# ADR-0055 - AX51 logs into Loki through a push-only receiver

## Status

Accepted on 2026-11-05.

## Context

AX51's logs are needed in the homelab Loki stack. AX51 reaches only `10.10.88.4:3100` through its dedicated `ax51-wazuh` WireGuard tunnel; the existing Wazuh route remains `10.10.88.3`. Exposing Loki's read API to AX51 is neither needed nor permitted. Alloy therefore provides a dedicated push-only receiver, restricted by the LoadBalancer source range to the AX51 tunnel peer (`10.60.0.2/32`).

Log volume is retained under a differentiated policy. The privacy notices reviewed for kinderreich-augsburg.de, sweetvisage.de and tsv-blaichach.de state that logs are deleted after at most seven days; other checked notices gave no retention period, and hoegerl.mobi and turngau-allgaeu.com have no privacy page.

## Decision

- Expose Alloy's Loki push endpoint at `10.10.88.4:3100` using a dedicated LoadBalancer Service and source range `10.60.0.2/32`. Do not expose Loki's read API.
- Give pushed records the authoritative label `host="ax51"` (overwriting any supplied value).
- Collect three source classes on AX51: system journal, Docker container logs, and access logs. Access logs are labeled `log_type="access"`.
- Retain `{log_type="access"}` for 168 hours (7 days) using Loki `retention_stream`; retain all other logs for 30 days.
- Keep full client IPs in access records; retention is the privacy control.
- Cross-reference AX41 [ADR 0016](https://github.com/CrashLoopBackCoffee/AX41/blob/main/docs/adr/0016-ax51-logs-to-homelab-loki-with-alloy.md).

## Implementation record

- OPNsense rule `ax51 log push to Alloy (ADR-0055)` (uuid `6785a16f-fea4-4433-8ea4-69ccf7fdca9c`, sequence 501, interface `wireguard`, TCP `10.60.0.2/32` to `10.10.88.4/32:3100`) created through the API on 2026-11-05, next to the ADR-0042 rule.
- AX51 `/etc/wireguard/ax51-wazuh.conf` `AllowedIPs` extended by `10.10.88.4/32` on 2026-11-05 (backup `ax51-wazuh.conf.pre-loki-20261105` on the host); `wg-quick@ax51-wazuh` is now active under systemd.
- Timestamps: the receiver keeps the sender's timestamps (`use_incoming_timestamp`) so entries delayed by a tunnel outage keep their original time.

## Rollback

Remove the `alloy-push` Service and receiver configuration, restore the previous Loki chart values without `retention_stream`, and remove the AX51 route (restore `ax51-wazuh.conf.pre-loki-20261105`, restart `wg-quick@ax51-wazuh`) and delete the OPNsense rule by its description. The existing Alloy syslog Service and Loki data remain untouched.

## Related

- [[ADR-0042 - AX51 reaches Wazuh through its own WireGuard instance]]
- [[ADR-0019 - LGTM observability stack on k0s]]
- AX41 ADR 0016: [AX51 logs to homelab Loki with Alloy](https://github.com/CrashLoopBackCoffee/AX41/blob/main/docs/adr/0016-ax51-logs-to-homelab-loki-with-alloy.md)
