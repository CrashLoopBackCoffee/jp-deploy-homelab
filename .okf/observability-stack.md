---
type: Service
title: Observability stack (Pulumi, prod)
description: LGTM monitoring on k0s - what runs, how it is reached, alert routing to Pushover, verification evidence, and the metric and provisioning pitfalls found while building it.
timestamp: 2026-10-13T00:00:00Z
tags: [homelab, kubernetes, observability, grafana, loki, mimir, alloy, alerting, pushover]
resource: https://app.pulumi.com/jaypee-solutions/observability/prod
---

# What it deploys

Stack `jaypee-solutions/observability/prod`, source `services/observability`, namespace `observability`, 21 resources at first apply plus a Longhorn NetworkPolicy. Design and alternatives are in ADR-0019. Components: Loki (single binary, 10 GiB Longhorn PVC), Mimir distributed on one node with blocks in the QuObjects bucket `mimir-metrics` (bundled MinIO, ruler and Alertmanager disabled), Grafana, Alloy (one Deployment), kube-state-metrics, node-exporter. All state volumes are Longhorn PVCs and therefore join the nightly `default` recurring backup group.

Grafana is at `https://g.4jp.de` (Traefik IngressRoute, wildcard certificate, dnsmasq host record `g` pointing at `10.10.88.1`). `grafana.4jp.de` is a public Cloudflare record for the user's old Grafana at `192.168.178.125`, which is why `g` is used. The admin password is a Pulumi-generated secret: `kubectl -n observability get secret grafana -o jsonpath='{.data.admin-password}' | base64 -d`. The workstation resolver uses `1.1.1.1`, which cannot resolve LAN records such as `g.4jp.de`; use the router resolver or `curl --resolve g.4jp.de:443:10.10.88.1`.

# Alerting

Alert rules, the Pushover contact point, the notification policy and both dashboards are provisioned from code (`alert_rules.py`, `grafana.py`, `dashboards.py`); nothing is click-operated. Pushover credentials come from the `Pushover Grafana` 1Password item (`username` is the user key, `password` the application token) into the Secret `grafana-secrets`; Grafana expands `$PUSHOVER_*` in the provisioning file. Provisioned text containing a literal `$` (alert templates) must use `$$`. Grafana reads alerting provisioning only at startup, so the Helm values carry a content-hash pod annotation; a rule change rolls the pod. File provisioning never deletes a rule whose entry vanished: list its uid in `REMOVED_RULE_UIDS` (written as `deleteRules`).

Test a receiver with `POST /apis/notifications.alerting.grafana.app/v1beta1/namespaces/default/receivers/<base64 name>/test` (the legacy `/api/alertmanager/.../receivers/test` returns 410). The body is `{"integration": {uid, type, version, settings}, "alert": {...}}` and, for provisioned receivers, `settings` must carry the secrets again; `secureFields` alone returns `user key not found`. The test on 2026-10-13 returned `success`.

Alerting cannot report its own failure: if Grafana, Alloy or Mimir is down, nothing pages.

# Verified (2026-10-13)

- All 16 pods Running; 29 scrape targets, none down, across apiserver, kubelet, cAdvisor, kube-state-metrics, node-exporter, CoreDNS, cert-manager, CloudNativePG, Traefik, MetalLB, Longhorn, Loki, Mimir, Grafana and Alloy.
- QuObjects write path: after `POST /ingester/flush`, a block (`index`, `chunks/000001`, `meta.json`) appeared under `blocks/anonymous/` in `mimir-metrics` with no `InvalidDigest`. Listing needs the `aws` CLI with `AWS_REQUEST_CHECKSUM_CALCULATION=when_required`; a `curl --aws-sigv4` probe returned 403 even for the known-good CNPG key. The store-gateway read path for data older than the ingester window has not been exercised.
- Loki returns pod logs; both datasources report healthy; 15 rules loaded and healthy; every rule expression returns live series; the Pushover test notification succeeded.

# Pitfalls found

- **Longhorn ships NetworkPolicies** (`longhorn-system`, chart 1.13) that admit only Longhorn pods to the manager, so Alloy, a probe pod and the API server proxy all got `connection refused` on port 9500. `longhorn_access.py` adds an additive policy letting only Alloy reach port 9500.
- **Longhorn 1.13 metric shapes differ from older docs.** `longhorn_volume_robustness` is a 0/1 series per `state` label (not a 0-3 enum); there is no `longhorn_backup_state`; backup freshness is `longhorn_volume_last_backup_at` (0 means never) and `longhorn_backup_target_status{condition="unavailable"}`. A rule written from older docs, `> bool 1`, could never fire and would have looked healthy. Always evaluate a new rule against live data.
- **The Barman plugin does not populate CloudNativePG's backup metrics** (`cnpg_collector_last_available_backup_timestamp` stays 0). Backup freshness comes from kube-state-metrics custom-resource metrics `cnpg_backup_stopped_at_seconds{phase}` over the `Backup` objects.
- **nginx gateways name their proxy port `http-metrics`** (Loki and Mimir), which the generic port-name scrape rule would hit and report as `up == 0`; the Alloy config drops containers named `gateway` or `nginx`.
- **The old `grafana/grafana` chart repository is deprecated**; use `grafana-community.github.io/helm-charts` (chart 13.x).
- `longhorn-volume-backup-stale` stays pending for 26 hours on a brand-new volume (its backup timestamp is 0 until the first nightly job). The first scheduled Longhorn backups with real volumes run at 02:00 UTC after the stack was applied; check `longhorn_volume_last_backup_at`.

# Operations

```sh
(cd services/observability && direnv exec ../.. pulumi preview --stack prod --non-interactive)
kubectl -n observability get pods
```

Related: [Kubernetes platform stack](./kubernetes-platform-stack.md), [PostgreSQL pilot recovery](./postgres-pilot-recovery.md), ADR-0019.
