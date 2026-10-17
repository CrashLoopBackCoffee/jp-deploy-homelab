---
tags:
  - homelab
  - adr
  - kubernetes
  - observability
type: adr
status: accepted
date: 2026-10-13
created: 2026-10-13
updated: 2026-10-13
adr: 19
---

# ADR-0019 - LGTM observability stack on k0s

## Status

Accepted on 2026-10-13 as the design for basic monitoring and verified the same day (see Verification).

## Context

The k0s cluster has no monitoring. Backups, WAL archiving, certificates, storage and node health are all unobserved, and the first scheduled backups ran without anyone watching them. The user wants "LGTM like the donors" (Loki, Grafana, Tempo, Mimir; the donor `mp-deploy-homelab/services/observability` deploys all but Tempo) with alerts delivered by Pushover. The donors' Mimir runs on the Mimir chart's bundled MinIO, which [[ADR-0015 - Remove MinIO and the s3 workspace]] rejected for this repository. The remote QNAP is offline, so the encrypted HBS 3 off-site test of [[ADR-0018 - PostgreSQL PITR and off-site recovery acceptance]] cannot run yet; the user deferred it and chose to continue with monitoring.

## Decision

- New workspace and Pulumi project `services/observability`, stack `prod`, namespace `observability`. It is separate from the platform add-ons in `services/kubernetes` so that preview and apply of cluster plumbing and of monitoring do not entangle. It reads the same kubeconfig item.
- Deploy **Loki** (single-binary, filesystem storage on a Longhorn PVC), **Mimir** (`mimir-distributed`, one replica per component, bundled MinIO disabled, ruler and Alertmanager disabled), **Grafana**, **Alloy**, **kube-state-metrics** and **prometheus-node-exporter**. Tempo is not deployed; Alloy's OTLP receiver is the place to add it later.
- Mimir stores blocks in a private QuObjects bucket `mimir-metrics` at `https://qnap.4jp.de:8443` with its own access key (`QuObjects Mimir Metrics` in the `Homelab` vault), consistent with [[ADR-0016 - QuObjects backup target and encrypted offsite copy]]. The NAS is a dependency of long-term metrics storage; ingesters keep recent data on their PVCs. The user must create the bucket (own storage space, scoped key); that step stays outside Pulumi.
- Grafana is exposed through Traefik at `g.4jp.de` using the wildcard certificate and a dnsmasq host record, as the n8n stack does. `grafana.4jp.de` is not used: it is a public Cloudflare record for the user's old Grafana instance (`192.168.178.125`). Its admin password is a Pulumi-generated secret.
- Alerting is Grafana-managed and provisioned from files, including the **Pushover contact point and notification policy** (the donors left contact points click-operated). The Pushover API token and user key come from a `Pushover Grafana` item in the `Homelab` vault and reach Grafana as environment variables, never in values or the repository.
- Initial alert rules cover what the cluster already depends on: scrape targets down, node CPU, memory and disk, PVC fullness, Longhorn volume and disk state, CloudNativePG continuous archiving and backup age, cert-manager certificate expiry, and crash-looping pods. Dashboards are provisioned from the repository.
- Metrics and logs retain 30 days.

## Consequences

- The Grafana, Loki and Mimir PVCs live on Longhorn and join its `default` recurring-job group, so they are backed up daily to QuObjects. That also gives the Longhorn scheduled backup its first real volumes to exercise. Whether metrics deserve that backup traffic can be revisited with a dedicated StorageClass or recurring-job group.
- Distributed Mimir is heavy for one node. Resource requests are lowered for a single node; revisit when nodes 2 and 3 join.
- Alerting cannot report its own failure. Grafana, Alloy or Mimir being down silences every alert until someone looks; a Pushover heartbeat or an external check is a later decision.
- QuObjects previously rejected boto3's optional checksum headers (`InvalidDigest`). Mimir uses a Go S3 client, so a write and read smoke test of the bucket is part of acceptance.
- Acceptance: preview shows only creations; all pods Ready; Mimir receives samples (`up` returns every target); Loki returns recent pod logs; Grafana loads through `https://g.4jp.de`; a test notification reaches the phone via Pushover.
- The off-site HBS 3 check of ADR-0018 remains unverified and outstanding. This ADR does not lift the rule that no application database migrates before it passes.

## Verification

Applied 2026-10-13 after a create-only preview of 21 resources; follow-up updates were each previewed. All pods Running, 29 scrape targets up, Loki and Mimir queryable through Grafana, a flushed Mimir block present in the `mimir-metrics` bucket (no checksum errors), 15 provisioned alert rules healthy against live series, and a Pushover test notification returned `success`. Findings that changed the design: Longhorn's chart NetworkPolicies blocked metric scraping, so an additive policy admits Alloy to the manager only; Longhorn 1.13's metrics differ from older docs (rules rewritten and every expression checked against live data); the Barman plugin leaves CloudNativePG's own backup metrics at 0, so backup freshness uses kube-state-metrics custom-resource metrics. Not yet exercised: the store-gateway read path for aged blocks, and the first scheduled Longhorn backup of these volumes (02:00 UTC). See `.okf/observability-stack.md`.

Update 2026-10-14: the first scheduled Longhorn backups ran at 02:00 UTC and completed for all five observability volumes; no alert fired. A restore from a scheduled backup passed on 2026-10-17 (a Paperless volume, `.okf/kubernetes-platform-stack.md`).

Update 2026-10-15: at the user's request the dashboard set grew from 2 to 9: Kubernetes workloads, Observability self-health and Logs explorer are generated in code; Node Exporter Full, CloudNativePG, Longhorn and Traefik are community dashboards vendored under `assets/grafana/dashboards/` and adapted when rendered. The donors' dashboards are specific to services JP does not run. Each was evaluated against live data before adoption; this also exposed a label bug in the kube-state-metrics scrape (see `.okf/observability-stack.md`).

## Alternatives considered

- kube-prometheus-stack: the standard Kubernetes choice with bundled rules, but the user asked for the donors' LGTM layout.
- Mimir on the chart's bundled MinIO: closest to the donors, rejected by ADR-0015.
- Prometheus instead of Mimir: much lighter; rejected by the user's choice of Mimir on QuObjects.

## Related notes

- [[ADR-0012 - Local DNS records through dnsmasq on OPNsense]]
- [[ADR-0014 - Longhorn on a dedicated ext4 data disk]]
- [[ADR-0016 - QuObjects backup target and encrypted offsite copy]]

## References

- [Grafana Mimir Helm chart](https://grafana.com/docs/mimir/latest/set-up/helm-chart/)
- [Grafana Loki Helm chart](https://grafana.com/docs/loki/latest/setup/install/helm/)
- [Grafana Alloy](https://grafana.com/docs/alloy/latest/)
- [Grafana alerting provisioning](https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/file-provisioning/)
