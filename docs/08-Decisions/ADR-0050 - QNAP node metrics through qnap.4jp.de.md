---
tags:
  - homelab
  - adr
  - observability
  - qnap
type: adr
status: accepted
date: 2026-11-05
created: 2026-11-05
updated: 2026-11-05
adr: 50
---

# ADR-0050 - QNAP node metrics through qnap.4jp.de

## Status

Accepted on 2026-11-05.

## Context

The legacy Prometheus scraped the QNAP node exporter at `192.168.178.60:9100` (job `node-exporter`, instance `qnap`). The cluster cannot reach `192.168.178.0/24` (ADR-0023, probes timed out again on 2026-11-05), so the QNAP was counted as a blocker for the LAN-only remainder of the old stack.

Findings on 2026-11-05, from a pod on k0s:

- `qnap.4jp.de` resolves to `10.10.0.10` (the 10G NIC on CoRE, dnsmasq reservation `qnap`), and `:9100`, `:8443` and `:443` are open. Mimir, Longhorn and CNPG already reach the QNAP through this name.
- `http://qnap.4jp.de:9100/metrics` answers 200 (node exporter 1.5.0, QTS 5.10.60) with 3,018 `node_*` series. 23 of 44 filesystems are per-snapshot FUSE mounts under `/mnt/snapshot`; the only `ext4` mounts are the data volume (`/share/CACHEDEV1_DATA`, 18.7 TB, 60% used), the same volume again as an NFS bind (`/share/NFSv=4/paperless-consume`), `/mnt/pool1` (2.3 GB, empty) and `/mnt/ext` (436 MB firmware partition, 93% used).
- Mimir held 108,766 active series of its 150,000 limit (ADR-0026) before this change.
- The generic rules (`node-cpu-high`, `node-memory-high`, `node-filesystem-full`, `target-down`) select by `instance`, not by job, so a scrape with `instance="qnap"` is covered without new rules.

## Decision

- **Alloy scrapes `qnap.4jp.de:9100` every 30 s** as job `qnap-node`, instance `qnap` (the legacy instance name, so old queries and dashboards still match). The target is a constant in `alloy.py`, like the Home Assistant host; it is not secret.
- **The filesystem rule ignores `/mnt/ext`**, as the legacy rule did. Otherwise the QNAP would page about a firmware partition that is always above 90%.
- **The legacy `QNAPPowerOff` mute and inhibit logic is not carried over** (ADR-0023: the QNAP has no nightly shutdown).
- **No dashboard yet.** The panels for NAS capacity and load are a separate step; the series are queryable in Grafana Explore.
- After the series are verified in Mimir, the QNAP target `192.168.178.60:9100` is removed from the legacy `node-exporter` job.

## Rejected

- Routing or opening `192.168.178.0/24` for the QNAP: the CoRE address already works and keeps the legacy LAN exception from growing.
- Dropping the 23 snapshot filesystems at scrape time: about 200 series, not worth the relabel rule and the risk of hiding a real mount.

## Consequences

- About 3,100 more active series (to roughly 112,000 of 150,000).
- Long RAID scrubs push the QNAP CPU above 90% for hours (ADR-0023, 2026-10-22: 20:00 to 06:00 UTC); `node-cpu-high` is a warning at priority 0, so a Thursday-night notification is expected and not an incident.
- A change of the QNAP address needs only the dnsmasq record; the scrape follows the name.
- Related: [[ADR-0023 - Retire the legacy dockerhost monitoring stack]], [[ADR-0026 - Mimir series budget and API server buckets]], [[ADR-0049 - Home VLAN addressing and the Zweiradgarage lock on HoME]].
