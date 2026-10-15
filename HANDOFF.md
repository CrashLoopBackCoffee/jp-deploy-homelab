# Handoff: bare-metal k0s homelab

Last updated: 2026-10-15. Knowledge lives in `.okf/` (start at `.okf/index.md`) and decisions in `docs/08-Decisions/` (ADR-0004 to ADR-0019). Read `AGENTS.md` first.

## Where things stand

| Area | State |
| --- | --- |
| Cluster | k0s `v1.36.4+k0s.1` on `k0s0` (`10.10.8.1/16`, VLAN 10), one controller+worker, no taints, API `https://10.10.8.1:6443` |
| Node access | `k0sctl@10.10.8.1` with the agent-held `k0s` key and passwordless sudo; `alten` is for humans only |
| Kubernetes stack | `jaypee-solutions/kubernetes/prod` applied, 133 resources; preview clean after the CNPG backup compatibility update |
| Observability | `jaypee-solutions/observability/prod` (`services/observability`): Loki, Mimir (blocks in QuObjects `mimir-metrics`), Grafana at `https://g.4jp.de`, Alloy, kube-state-metrics, node-exporter; 15 alert rules and 9 dashboards (5 generated, 4 community) provisioned, alerts delivered by Pushover (ADR-0019) |
| Add-ons | MetalLB (`10.10.88.1`-`.250`), NFS CSI, cert-manager (DNS-01 via Cloudflare), Traefik at `10.10.88.1`, CloudNativePG operator and Barman plugin, OpenEBS LVM LocalPV, Longhorn 1.13.0 (1 replica, default StorageClass `longhorn`) |
| TLS / DNS | Wildcard `*.4jp.de` issued by Let's Encrypt; dnsmasq records `k8s-ingress-prod.4jp.de` and `g.4jp.de` via the OPNsense API. `grafana.4jp.de` belongs to the user's old Grafana; the workstation resolver (`1.1.1.1`) cannot resolve LAN-only records |
| Storage | `postgres` VG on the WDC 256 GB NVMe (`openebs-lvm-postgres`); Kingston 1 TB NVMe is ext4 at `/var/lib/longhorn` for Longhorn. Both have QuObjects backup targets; PostgreSQL base+WAL and Longhorn disposable backup restores succeeded (ADR-0016, ADR-0017). The temporary PostgreSQL restore Cluster/PVC/PV was deleted after explicit approval. |
| Repo | `svn`, `obsidian`, `ollama`, `ingress`, `s3` (MinIO) workspaces removed; `monitoring`, `backup`, `iot`, `n8n`, `paperless` remain |
| Git | PRs #5 and #7 to #13 are merged; local `main` is current at the #5 merge. All other local and remote branches are deleted, so only `main` exists. Further edits belong on feature branches and go through PRs. |
| Inventory | `k0s0` is documented in NetBox (device, `enp6s0` with MAC, `10.10.8.1/16`, platform Ubuntu 24.04), verified 2026-10-11; nodes 2 and 3 need the same records once mapped |
| Security | OPNsense API user holds only "Services: Dnsmasq DNS/DHCP: Settings" (verified: Unbound returns 403) |

## Working in this repo

- Enter with direnv. `.envrc` loads `OP_SERVICE_ACCOUNT_TOKEN`, `OPNSENSE_*`, and writes the admin `KUBECONFIG` to `.direnv/kubeconfig`. Warn before commands that might request biometric approval.
- Pulumi: from `services/kubernetes` or `services/observability`, run `direnv exec ../.. pulumi preview --stack prod --non-interactive` before every `pulumi up`; do not interrupt updates.
- Git: `main` changes only through feature-branch PRs. Pre-commit hooks scan the whole directory, so untracked files can block a commit. Never commit APM-managed skills (`.agents/skills/`, `.claude/skills/`); `apm.yml` and `apm.lock.yaml` are tracked.
- Pulumi tips: clear leftovers of an interrupted update with `pulumi refresh --clear-pending-creates`. A preview can fail on a transient chart download from `github.com`; retry before assuming drift.
- NetBox (`https://netbox.4jp.de`, NetBox 4.2): `nbcli` is configured in `~/.nbcli/user_config.yml`; its Python (`~/.local/share/uv/tools/nbcli/bin/python`) has `pynetbox`.
- Node changes go in `services/k0s` (`k0sctl/cluster.yaml`, `ansible/`); cluster add-ons go in Pulumi.
- Checks: `uv run ./scripts/run-all-checks.sh`, `uv run /Users/alten/.agents/skills/okf-validate/scripts/okf_validate.py .okf --strict`. Ruff has one existing `PLW0108` finding in `paperless.py`.
- Secrets: all in the `Homelab` vault, `my.1password.eu`. Pulumi's resolver looks items up by title; the `op` CLI needs the item ID for `Cloudflare [4jp.de]` (`b6i34pfgjitlzneedilxq47lxa`).
- Donors: run `scripts/pull-donors` at least once a day and before reading `mp-deploy-homelab` or `th-deploy-homelab` (siblings of this repository); stale clones hid relevant donor work on 2026-10-15.

## Open items

1. Scheduled backups are healthy: CloudNativePG ran nightly at 03:00 UTC (2026-10-13 to 2026-10-15, all `completed`), and Longhorn backed up the five observability volumes at 02:00 UTC on 2026-10-14 and 2026-10-15 (all `Completed`). A restore from a scheduled Longhorn backup is untested; do it with a disposable volume before relying on Longhorn for application data.
2. ADR-0018 (accepted): time-targeted PITR is **verified**. The encrypted HBS 3 off-site backup and restore are deferred because the remote NAS is offline and its reconfiguration is still to be scheduled. They must pass before any application migration.
3. Observability follow-ups (ADR-0019): Mimir's store-gateway read path for aged blocks is untested; nothing alerts if Grafana, Alloy or Mimir itself is down (consider a Pushover heartbeat or an external check); metrics volumes are included in the nightly Longhorn backups.
4. Other stacks still carry donor values (`tobiash.net`, `op://Pulumi/...`, Synology endpoints); none has been previewed. Each needs a JP mapping first. Paperless migration is not started.
5. Nodes 2 and 3 are unmapped; Phase 1 is explicitly non-HA. The API endpoint `10.10.8.1` must become a load-balanced VIP before Phase 3 (ADR-0008). Increase Longhorn replicas after node 2 joins.
6. Public exposure: static IPv4 with Caddy on OPNsense (ADR-0011).
7. sshd on `k0s0` still allows password authentication globally.
8. Housekeeping: all stale branches are deleted. Decide whether `docs/.obsidian/` is tracked or ignored (it is neither today); set the primary MAC on the `enp6s0` interface in NetBox (cosmetic); add a Longhorn mount check (`findmnt /var/lib/longhorn`) to a runbook.

## Gotchas

- `op` prompts time out when run headless; use the service account. Never write secrets to 1Password from Pulumi (the service account is read-only).
- The LAN resolver is authoritative for `4jp.de`, so ACME self-checks use public nameservers (configured in `certmanager.py`).
- Delete PVCs before uninstalling the OpenEBS driver, otherwise logical volumes and kubelet mounts are orphaned.
- Volume expansion needs a pod restart.
- Never address disks by `/dev/...` names; use by-id paths and serials.
- k0sctl needs all three host key types of `10.10.8.1` in `known_hosts`.
- Longhorn needs `multipathd` to ignore `sd*` devices and `nfs-common` on the node; both are in `services/k0s/ansible/prepare-longhorn-storage.yaml`. The chart has hook jobs, so it is a `helm.v3.Release`, and there must be only one CSI snapshot controller (OpenEBS provides it).
- If `/var/lib/longhorn` is ever unmounted, Longhorn would write replicas to the root volume.
- Some terminals get `No route to host` for hosts on the Mac's own subnet (`192.168.178.0/24`, including NetBox) while the browser and another terminal work. Suspected cause: macOS Local Network permission for that terminal app. Run LAN checks from a terminal that works.
- The workstation resolver (`1.1.1.1`) cannot resolve LAN-only records such as `g.4jp.de`; use the router resolver or `curl --resolve`.
- Full list: `.okf/operational-lessons.md`.

## Starter prompt for the next session

```text
Continue the bare-metal k0s homelab work. Read HANDOFF.md, AGENTS.md, and .okf/index.md first. All PRs through #13, including #5 and #7, are merged into `main`, and merged local branches are cleaned up. The cluster has a verified PostgreSQL pilot (scheduled backups, restore and time-targeted PITR) and a running LGTM observability stack with Pushover alerting at https://g.4jp.de (ADR-0019); nightly CloudNativePG and Longhorn backups have run on several nights and all alert rules are inactive. The encrypted off-site HBS 3 backup and restore test is deferred until the remote NAS is back online and reconfigured; it still gates application migration. Next candidates: map one donor stack (Paperless first) to JP values and plan its migration to CloudNativePG, and test a Longhorn restore from the nightly backups. Ask before destructive actions, preview before applies, record decisions in ADRs and insights in .okf, and warn before any command that may require biometric approval.
```
