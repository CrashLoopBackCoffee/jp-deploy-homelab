---
tags:
  - homelab
  - adr
  - observability
  - mimir
  - ax51
type: adr
status: accepted
date: 2026-11-06
created: 2026-11-06
updated: 2026-11-06
adr: 58
---

# ADR-0058 - AX51 metrics into Mimir through a push-only receiver

## Status

Accepted on 2026-11-06 and applied the same day.

## Context

AX41 [ADR 0018](https://github.com/CrashLoopBackCoffee/AX41/blob/main/docs/adr/0018-crowdsec-metrics-to-homelab-via-alloy.md) sends CrowdSec metrics (`cs_*` from the engine, `fw_bouncer_*` from the firewall bouncer) from AX51 to the homelab with Alloy `prometheus.remote_write`. AX51 reaches the homelab only through its `ax51-wazuh` WireGuard tunnel and must not read Mimir. [[ADR-0055 - AX51 logs into Loki through a push-only receiver]] solved the same problem for logs.

## Decision

- Alloy gets `prometheus.receive_http` on TCP 9090, which serves only the remote-write path `/api/v1/metrics/write`. It forwards to the existing `prometheus.remote_write "mimir"`. Mimir's query API is never exposed to AX51 (`GET /api/v1/query` on the listener returns 404).
- The existing `alloy-push` Service (`10.10.88.4`, source range `10.60.0.2/32`) gets a second port `mimir-push` (9090). The address, source range and `AllowedIPs` on AX51 (`10.10.88.4/32`, ADR-0055) are unchanged, so AX51's WireGuard configuration needed no edit.
- A `prometheus.relabel` pins `host="ax51"` on everything that arrives, as `loki.relabel` does for logs.
- OPNsense rule `ax51 metrics push to Alloy (ADR-0058)` (uuid `a1e5c04e-1bb5-483d-8715-e3fd85d23ab8`, sequence 502, interface `wireguard`, TCP `10.60.0.2/32` to `10.10.88.4/32:9090`) created through the API and applied on 2026-11-06, next to the ADR-0055 rule 501 (all other fields identical).
- Config: `alloy.push.metrics-port: 9090` in `Pulumi.prod.yaml`.
- AX41: `alloy_metrics_push_url: http://10.10.88.4:9090/api/v1/metrics/write`; `ansible-playbook ansible/alloy.yml` rendered the scrape and `remote_write` blocks and restarted Alloy.
- Dashboard `docs/grafana/crowdsec-ax51.json` (uid `crowdsec-ax51`, 14 panels) was imported into `g.4jp.de` folder `Security` through the Grafana API with datasource `Mimir`. It is not provisioned from code, so edit it in the AX41 file and re-import with `overwrite`.

## Verification

- `pulumi preview` showed exactly 2 updates (Alloy Helm release, `alloy-push` Service); both applied. Alloy reloaded in place and logged `server listening ... http=[::]:9090`.
- From a pod: `POST /api/v1/metrics/write` without body answers 400 (reachable, rejects empty input); `GET /api/v1/query` answers 404.
- About 45 s after the AX51 restart, Mimir held 629 `crowdsec` and 62 `crowdsec-firewall-bouncer` series with `host="ax51"`, and `up{host="ax51"}` was 1 for both jobs.
- All 14 dashboard panel queries returned data on Mimir.
- Not tested: a push from a source outside `10.60.0.2/32` (the Service source range is the same mechanism as ADR-0055).

## Consequences

- Any process on AX51 can now write arbitrary series as `host="ax51"` into Mimir; the series budget (250,000, [[ADR-0041 - Mimir series limit raised to 250000]]) is the shared limit. CrowdSec adds about 700 series.
- Behavior after a long tunnel outage (retry from AX51's WAL, Mimir's acceptance window for old samples) was not tested.

## Rollback

Set `alloy_metrics_push_url: ""` in AX41 and re-run `alloy.yml`; remove the `mimir-push` port, the three Alloy blocks and `metrics-port`, apply; delete the OPNsense rule by uuid; delete the Grafana dashboard `crowdsec-ax51`.

## Related

- [[ADR-0055 - AX51 logs into Loki through a push-only receiver]]
- [[ADR-0042 - AX51 reaches Wazuh through its own WireGuard instance]]
- AX41 ADR 0018: [CrowdSec metrics to the homelab via Alloy](https://github.com/CrashLoopBackCoffee/AX41/blob/main/docs/adr/0018-crowdsec-metrics-to-homelab-via-alloy.md)
