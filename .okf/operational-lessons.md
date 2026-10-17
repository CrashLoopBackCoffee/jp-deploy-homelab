---
type: Runbook
title: Operational lessons from the first k0s and Pulumi rollout
description: Pitfalls hit while bringing up k0s0 and the Kubernetes stack, with the fix or rule for each, plus suggested standing instructions for agents.
timestamp: 2026-10-11T15:00:00Z
tags: [homelab, lessons, pulumi, k0s, 1password, opnsense, storage]
---

# Lessons

| Area | What happened | Rule |
| --- | --- | --- |
| Git | `services/` was untracked, so deleting four workspaces was irreversible | Commit before destructive refactors; recover from donor repos only |
| k0sctl / SSH | `k0sctl` failed with a host-key mismatch when `known_hosts` held only the ed25519 key | Add all host key types with `ssh-keyscan` after verifying the known fingerprint |
| k0sctl | Needs a user with passwordless sudo; a fingerprint-gated key plus sudo password cannot work | Use the dedicated `k0sctl` account (`docs/08-Decisions/ADR-0007 - Dedicated k0sctl automation account.md`) |
| Node prep | kubelet will not run with swap | Disable swap and its `/etc/fstab` entry before bootstrap |
| Disks | Reported drives held old Proxmox and Windows installs | Check `lsblk -f` and serials before assigning a role; wipe only with explicit approval |
| uv | Adding `services/k0s` (no `pyproject.toml`) broke the workspace glob `services/*` | Exclude non-Python directories in `[tool.uv.workspace]` |
| 1Password | `op` rejects brackets in item titles, while the Pulumi resolver needs the title | Read by item ID with `op`; keep titles stable in refs |
| 1Password | Desktop-app approval prompts time out headless (`authorization timeout`) | Use the service account token loaded by `.envrc` (`docs/08-Decisions/ADR-0013 - 1Password service account for Pulumi.md`) |
| OPNsense | Credentials were in `username`/`password`, not `Key`/`Secret`; the key returned 403 until the right privilege was granted | Test the exact endpoints the code calls before applying |
| OPNsense DNS | The helper wrote Unbound overrides, but the router runs dnsmasq (`docs/08-Decisions/ADR-0001 - Use dnsmasq instead of Kea on OPNsense.md`) | Read the decision log before choosing APIs (`docs/08-Decisions/ADR-0012 - Local DNS records through dnsmasq on OPNsense.md`) |
| cert-manager | DNS-01 stalled: the LAN resolver is authoritative for `4jp.de` and returned NXDOMAIN for `_acme-challenge` | Force public recursive nameservers for the self-check |
| OpenEBS LVM | `snapshot-controller` crash-looped with the snapshot CRDs disabled | Keep the chart default CRDs and controller on |
| OpenEBS LVM | Volume expansion applies only after the pod restarts | Plan rolling restarts for CloudNativePG resizes |
| OpenEBS LVM | Uninstalling the driver before deleting PVCs left an orphan LV and a stale kubelet mount | Delete PVCs first; otherwise `umount`, then `lvremove` by hand |
| Pulumi | Interrupting `pulumi up` left a pending create | Wait for runs; clear leftovers with `pulumi refresh --clear-pending-creates` |
| Pulumi | Dynamic OPNsense resources read credentials at apply time only | Previews can use placeholders; applies cannot |
| Cloudflare | The token could read the zone but not manage tokens | Verify DNS Edit with a temporary TXT record before relying on DNS-01 |
| Longhorn | `multipathd` is active on Ubuntu and claims Longhorn's `/dev/sdX` devices | Blacklist `^sd[a-z0-9]+` in `/etc/multipath.conf` and restart `multipathd` before installing |
| Longhorn | The chart ships pre-upgrade, post-upgrade, and pre-delete hook jobs | Use `helm.v3.Release`, not `helm.v4.Chart` |
| Longhorn | The default replica count of 3 leaves every volume degraded on one node | Set replica count 1 until a second node exists |
| Pulumi | A preview failed with a timeout fetching the chart tgz from `github.com` while the apply had worked | Retry the preview; it is network flakiness, not drift |
| OPNsense | The API key cannot list users (404), so its privileges cannot be audited through its own key; after a first UI removal the key still answered 200 on Unbound, and only a later change produced 403 | Verify privilege changes by probing the exact endpoints (200 vs 403), not by trusting the UI state alone |
| LAN access | `curl` and `pynetbox` to a host on the Mac's own subnet failed with `No route to host` from some terminals, while `traceroute`, the browser, and another terminal worked | Run LAN API checks from a terminal that works; if one fails instantly with `No route to host`, check macOS Privacy & Security > Local Network for that app (suspected, unconfirmed) |
| Barman Cloud / QuObjects | The first base backup and WAL archive failed with S3 `InvalidDigest`; changing the ObjectStore did not update the already-running sidecar environment | Set boto3's optional request/response checksum modes to `when_required`, preview/apply the ObjectStore change, then use `kubectl cnpg restart CLUSTER` for a controlled Pod rollout; verify archiver counters and restore actual rows from an independent Cluster |
| CNPG / Longhorn | Both operators define a `Backup` resource; unqualified `kubectl wait backup/...` resolved to Longhorn | Qualify CNPG backups as `backup.postgresql.cnpg.io/NAME` |
| Longhorn | The chart ships NetworkPolicies that admit only Longhorn pods to the manager, so a scraper in another namespace gets `connection refused` on port 9500 even though the pod listens | Add an additive NetworkPolicy for the one scraper and port; policies are additive |
| Longhorn 1.13 | `longhorn_volume_robustness` is one 0/1 series per `state` label and `longhorn_backup_state` does not exist; backup freshness is `longhorn_volume_last_backup_at` | Query the live metric names and labels before writing rules |
| Grafana | File-provisioned alert rules are read only at startup and are not deleted when their entry disappears | Roll the pod on content change (hash annotation) and list removed uids under `deleteRules` |
| Grafana | Local `grafana.4jp.de` collided with the user's old Grafana, a public Cloudflare record | Check the name resolves nowhere (`dig` against router and public resolvers) before creating a host record; this stack uses `g.4jp.de` |
| Alloy / Prometheus | A `pod` target label on the kube-state-metrics scrape overwrote the metric's own `pod` label (the real one became `exported_pod`), so pod-keyed queries and alert text were silently wrong | Never set `pod` or `namespace` target labels for a scrape whose series describe other objects; check a sample series' labels after adding a scrape |
| Kubernetes / MetalLB | A LoadBalancer Service with `loadBalancerSourceRanges` still accepted traffic from a disallowed host on its auto-allocated node port (found 2026-10-17 with the syslog receiver): kube-proxy enforces the ranges for the load balancer address only | For a MetalLB Service that must be restricted set `allocateLoadBalancerNodePorts: false` at creation (setting it later keeps the existing ports, so the Service has to be recreated), and test the node port from a disallowed host, not only the load balancer address |
| Node / Alloy | The first apply of the probe config left a new Alloy pod in `CrashLoopBackOff` with `couldn't initialize inotify: too many open files` (2026-10-17): `fs.inotify.max_user_instances` is 128 per user, k0s, the kubelet, containerd and every root pod share it, and the node held 153 instances in total. The old pod kept serving, but `Scrape target down` fired and Helm stayed in `pending-upgrade` | Raise the limit on the node (`services/k0s/ansible/tune-kernel-inotify.yaml`, 1024) before adding watchers; prefer `detector = "poll"` for Alloy's `local.file`; count the instances with a privileged `kubectl debug node/... --profile=sysadmin` pod (`ls -l /proc/*/fd`, grep `anon_inode:inotify`) and delete the pod afterwards |
| Pulumi / Helm | A `pulumi up` run through a tool with a 290 s limit was killed while the Alloy release waited for a pod that never became ready; Helm kept `pending-upgrade`, and the Grafana part of the same apply had already put alert rules live without the probes behind them | Never run a Helm-releasing `pulumi up` with a hard timeout (use a background run without one); recover with `helm -n <ns> rollback <release> <last deployed revision>`, then `pulumi preview`; when two parts of one apply depend on each other (rules and the probes behind them), expect the first part to alert early and cover it with an expiring Grafana silence |
| Mimir | New probes and scrapes were only partly ingested: Alloy logged `per-user series limit of 150000 exceeded` (2026-10-17). One job, the Kubernetes API server, held 82,727 of the 143,000 active series, about 66,000 of them unused histogram `_bucket` series | Look at `topk(10, count by (job)({__name__=~".+"}))` and `topk(10, count by (__name__)({job="<job>"}))` before raising `max_global_series_per_user`; drop what nothing reads (ADR-0026). Series leave memory only at the next head compaction, so `POST /ingester/flush?wait=true` on the ingester pod frees the budget at once |
| Alloy | `prometheus.scrape` without `job_name` labels its series with the component name (`prometheus.scrape.ax51`), so alerts, dashboards and `up{job="ax51"}` found nothing even though every target was up | Always set `job_name` when other things select on the job; check with `count by (job)(up)` after adding a scrape. The leftover series under the wrong name age out by themselves |
| Pulumi | A `delete original` of a ConfigMap that no longer existed (left over from an interrupted replacement) kept the update running for 600 s before it succeeded | After an interrupted update check what already exists in the cluster; expect a final cleanup step to wait out the provider's 10-minute timeout, and do not interrupt it |
| CNPG / QuObjects | On 2026-10-16 both nightly base backups (`postgres-pilot`, `paperless-db`) failed at about 03:04 UTC with `NoSuchUpload ... The specified bucket does not exist` on `CompleteMultipartUpload`, and `paperless-db` had WAL archive failures from 01:43; the bucket worked again hours later, the alert `cnpg-backup-stale` fired at 36 hours without a success, and Mimir and Longhorn (other buckets) showed no errors | Treat as a transient object-store outage: confirm with an on-demand plugin backup (it completed in 6 s), check `ContinuousArchiving` and `pg_stat_archiver` (retried WAL files catch up by themselves), take a fresh base backup of every cluster with real data; the alert clears within about two minutes of a completed backup. The cause is on the QNAP side (unconfirmed) |
| Mimir | `usage_stats` reports to `stats.grafana.org`, which resolves to `0.0.0.0` on the LAN resolver, so Mimir logs `connection refused` about once a minute | Not an object-store error; filter it out when searching Mimir logs for storage problems (disabling `usage_stats` is optional) |

# Suggested standing instructions for agents

- Never guess hostnames, IPs, or disk serials; ask or read them from the host.
- Before destructive cleanup, dry-run it and delete dependents before the drivers that own them.
- Node-level changes belong in `services/k0s` (k0sctl, Ansible); cluster add-ons belong in Pulumi.
- Pulumi must only read secrets from 1Password; writes use the interactive `op` session.
- Dry-run or preview first; credentials are tested against the exact endpoints the code calls.
- Check the metric catalogue of the deployed version before writing an alert rule, and evaluate every rule against live data; a rule on a metric of the wrong shape or name is silently inactive.
- Never run `cd` in the shell tool, even inside a chained command; use the tool's `cwd` parameter.
- Pull the donor repositories (`scripts/pull-donors`) at least once a day and before reading them; the reflog shows the last pull. Never conclude that a donor lacks something from a clone that is days old.
- Never commit APM-managed skills (`.agents/skills/`, `.claude/skills/`); `apm.yml` and `apm.lock.yaml` are tracked. Pre-commit scans the whole directory, so untracked files can block a commit.
- Warn before any step that needs a 1Password biometric approval: `direnv` loading `.envrc` once, and the first SSH use of the `k0s` key through the 1Password agent.
- Stage explicit file paths, never a directory: untracked tool folders such as `docs/.obsidian/` get rewritten in place by the pre-commit hooks (it happened on 2026-10-15; restore from the index, then unstage).

See also [k0s0 node](./k0s0-node.md) and [Kubernetes platform stack](./kubernetes-platform-stack.md).
