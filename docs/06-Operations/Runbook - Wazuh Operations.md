---
tags:
  - homelab
  - runbook
  - wazuh
type: runbook
status: active
created: 2026-10-29
updated: 2026-10-29
---

# Runbook - Wazuh Operations

## Scope and component map

Wazuh is a single-node, non-HA deployment in namespace `wazuh`, managed by the `services/wazuh` Pulumi stack (`prod`). The deployment and its accepted risks are described in [[ADR-0037 - Wazuh security monitoring on k0s]] and [[Wazuh Security Monitoring]]; terminology is in [[GLOSSARY]]. The current deployed version is pinned in `services/wazuh/Pulumi.prod.yaml`.

| Component | Kubernetes resource / location | Role |
| --- | --- | --- |
| Indexer | StatefulSet/Pod `wazuh-indexer-0`, Service `wazuh-indexer:9200`, PVC `data-wazuh-indexer-0` | OpenSearch-compatible alert, inventory and vulnerability indices |
| Manager | StatefulSet/Pod `wazuh-manager-0`, API Service `wazuh-manager:55000`, public agent LB `wazuh-manager-agents` (`10.10.88.3`) | Agent enrollment, analysis, vulnerability scanner and Filebeat indexing |
| Dashboard | Deployment `wazuh-dashboard`, LAN ingress `https://wazuh.4jp.de` | Wazuh app and operator interface |
| Exporters | Deployments `wazuh-indexer-exporter`, `wazuh-findings-exporter` | Indexer and findings metrics to Alloy/Mimir |
| CTI freshness | `cti-freshness` manager sidecar; `ossec-log-tail` forwards manager log lines | Remote Wazuh CTI endpoint reachability heartbeat and scanner log signal to Loki |
| Agent | Host `k0s0`, ID `001`, Ansible inventory/playbook under `services/wazuh/ansible/` | Host inventory and vulnerability data |
| Credentials and PKI | Secret `wazuh-credentials`; certificate Secrets `wazuh-*`; CA Secret `wazuh-ca` | Generated credentials, API/enrollment and TLS identities |

The indexer and manager PVCs are Longhorn-backed and included in cluster backups. Their claims are `data-wazuh-indexer-0` (50 GiB) and `manager-data-wazuh-manager-0` (20 GiB). Do not delete, replace, or rebind either PVC as an ordinary troubleshooting step.

## Credentials

Retrieve credentials only in a private terminal when needed; never paste or log decoded values. The dashboard admin password is:

```sh
kubectl -n wazuh get secret wazuh-credentials -o jsonpath='{.data.admin}' | base64 -d
```

Other values (`kibanaserver`, `grafana_reader`, `metrics_reader`, API `api`, enrollment `enrollment`) are keys in `wazuh-credentials`; use secretKeyRef mounts or read them only in a deliberately private session. Do not fetch secrets into shell history, tickets, chat, or command output captured by CI. The API password key belongs to `wazuh-wui`; enrollment is also mounted as `/var/ossec/etc/authd.pass`. The indexer administrator is privileged: do not use it for routine read-only checks.

Pulumi resolves its 1Password references at runtime. Before Pulumi, unlock the 1Password CLI/session and verify the repo's configured service account; an unlock prompt/timeout is not evidence of broken Kubernetes resources. Do not print service-account tokens or secret values.

## Health checks

Run from the repository/worktree with the production kubeconfig context selected.

```sh
kubectl -n wazuh get pods,pvc
kubectl -n wazuh get statefulset,deployment
kubectl -n wazuh get certificates
kubectl -n wazuh logs wazuh-manager-0 -c manager --since=2h
kubectl -n wazuh logs wazuh-manager-0 -c cti-freshness --since=2h
kubectl -n wazuh logs wazuh-manager-0 -c ossec-log-tail --since=2h
kubectl -n wazuh exec wazuh-manager-0 -c manager -- /var/ossec/bin/agent_control -l
```

A healthy steady state has all workload Pods Ready, both claims Bound, certificates Ready, the indexer cluster `green`, and agent `001` (`k0s0`) `Active`. To inspect indexer health, use an authenticated admin session/probe with the administrator TLS certificate and CA (never put passwords inline in commands or echo them): query `GET /_cluster/health`; require `status=green`, one node, and `unassigned_shards=0`. Yellow means unassigned replicas; this is a single-node cluster and replica settings must be zero. Red or unavailable primary shards require immediate investigation; do not delete data or run securityadmin as a health fix.

Agent state is independently checked with `agent_control -l` and the Wazuh API `GET /agents?agents_list=001`. It must report active. On an upgrade, agent version must be no higher than manager version. `wazuh-agent-disconnected` being Normal does not substitute for checking the named agent.

### CTI/feed signals

The manager's `cti-freshness` sidecar polls the public catalog endpoint every 10 minutes and emits `event=cti_freshness` records into Loki. The Loki heartbeat alert is intended to detect a missing periodic probe/log pipeline signal (absence for 30 minutes), not prove that downloaded data was applied. Check recent heartbeat records and explicit CTI probe errors in Loki, then inspect manager scanner logs for `Error updating feed` or related errors.

`Feed update process completed.` is **not** a heartbeat. In 4.14.9 it is logged when new catalog content is applied; with no new content it may not recur for hours. Its absence alone cannot establish a stale feed. Conversely a heartbeat only proves the remote endpoint/probe and log path are alive, not local feed application. Treat these as separate evidence. The current pilot decision is STOP on enrolling additional hosts until CTI freshness is reviewed; only the approved k0s0 agent is enrolled.

## Certificate renewal and pod restart

cert-manager renews the leaf Certificates and updates their corresponding Secrets, but updating a Secret does not by itself restart a pod that consumes it. The `wazuh-certificate-rotation` CronJob runs daily at 03:17 UTC, hashes the served certificate data and records a metadata-only baseline on each owning workload. This initial observation does not change pod templates; later differences update pod-template annotations and roll consumers in dependency order. Inspect its result with:

```sh
kubectl -n wazuh get cronjob wazuh-certificate-rotation
kubectl -n wazuh create job --from=cronjob/wazuh-certificate-rotation cert-rotation-manual
kubectl -n wazuh logs job/cert-rotation-manual
kubectl -n wazuh delete job cert-rotation-manual
```

The job uses a namespace Role and restricted baseline-compatible security context. It reconciles in dependency order: `wazuh-indexer` and `wazuh-admin` → indexer; `wazuh-manager` and `wazuh-filebeat` → manager; `wazuh-dashboard` → dashboard; and reader certificates → exporters. The initial run records metadata-only baselines, avoiding a pod-template change; changed hashes patch the owning pod templates. Verify rollout completion, all Pods Ready, indexer green and agent `001` Active.

For a planned renewal, `cmctl` can request renewal (use a supported cmctl matching cluster cert-manager):

```sh
cmctl renew -n wazuh <certificate-name>
kubectl -n wazuh wait --for=condition=Ready certificate/<certificate-name> --timeout=5m
kubectl -n wazuh create job --from=cronjob/wazuh-certificate-rotation cert-rotation-manual
```

Do not hand-edit certificate Secrets. For an individual cert, verify only its consumer rolls; for a full rotation, verify indexer first, manager next, dashboard after manager, and exporters last.

## Indexer security configuration after rebuild

The indexer Pod includes a `security-reconciler` sidecar that runs the same idempotent security-configuration script as the Pulumi Job after every pod start. It waits for indexer HTTPS readiness, then applies the code-managed OpenSearch Security roles/mappings, templates, ISM policies and replica settings, logs success, and remains alive. It mounts only the required security ConfigMap, `internal_users.yml`, `wazuh-admin` certificate and `wazuh-ca` CA certificate read-only; `/tmp` is an `emptyDir` for the script's scratch files. No additional API permissions or elevated Pod Security settings are used.

After an indexer pod restart/rebuild, inspect the sidecar log and validate cluster health and admin access:

```sh
kubectl -n wazuh logs wazuh-indexer-0 -c security-reconciler
kubectl -n wazuh exec wazuh-indexer-0 -c security-reconciler -- \
  curl --silent --show-error --cacert /ca/ca.crt --cert /certs/tls.crt \
  --key /certs/tls.key https://wazuh-indexer:9200/_cluster/health
```

Require a successful security-admin apply, `status=green`, zero unassigned shards, reader write requests denied with HTTP 403, all Grafana datasource health checks OK, all Pods Ready and agent `001` Active. If the sidecar fails or its log lacks the success output, inspect its logs and events; the input-hashed Pulumi security Job remains available as a manual recovery path after indexer readiness. Do not enable OpenSearch default security initialization or hand-edit roles.

## 4.14.x upgrade rehearsal / procedure

Only upgrade stable patch releases. Check the Wazuh release notes/release tag and verify matching stable tags exist for `wazuh/wazuh-indexer`, `wazuh/wazuh-manager`, and `wazuh/wazuh-dashboard` on Docker Hub. Do not promote an RC. Confirm the release is within 4.14.x and review any required manual migration steps. Agents must never be upgraded before the manager.

1. Confirm current steady-state health and record the image version, cluster health, pod readiness and agent 001 status/version. Ensure no active recovery or certificate work.
2. Take on-demand Longhorn backups of **both** live data volumes before changing the version. Identify source volume names from PVC `.spec.volumeName`, create uniquely named on-demand Longhorn backups for each source volume, and wait until each backup reports `Completed`/100% with a non-empty backup URL. Verify both URLs identify the intended source volume. The #100 test used distinct temporary restore volumes and established the restore path; do not rely solely on a successful Snapshot CR or the nightly schedule.

The Longhorn API sequence exercised in #100 is one `Snapshot` CR followed by one `Backup` CR per volume. This function snapshots and starts the backup; use distinct run names and run it for each current PVC volume before the upgrade:

```sh
backup_volume() {
  volume=$1
  name=$2
  kubectl -n longhorn-system apply -f - <<EOF
apiVersion: longhorn.io/v1beta2
kind: Snapshot
metadata:
  name: ${name}-snapshot
  namespace: longhorn-system
spec:
  volume: ${volume}
  createSnapshot: true
EOF
  kubectl -n longhorn-system wait --for=jsonpath='{.status.readyToUse}'=true \
    snapshot.longhorn.io/${name}-snapshot --timeout=10m
  kubectl -n longhorn-system apply -f - <<EOF
apiVersion: longhorn.io/v1beta2
kind: Backup
metadata:
  name: ${name}
  namespace: longhorn-system
spec:
  snapshotName: ${name}-snapshot
  backupMode: incremental
EOF
  kubectl -n longhorn-system wait --for=jsonpath='{.status.state}'=Completed \
    backup.longhorn.io/${name} --timeout=30m
  kubectl -n longhorn-system get backup.longhorn.io ${name} \
    -o jsonpath='{.status.state} {.status.progress} {.status.url}{"\n"}'
}
run=$(date -u +%Y%m%d-%H%M%S)
backup_volume pvc-8ee761c0-8e8a-4c35-bc03-251bee2475c0 wazuh-indexer-${run}
backup_volume pvc-f92dd1a9-14a7-4586-b2c0-73065c5a2701 wazuh-manager-${run}
```

Require `Completed`, progress `100`, and a URL whose `volume=` matches each intended source volume. Retain the completed backup objects until the upgrade is accepted; do not delete the Longhorn Backup CRs or remote backups during cleanup.
3. Edit only `version` in `services/wazuh/Pulumi.prod.yaml` to the chosen patch. From `services/wazuh`, run `direnv exec ../.. pulumi preview --stack prod --non-interactive`. Review the full diff: only image/version-dependent resources should change; PVCs, Secrets and data must not be replaced. Apply serially with `direnv exec ../.. pulumi up --stack prod --non-interactive` after preview. Never run Pulumi commands concurrently.
4. Respect the dependency order: indexer first and wait for green; manager second and wait for Ready/API/agent connectivity; dashboard third and verify login/API; exporters last. If the Pulumi update rolls several resources together, monitor each rollout and do not proceed until the dependency is healthy. Do not upgrade the host agent yet.
5. Verify all Pods Ready, `_cluster/health` green with zero unassigned shards, dashboard and API functioning, fresh alerts/state ingestion, CTI signals, and agent 001 Active. Confirm the manager reports the target version.
6. Only after the manager is verified at the target version, upgrade agent 001 using the repository playbook pinned to that exact package version (including `-1` Debian package suffix), preserving its hold behavior. Run the playbook with `--limit k0s0`; provide enrollment secret by environment as documented in `.okf/wazuh.md`, and do not enable shell tracing. Verify host dpkg version and API agent version match the target and status remains Active.

### Rollback

If upgrade fails before data migration or indices are changed, first revert only the Pulumi `version` to the previous known-good version, preview and review, then apply. Wait in the same indexer → manager → dashboard → exporters order and verify green/Ready/API/agent. Revert the agent package only after manager is back on that prior version; never run an agent newer than manager.

If indexer data is incompatible or corrupted, do **not** assume a version revert is sufficient. Keep the failed PVC untouched, stop/revert the workload under operator control, and restore a matching pre-upgrade Longhorn backup to a separate volume first. Validate the restore before any production cutover. Preserve manager volume separately; manager data includes `client.keys` and enrolled-agent state. Recovery can lose alerts created after the backup. Never attach a restored indexer PVC alongside a live indexer or start a second indexer over production data.

## Restore procedure (validated in ticket #100)

The #100 rehearsal restored manager and indexer backups into distinct temporary Longhorn volumes, waited for `restoreRequired=false`, detached them and inspected them read-only. It did not replace production PVCs or start an indexer from the copy.

1. Identify source PVC and Longhorn volume: `kubectl -n wazuh get pvc -o wide`; match each `spec.volumeName` to the `longhorn-system` `BackupVolume` KubernetesStatus label. Select a completed `backups.longhorn.io` object whose `status.url` names that source volume; record its exact `status.volumeSize`.
2. In `longhorn-system`, create a uniquely named `longhorn.io/v1beta2 Volume` with `spec.fromBackup` equal to that backup URL, `spec.size` set to the exact quoted volume-size bytes, and `numberOfReplicas: 1`. Wait for restore completion (`status.restoreRequired=false`) and detach.
3. Create a manually bound PV/PVC referring to the restore volume handle. Use a throwaway namespace with Pod Security `baseline`; mount the PVC read-only in an inspection pod. Do not start an indexer against this data. For manager recovery compare restored `/var/ossec/etc/client.keys` line count with the expected current count, and inspect `/etc`, `/logs`, `/queue`, `/var`, `/filebeat`, `active-response`, `agentless`, `api`, `integrations`, and `wodles`. For indexer verify `/usr/share/wazuh-indexer/data/nodes/0/indices` exists.
4. For production recovery, plan a maintenance cutover: preserve the failed PVC, stop the corresponding workload, take/record its current state, then bind a separately restored and verified volume through an explicitly reviewed recovery change. Do not improvise PV/PVC deletion or patch a live claim. Keep manager and indexer recovery coordinated; verify green health, manager API, agent 001 Active and dashboard after cutover.
5. Delete inspection Pod, temporary namespace/PVC, PV and Longhorn restore Volume CR; verify they are absent. Keep Longhorn finalizers intact and wait for purge. Ticket #100 found Longhorn source snapshot purge can remain pending; do not remove finalizers manually. A manager-based rebuild can recover current state from current inventory but cannot restore historical alert documents.

## Troubleshooting

- **securityadmin Job exits 127:** command/script was unavailable in the job image/path (historically observed when the securityadmin executable path was wrong). Check Job events/logs and image path; fix the code-managed job and preview. Do not treat the indexer as secured merely because the Job exists. **Exit 255** was observed for invocation/configuration or TLS/authentication failure; inspect the complete job logs, certificate/DN matching and indexer readiness. Do not hand-edit live security roles: the hashed Pulumi job is source of truth.
- **Filebeat bulk requests fail with `_type` compatibility errors:** Wazuh 4.14.9 Filebeat needs `compatibility.override_main_response_version: true` for the OpenSearch 2.19.6 indexer. Confirm this setting in manager Filebeat config, then inspect `filebeat test output` and logs. Do not change index templates to hide the incompatibility.
- **Indexer health yellow, unassigned replica shards:** single-node OpenSearch cannot place replicas. Check cluster health and index settings. The code-managed security/ISM job sets replica count to zero on the system indices and ISM history so future history indices remain single-node compatible. Fix through code and its hashed job; do not manually force allocation or delete indices.
- **Indexer health red / primary unassigned:** treat as data availability incident. Capture logs/health and PVC status; avoid restart loops and data deletion. Use the known-good backup restore path only with an explicitly reviewed cutover.
- **Pod restarts but certificate appears old:** Secret update alone does not reload process certificates. Verify cert Ready and Secret key timestamps/resource version, then restart affected consumers in the order above.
- **Pulumi hangs/errors resolving 1Password:** unlock 1Password and confirm authentication/service-account state. A provider prompt timeout is not evidence that the Pulumi update partially applied; inspect stack state and live resources before retrying any Pulumi operation. Never parallelize or blindly retry a timed-out Pulumi command.
- **Agent absent/disconnected:** check manager `agent_control -l`, API status, service reachability from the approved network, `client.keys` persistence and host service/package. Do not re-enroll or delete an agent ID before checking its existing registration.
- **Feed success line is old:** do not infer failure from that alone. Check CTI heartbeat in Loki, explicit scanner/CTI errors, and evidence of local application separately; heartbeat indicates probe/log pipeline liveness only.

## Alerts

Grafana rules and meanings (new Wazuh rules use warning severity and normal Pushover unless otherwise noted):

| Alert | Meaning |
| --- | --- |
| `wazuh-agent-disconnected` | One or more agents disconnected; 1-hour hold. Check the named agent; no series is normal only when no agents are enrolled. |
| `wazuh-indexer-red` | Indexer reports red health for 10 minutes; investigate primary shard/data availability. |
| `wazuh-indexer-disk-low` | Indexer PVC has <20% free for 30 minutes; investigate capacity before writes fail. |
| `wazuh-manager-down` | Manager StatefulSet has no ready replica for 10 minutes; missing series alerts. |
| `wazuh-high-level-event` | A Wazuh detection rule level 12+ event occurred in the last 15 minutes; inspect the actual alert. This scale is distinct from Grafana severity. |
| `wazuh-critical-finding-active` | A new Active Critical vulnerability transition event matched the selected Wazuh rule IDs; grouped by agent in Loki. Event delivery is best-effort; use the authoritative Wazuh index for current state. |
| `wazuh-feed-error` | Manager scanner log reports an explicit feed update error or CTI probe error; investigate feed processing/connectivity. |
| `wazuh-cti-probe-silent` | Periodic CTI heartbeat absent from Loki for 30 minutes; probe or log pipeline may be down, not proof of local feed staleness. |
| `certificate-expiring` | cert-manager certificate expiry is within 14 days for an hour; investigate renewal. |
| `longhorn-volume-unhealthy` | Longhorn volume is degraded/faulted; critical. |
| `longhorn-volume-backup-stale` | Volume has no recent successful backup (30-hour threshold with hold); critical. |
| `longhorn-backup-target-unavailable` | Longhorn backup target unavailable for 10 minutes; critical. |
| `pvc-nearly-full`, `pod-crash-looping`, `target-down`, `node-not-ready`, `node-memory-high`, `node-filesystem-full` | Generic platform capacity, readiness and scrape signals that may affect Wazuh. |

At the end of maintenance, confirm relevant Wazuh alerts are Normal and no new manager/indexer/PVC errors are present.

## Accepted risks and boundaries

Per [[ADR-0037 - Wazuh security monitoring on k0s]], this is one node and one indexer/manager; Wazuh availability shares the k0s failure domain and downtime is accepted. There is no automated remediation or containment; operators triage findings manually. Alert event forwarding is best effort; Wazuh indices are authoritative, and event streams are not a complete vulnerability lifecycle ledger. CTI remote metadata/heartbeat cannot prove local feed application. Indexer restore or manager-based rebuild can lose historical alert documents. The manager trusts indexer administrator credentials, and broad initial egress/enrollment MITM exposure and Pulumi-stored CA/secrets are accepted risks. Backups are local QuObjects initially and require restore testing; off-site backup is not yet a go-live guarantee. Proxmox coverage is partial, OPNsense has no reliable FreeBSD CVE coverage, and QNAP has no agent/CVE coverage. Wazuh 5.x is a separate breaking migration, not an extension of this 4.14.x runbook.

## Rehearsal record (2026-10-29)

Upstream check found stable 4.14.9 on GitHub and matching Docker Hub image tags for indexer, manager and dashboard. 4.14.10-rc1 and 4.14.10-rc2 exist, but no stable 4.14.10 release was available; RC tags were deliberately not deployed. Therefore an actual patch-version upgrade and version rollback could not be exercised safely yet. Remaining step: when stable 4.14.10 or newer is released, repeat the upgrade/rollback rehearsal above, backing up both volumes first and upgrading the agent only after verifying the manager. The no-version operational rehearsal evidence and any live checks are recorded in `.okf/wazuh.md` and `.okf/log.md`.
