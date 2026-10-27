---
type: Architecture
title: Wazuh security monitoring (planned)
description: Proposed Wazuh 4.14.9 architecture, upstream pitfalls, LGTM integration contracts, and phased implementation plan.
timestamp: 2026-10-26T00:00:00Z
tags: [homelab, security, wazuh, vulnerability-management, kubernetes, observability]
resource: https://github.com/wazuh/wazuh-kubernetes/tree/v4.14.9
---

# Wazuh security monitoring (planned)

**[User decision]** Planned single-node Wazuh deployment on k0s; not deployed. Host software inventory/vulnerability reporting is primary, with manual operator triage and no automated remediation. Architecture, implementation, decisions and terms: [[Wazuh Security Monitoring]], [[Wazuh Implementation Plan]], [[ADR-0037 - Wazuh security monitoring on k0s]], [[GLOSSARY]].

## Upstream 4.14.9 facts and pitfalls

- **[Verified (upstream)]** Official Kubernetes deployment uses Kustomize, with 3 indexers, manager master/workers and dashboard. Local-environment manifests include demo credentials/certificates, unpinned BusyBox, privileged `vm.max_map_count` init, MicroK8s storage class, and public load balancers. Adapt rather than apply as-is. https://github.com/wazuh/wazuh-kubernetes/tree/v4.14.9
- **[Verified (upstream)]** Security configuration changes require `securityadmin.sh`; default-init security files apply only at first start. https://documentation.wazuh.com/current/deployment-options/docker/wazuh-container.html
- **[Inference]** OpenSearch client certificates should use PKCS#8 keys and explicit DN matching.
- **[Verified (upstream)]** State indices include `wazuh-states-vulnerabilities-*` and inventory indices; vulnerability documents expose `vulnerability.detected_at`, severity, score and scanner condition. State indices have no `@timestamp` and no explicit fixed-version field. https://documentation.wazuh.com/current/user-manual/wazuh-indexer/wazuh-indexer-indices.html
- **[Verified (upstream)]** Wazuh 5.0 is a breaking migration with a new agent protocol/schema and migration tooling, not an in-place upgrade. https://github.com/wazuh/wazuh-kubernetes/blob/main/docs/ref/upgrade.md
- **[Verified (upstream)]** OPNsense plugin supports agent/event forwarding only; FreeBSD is not a vulnerability-detection vendor feed. QNAP has no Wazuh agent in this plan. https://docs.opnsense.org/manual/wazuh-agent.html ; https://documentation.wazuh.com/current/user-manual/capabilities/vulnerability-detection/compatibility-matrix.html
- **[Verified (upstream)]** Trivy v0.69.4 was affected by a supply-chain compromise; planned chart bundles 0.75.0. https://github.com/advisories/GHSA-69fq-xp46-6x23
- **[Verified (upstream)]** pyToshka Wazuh Prometheus exporter is stale (last push 2025-07-04; no releases); reject it. `json_exporter` supports POST bodies, HTTP client auth/TLS and JSONPath. https://github.com/pyToshka/wazuh-prometheus-exporter ; https://github.com/prometheus-community/json_exporter

## Integration decision

**[User decision]** Grafana queries OpenSearch for current findings and Mimir for aggregate trends/health. Loki receives selected vulnerability transition events and manager feed logs; Wazuh alert indices remain authoritative. New Active Critical events are grouped per agent for five minutes and delivered through a separate Loki Grafana alert rule to normal Pushover. Delivery is best-effort; state and event history are distinct. Trivy covers k0s workload images only; Wazuh dashboard remains necessary for agent management, IT Hygiene, SCA, FIM, rule/decoder testing and API console. All new Grafana alert rules based on Wazuh data start at warning; promotion requires reviewed evidence after about two weeks. Wazuh detection-rule levels are a separate scale.

## Vulnerability events and CTI health

- **[Verified (upstream)]** Wazuh 4.14.9 package-delta alerts use `data.vulnerability.status` (`Active`/`Solved`), CVE and package identity, with agent identity and top-level alert `timestamp`; rules 23502–23506 cover solved and active severities. https://github.com/wazuh/wazuh/blob/v4.14.9/ruleset/rules/0520-vulnerability-detector_rules.xml ; https://github.com/wazuh/wazuh/blob/v4.14.9/src/wazuh_modules/vulnerability_scanner/src/scanOrchestrator/eventPackageAlertDetailsBuilder.hpp
- **[Verified (upstream)]** Events are not a complete lifecycle ledger: initial inventory/sync and some rescans do not emit transitions; hotfix resolution may identify “one or many packages.” Treat the vulnerability state index as authoritative and events as best-effort notifications. https://documentation.wazuh.com/4.14/user-manual/capabilities/vulnerability-detection/how-it-works.html
- **[Verified (upstream)]** The manager writes plain-text logs to `/var/ossec/logs/ossec.log`; scanner logs include `Feed update process completed.` and `Error updating feed: ...`. **[Inference]** A read-only sidecar can tail this file via the manager `logs` volume and send lines to Loki. Warn on explicit errors or no success observed for two hours; absence alone does not prove failure. https://documentation.wazuh.com/4.14/user-manual/reference/ossec-conf/logging.html ; https://github.com/wazuh/wazuh/blob/v4.14.9/src/wazuh_modules/vulnerability_scanner/src/databaseFeedManager/databaseFeedManager.hpp
- **[Verified (upstream)]** The API exposes manager logs, but `manager:read` is broader than the single logs endpoint; no native feed-freshness Prometheus metric was verified. The chosen sidecar avoids API credentials and that broader RBAC scope. https://documentation.wazuh.com/4.14/user-manual/api/rbac/reference.html
- **[User decision]** Debian-family agents only initially; k0s0 is the stop/go pilot; only explicitly approved hosts are added. Proxmox coverage is partial. OPNsense event forwarding is included as non-blocking manual tier-3 integration, without CVE coverage. Authentik SAML is optional post-core with local break-glass login.
