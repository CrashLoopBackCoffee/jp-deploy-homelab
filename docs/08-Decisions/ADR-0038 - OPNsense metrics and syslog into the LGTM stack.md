---
tags:
  - homelab
  - adr
  - opnsense
  - observability
  - kubernetes
type: adr
status: accepted
date: 2026-10-27
created: 2026-10-27
updated: 2026-10-27
adr: 38
---

# ADR-0038 - OPNsense metrics and syslog into the LGTM stack

## Status

Accepted on 2026-10-27.

## Context

OPNsense (`router.4jp.de`, CoRE interface `10.10.0.1`) is the edge firewall and the only uplink, and it is not yet in the LGTM stack ([[ADR-0019 - LGTM observability stack on k0s]]). The user wants its metrics, all its logs including the firewall log (`filterlog`), dashboards, and a focused set of alerts. The k0s node (`10.10.8.1`) is in the same `10.10.0.0/16` as the firewall, and pods resolve `router.4jp.de` through CoreDNS to the OPNsense resolver.

## Decision

- **Two metric sources, both scraped by Alloy:**
  - The `os-node_exporter` plugin on the firewall (host metrics with FreeBSD names), bound to the CoRE interface `10.10.0.1:9100`. Job `opnsense-node`, every 30 s.
  - The AthennaMind `opnsense-exporter` (`ghcr.io/athennamind/opnsense-exporter`) as a Deployment in the `observability` namespace, reading the OPNsense API over HTTPS with the read-only user `metrics-exporter` (least privilege, listed in [[OPNsense]]). Job `opnsense`, every 60 s. The collectors for services this firewall does not run (Unbound statistics, Kea, CARP, OpenVPN, IPsec) are disabled. The key and secret are in 1Password item `OPNsense Metrics Exporter` (same convention as item `OPNsense`, [[ADR-0012 - Local DNS records through dnsmasq on OPNsense]]); the pod template carries a checksum of them so a rotated key rolls the pod.
- **Logs:** OPNsense sends all applications at `info` and above over RFC 5424 and TCP to a **dedicated port 1516** on `alloy-syslog` (`10.10.88.2`, [[ADR-0024 - QNAP syslog into Loki]]). A dedicated port gives its lines their own labels (`job="opnsense-syslog"`, `source="opnsense"`). `10.10.0.1/32` joins `alloy.syslog.allowed-sources`; it can then also reach ports 1514 and 1515, which is accepted.
- **`filterlog` parsing in Alloy:** the CSV line yields the labels `interface`, `action` and `direction`; rule id, protocol, source and destination address and ports are **structured metadata**, so they can be filtered and grouped without creating streams. IPv4 and IPv6 are parsed separately.
- **Generated dashboards** `OPNsense` and `OPNsense logs` instead of the community dashboard 21113.
- **Three warning alert rules:** `opnsense-api-down`, `opnsense-gateway-unhealthy`, `opnsense-pf-states-high`.

## Consequences

- The firewall needs manual setup (plugin, API user, firewall rule from the k0s node to ports 9100 and 443, remote logging); the steps are in [[OPNsense]].
- A firewall that is down cannot page while it is the only uplink; the existing `Scrape target down` rule covers both scrape jobs.
- `filterlog` at `info` is high volume; watch the Loki volume (`kubelet_volume_stats_used_bytes`, 10 GiB) and Mimir's series budget ([[ADR-0026 - Mimir series budget and API server buckets]]) after the first weeks.
- Syslog stays unencrypted and unauthenticated; the source range is the only protection (see ADR-0024).
- The exporter pins its image tag in the stack config and is updated by Renovate.
- **Gateway monitoring must be on.** The exporter emits `opnsense_gateways_{status,rtt,rttd,loss}` only for gateways with monitoring enabled. It was off on all four gateways; it is now on for `WAN_GW` with monitor IP `9.9.9.9`. The default monitor IP (the PPPoE peer `62.156.244.4`) does not answer ICMP and reported 100% loss. The other gateways stay unmonitored.
- **Verified 2026-10-27:** both scrape jobs `up`; `opnsense_up` 1; 0 exporter endpoint errors; 466 `opnsense-node` and about 505 `opnsense` series (Mimir at 100,666 of 150,000); no discarded samples. Synthetic IPv4 and IPv6 `filterlog` lines were parsed into the labels and structured metadata above, and real OPNsense lines then arrived from `10.10.0.1` over TCP port 1516 (host `router.4jp.de`, interfaces such as `vlan0.30`). Every dashboard panel returned data except the log panel `Errors and warnings by app` (no warnings logged in the first hour). The three rules are `ok` and `inactive`.

## Alternatives considered

- **SNMP (bsnmpd) or `os-telegraf`:** neither fits Prometheus-native pull scraping as well as the two exporters.
- **Community dashboard 21113:** one revision from 2024, covers only status, gateways, interfaces and ARP, and its datasource input is not matched by the dashboard adaptation code.
- **Reusing port 1514:** the lines would be labelled `qnap-syslog`.
- **UDP:** loses messages; TCP is chosen, UDP stays available on the same port.
- **Running the API exporter as an OPNsense plugin:** keeps the firewall lean and the exporter in the same deployment pipeline as the rest.

## Related notes

- [[ADR-0019 - LGTM observability stack on k0s]]
- [[ADR-0024 - QNAP syslog into Loki]]
- [[OPNsense]]
