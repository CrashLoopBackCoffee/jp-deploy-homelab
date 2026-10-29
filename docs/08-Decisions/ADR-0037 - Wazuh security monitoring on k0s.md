---
tags: [homelab, adr, security, wazuh, observability]
type: adr
status: accepted
date: 2026-10-26
created: 2026-10-26
updated: 2026-10-29
adr: 37
---

# ADR-0037 - Wazuh security monitoring on k0s

## Status

Accepted on 2026-10-29 after the full Phase 2 live acceptance gate passed. Implementation refinements from the proposal: Wazuh 4.14.9's Filebeat client required `compatibility.override_main_response_version: true`; Pulumi TLS leaf keys are PKCS#8; the generated indexer admin credential was rotated after diagnostic exposure; recommended sizing was retained after the Phase 1 capacity gate passed; the agent endpoint is MetalLB `10.10.88.3`; security configuration, users, roles, templates, ISM policies and single-node replica settings are applied by the hashed Pulumi security Job; NetworkPolicies enforce ingress-only isolation while egress remains open.

## Context

**[Verified (repo)]** k0s currently has one controller/worker node, `k0s0`; Grafana, Loki, Mimir and Alloy already provide the primary observability platform. **[Verified (upstream)]** Wazuh 4.14.9 is stable; 5.0.0-rc1 is a breaking rewrite requiring a new deployment and migration. https://github.com/wazuh/wazuh/releases/tag/v4.14.9 ; https://github.com/wazuh/wazuh-kubernetes/blob/main/docs/ref/upgrade.md

**[Inference]** The goal is host software inventory and vulnerability management, with Grafana as the primary interface, while retaining Wazuh-specific operational workflows in its dashboard. This proposal does not deploy anything.

## Decision

1. **Placement:** deploy on k0s, not a Proxmox VM. Reuse Pulumi, Longhorn, ingress, TLS, MetalLB and Alloy. Accept shared failure domain and downtime; agents buffer events and nothing depends on Wazuh. Revisit if cluster-outage forensics becomes required.
2. **Deployment:** repository-native Pulumi Python adaptation of official `wazuh-kubernetes` v4.14.9 manifests, workspace `services/wazuh`, namespace `wazuh`. Reject upstream Kustomize as-is (demo credentials/certs, privileged sysctl, unpinned init, MicroK8s storage, public LBs, HA defaults) and unofficial community Helm charts.
3. **Topology:** one indexer, one standalone manager, one dashboard. HA is unjustified on a one-node cluster and for this non-critical use.
4. **Storage:** 50Gi indexer and 20Gi manager on Longhorn, one replica, nightly backup. Do not use PostgreSQL-reserved OpenEBS LVM or unbacked hostPath. Indexer restore may rebuild state and lose alert history; manager state, especially `client.keys`, is priority.
5. **Kernel:** ensure host `vm.max_map_count=262144` via Ansible when needed; no privileged init container. Apply namespace Pod Security `baseline`.
6. **PKI:** internal Pulumi TLS CA and cert-manager leaf certificates, PKCS#8 RSA keys, automated renewal; restart pods after renewal. Do not use manual upstream demo certificates. Export CA PEM for Grafana.
7. **Credentials:** Pulumi-generated passwords and bcrypt hashes for admin, dashboard, Grafana reader, metrics reader, API and enrollment. Remove demo users. Version security config in code and apply with `securityadmin.sh`; UI changes are overwritten.
8. **Exposure:** LAN-only dashboard through Traefik TLS re-encryption. Agents use a fixed, source-restricted MetalLB address for TCP 1514/1515. API and indexer remain ClusterIP.
9. **Grafana integration:** query OpenSearch directly with a read-only Grafana datasource; aggregate counts into Mimir; send selected events to Loki. Do not duplicate vulnerability state in Loki or deploy a second Alloy.
10. **Agents:** native packages installed by Ansible, no DaemonSet. Agent versions never exceed manager version.
11. **Container coverage:** add Trivy Operator for Kubernetes workload images, vulnerability scanning only, with results in Mimir. Do not feed duplicate results into Wazuh. Dockerhost image scanning is out of scope.
12. **Version:** target Wazuh 4.14.9; plan a separate 5.x migration. Keep schema-dependent integration in exporter modules and dashboard panels. **[User decision]**
13. **Alert severity:** every new Grafana alert rule based on Wazuh data starts at `severity=warning` and uses normal Pushover; after about two weeks, promote only with reviewed evidence, not elapsed time alone. **[User decision]**
14. **Operational purpose:** prioritize host software inventory and vulnerability reporting; detection only, no automated remediation or containment. The homelab operator owns manual triage. **[User decision]**
15. **Rollout and supported hosts:** enroll k0s0 as a stop/go pilot, then only explicitly inventoried/approved Debian-family hosts. Include Proxmox with partial CVE coverage documented. Include OPNsense event forwarding in v1 as a non-blocking, manual, tier-3 community integration; it provides no reliable FreeBSD CVE coverage. **[User decision]**
16. **Inventory and scope:** collect the planned OS/package, process, hardware and network inventory. Trivy covers k0s workload images; Dockerhost image scanning and QNAP agent/CVE coverage remain out of scope. **[User decision]**
17. **Finding model:** distinguish current vulnerability findings (current state) from vulnerability transition events (timestamped `Active`/`Solved` alerts) and CTI feed observations (remote catalog metadata, probe errors and periodic heartbeat). State is authoritative; event alerts are not a complete lifecycle ledger, and remote metadata/heartbeat do not prove local feed application. **[User decision; Verified (upstream)]** https://documentation.wazuh.com/4.14/user-manual/capabilities/vulnerability-detection/how-it-works.html
18. **Finding notifications:** notify on newly Active Critical findings, keyed by agent ID, CVE and package identity; group by agent over five minutes. Use Loki alert rules defined separately from the Mimir-only rule model. Keep resolved events as dashboard context. Parse source timestamps, falling back to arrival time if parsing fails. Loki delivery is best-effort; Wazuh alert indices remain the durable record. **[User decision]**
19. **CTI health:** Live 4.14.9 evidence showed `Feed update process completed.` only when new content was applied: with a 60-minute interval there was one occurrence in roughly eight hours (00:03:55 UTC, 2026-10-29). The two-hour no-completion alert is invalid and is replaced by explicit scanner/CTI probe error alerts plus an alert when the periodic CTI heartbeat is absent from Loki for 30 minutes; the latter also detects a dead manager log pipeline, not local feed staleness. A read-only `cti-freshness` sidecar polls the public Wazuh catalog endpoint `https://cti.wazuh.com/api/v1/catalog/contexts/vd_1.0.0/consumers/vd_4.8.0` every 10 minutes and logs `{"timestamp":"<UTC RFC3339Nano>","event":"cti_freshness","context":"vd_1.0.0","consumer":"vd_4.8.0","remote_offset":N,"remote_updated_at":"<UTC>"}` or a `cti_freshness_error` event with HTTP status. This shows public remote catalog offset/request health, not proof that local manager state applied it; local offset comparison remains a follow-up. It uses no manager API credential. **[Verified (live; ticket #97)]** https://github.com/wazuh/wazuh/blob/v4.14.9/src/wazuh_modules/vulnerability_scanner/src/databaseFeedManager/databaseFeedManager.hpp
20. **Network boundary:** initially allow agent traffic from `10.10.0.0/16` and the dockerhost `/32`, and leave pod egress open; tighten after observed flows and the approved host list. **[User decision]**
21. **Retention and recovery:** retain Wazuh alert indices for 60 days, do not store archive streams, and accept local QuObjects backups initially with restore tests; off-site backup is not a go-live gate. **[User decision]**
22. **Dashboard identity:** Authentik SAML is optional post-core work; retain local basic authentication as break-glass. **[User decision; Verified (upstream)]** https://documentation.wazuh.com/current/user-manual/user-administration/single-sign-on/authentik.html
23. **Alert notification:** warning-severity Grafana rules use normal Pushover, not emergency-priority paging. Wazuh detection-rule levels remain a separate scale. **[User decision]**
24. **Access risk:** accept the manager’s indexer-administrator trust and document the compromise blast radius. **[User decision]**
25. **Certificate rotation:** A daily baseline-PSA CronJob hashes served leaf Secrets and updates workload pod-template annotations on change, so consumers restart without an initial annotation-driven restart storm; RBAC is namespace-scoped and limited to required reads and workload patches.
26. **Security configuration after indexer restart:** An indexer-pod sidecar waits for HTTPS readiness, runs the existing idempotent securityadmin configuration once per pod start using read-only config/credential/certificate mounts, then sleeps. This repairs the security index after an empty-PVC rebuild without relying on Pulumi input changes.

## Consequences

**[Inference]** Wazuh availability is bounded by the single k0s node; planned requests total about 1.13 CPU and 5.2Gi memory with 70Gi storage, subject to the live capacity gate. CTI probe silence is detected after 30 minutes, and explicit scanner/probe errors are alerted; neither remote metadata nor heartbeat proves that feed content was applied locally. Event notifications may be missed during ingestion/pod outages, while Wazuh alert indices remain authoritative. The manager’s indexer-admin trust, enrollment MITM exposure, broad initial network policy and Pulumi-stored CA/secrets are accepted risks. Local QuObjects backups require restore tests; off-site backup remains a follow-up, not a go-live gate. Wazuh 5.x requires a separate migration.

## Alternatives considered

### k0s or Proxmox VM

**[Inference]** k0s reuses existing automation and services; VM placement adds a separate unmanaged lifecycle and is less integrated. Revisit for independent outage forensics.

### Pulumi, upstream Kustomize or community Helm

**[Verified (upstream)]** Official deployment is Kustomize and no official Helm chart exists: https://github.com/wazuh/wazuh-kubernetes/tree/v4.14.9. **[Inference]** Pulumi adaptation follows repository conventions and permits secure single-node configuration. Community Helm is unofficial and may lag.

### Longhorn or local storage

**[Verified (repo)]** Longhorn is backed up; PostgreSQL VG is reserved. **[Inference]** Longhorn is preferred over hostPath/local-path due to backup and lifecycle support.

### Single node or HA

**[Verified (repo)]** only one cluster node is joined. **[Inference]** single replicas fit the current topology and tolerated downtime; HA would add unavailability without independent nodes.

### Direct OpenSearch or copying to Loki

**[Inference]** Grafana queries OpenSearch for native fields and Loki receives only selected event logs. Copying vulnerability state duplicates storage and high-cardinality data.

### Native agents or DaemonSet

**[Inference]** native agents provide host package inventory and keep operating during kubelet failure. A DaemonSet would need privileged host mounts and does not naturally see host dpkg inventory.

### Wazuh alone or Wazuh plus Trivy

**[Inference]** Wazuh covers host OS packages; Trivy Operator covers workload images. Separate systems avoid duplicate vulnerability databases.

### Exporters

**[Verified (upstream)]** `json_exporter` supports POST bodies and JSONPath extraction; maintained Elasticsearch exporter is available. https://github.com/prometheus-community/json_exporter ; https://github.com/prometheus-community/elasticsearch_exporter. **[Inference]** Reject stale pyToshka Wazuh exporter; use these maintained components and Alloy's embedded exporter where suitable.

## Related notes

[[Wazuh Security Monitoring]], [[Wazuh Implementation Plan]], [[GLOSSARY]], [[ADR-0019 - LGTM observability stack on k0s]], [[ADR-0014 - Longhorn on a dedicated ext4 data disk]]
