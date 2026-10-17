# Handoff: bare-metal k0s homelab

Last updated: 2026-10-17. Knowledge lives in `.okf/` (start at `.okf/index.md`) and decisions in `docs/08-Decisions/` (ADR-0004 to ADR-0022). Read `AGENTS.md` first.

## Where things stand

| Area | State |
| --- | --- |
| Cluster | k0s `v1.36.4+k0s.1` on `k0s0` (`10.10.8.1/16`, VLAN 10), one controller+worker, no taints, API `https://10.10.8.1:6443` |
| Node access | `k0sctl@10.10.8.1` with the agent-held `k0s` key and passwordless sudo; `alten` is for humans only |
| Kubernetes stack | `jaypee-solutions/kubernetes/prod` applied, 133 resources; preview clean after the CNPG backup compatibility update |
| Observability | `jaypee-solutions/observability/prod` (`services/observability`): Loki, Mimir (blocks in QuObjects `mimir-metrics`), Grafana at `https://g.4jp.de`, Alloy, kube-state-metrics, node-exporter; 16 alert rules and 9 dashboards (5 generated, 4 community) provisioned, alerts delivered by Pushover (ADR-0019). The 16th rule, `paperless-backup-stale`, is in PR #22 and already applied to the cluster |
| Paperless | `jaypee-solutions/paperless/prod` (`services/paperless`): Paperless-ngx 3.3.1 at `https://paperless.4jp.de`, dedicated CloudNativePG cluster `paperless-db`, restic to an off-site Nextcloud nightly at 02:00, QNAP NFS share `/paperless-consume` as scanner intake; local accounts for now, Authentik single sign-on decided (ADR-0021) but not applied; deployed 2026-10-15 from `feature/paperless-prep`, upgraded to 3.x from `feature/paperless-v3` |
| Add-ons | MetalLB (`10.10.88.1`-`.250`), NFS CSI, cert-manager (DNS-01 via Cloudflare), Traefik at `10.10.88.1`, CloudNativePG operator and Barman plugin, OpenEBS LVM LocalPV, Longhorn 1.13.0 (1 replica, default StorageClass `longhorn`) |
| TLS / DNS | Wildcard `*.4jp.de` issued by Let's Encrypt; dnsmasq records `k8s-ingress-prod.4jp.de` and `g.4jp.de` via the OPNsense API. `grafana.4jp.de` belongs to the user's old Grafana; the workstation resolver (`1.1.1.1`) cannot resolve LAN-only records |
| Storage | `postgres` VG on the WDC 256 GB NVMe (`openebs-lvm-postgres`); Kingston 1 TB NVMe is ext4 at `/var/lib/longhorn` for Longhorn. Both have QuObjects backup targets; PostgreSQL base+WAL and Longhorn disposable backup restores succeeded (ADR-0016, ADR-0017). The temporary PostgreSQL restore Cluster/PVC/PV was deleted after explicit approval. |
| Repo | `svn`, `obsidian`, `ollama`, `ingress`, `s3` (MinIO) workspaces removed; `monitoring`, `backup`, `iot`, `n8n`, `paperless` remain |
| Git | `main` holds everything up to the PR #16 merge; as of 2026-10-17 nothing else has merged. **Four JP pull requests are stacked; merge them in this order and retarget each to `main` after the one below it merges:** #17 `feature/paperless-prep` (Paperless deployment, base `main`), #19 `feature/paperless-v3` (upgrade to 3.3.1, ADR-0021), #20 `docs/cnpg-backup-outage-2026-10-16` (incident notes), #21 `feature/cnpg-backup-window` (backups at 21:00 UTC, ADR-0022). The docs-only PR for this handoff is stacked on #21. Independent, base `main`: #18 `chore/pull-donors` (`scripts/pull-donors`, a daily-pull rule; **the script exists only on that branch until it merges**, so from another branch run `DONOR_PARENT=<parent dir> bash <(git show chore/pull-donors:scripts/pull-donors)`) and #22 `feature/paperless-backup-alert` (the `paperless-backup-stale` alert). The cluster already runs the state of #21 and #22 (applied from the branches), so `main` is behind the cluster until they merge. AX41 PR #97 (Authentik blueprint for Paperless) is still open in `jaypee-solutions/AX41`. |
| Inventory | `k0s0` is documented in NetBox (device, `enp6s0` with MAC, `10.10.8.1/16`, platform Ubuntu 24.04), verified 2026-10-11; nodes 2 and 3 need the same records once mapped |
| Security | OPNsense API user holds only "Services: Dnsmasq DNS/DHCP: Settings" (verified: Unbound returns 403) |

## Working in this repo

- Enter with direnv. `.envrc` loads `OP_SERVICE_ACCOUNT_TOKEN`, `OPNSENSE_*`, and writes the admin `KUBECONFIG` to `.direnv/kubeconfig`. Warn before commands that might request biometric approval.
- Pulumi: from `services/kubernetes`, `services/observability` or `services/paperless`, run `direnv exec ../.. pulumi preview --stack prod --non-interactive` before every `pulumi up`; do not interrupt updates.
- Git: `main` changes only through feature-branch PRs. Pre-commit hooks scan the whole directory, so untracked files can block a commit. Never commit APM-managed skills (`.agents/skills/`, `.claude/skills/`); `apm.yml` and `apm.lock.yaml` are tracked. Stage explicit file paths, never a directory: the hooks rewrite untracked folders such as `docs/.obsidian/` in place.
- Pulumi tips: clear leftovers of an interrupted update with `pulumi refresh --clear-pending-creates`. A preview can fail on a transient chart download from `github.com`; retry before assuming drift.
- NetBox (`https://netbox.4jp.de`, NetBox 4.2): `nbcli` is configured in `~/.nbcli/user_config.yml`; its Python (`~/.local/share/uv/tools/nbcli/bin/python`) has `pynetbox`.
- Node changes go in `services/k0s` (`k0sctl/cluster.yaml`, `ansible/`); cluster add-ons go in Pulumi.
- Checks: `uv run ./scripts/run-all-checks.sh`, `uv run /Users/alten/.agents/skills/okf-validate/scripts/okf_validate.py .okf --strict`.
- Secrets: all in the `Homelab` vault, `my.1password.eu`. Pulumi's resolver looks items up by title; the `op` CLI needs the item ID for `Cloudflare [4jp.de]` (`b6i34pfgjitlzneedilxq47lxa`).
- Donors: run `scripts/pull-donors` at least once a day and before reading `mp-deploy-homelab` or `th-deploy-homelab` (siblings of this repository); stale clones hid relevant donor work on 2026-10-15.

## Open items

1. **Backups verified.** CloudNativePG base backups run at 21:00 UTC (23:00 CEST). The first runs in the new window, `postgres-pilot-backup-20261016210000` and `paperless-db-backup-20261016210000`, are `completed`; the 2026-10-16 03:00 UTC failures stay unexplained (the QNAP HBS sync window is only suspected, ADR-0022). If a backup fails again, HBS is not the cause: look at the QNAP's QuObjects logs. The `cnpg-backup-stale` alert fires after 36 hours without a success. After DST ends on 2026-10-25 set `0 0 22 * * *` in the `kubernetes` and `paperless` stack configs to keep 23:00 local. **Longhorn restore verified 2026-10-17:** the `media-paperless-0` volume was restored from the scheduled backup of 02:05 UTC into a disposable volume and its files had the same checksum as the live volume (`.okf/kubernetes-platform-stack.md`); the test objects were deleted with approval.
2. ADR-0018 (accepted): time-targeted PITR is **verified**. The encrypted HBS 3 off-site backup and restore are deferred because the remote NAS is offline and its reconfiguration is still to be scheduled. They must pass before any application migration.
3. Observability follow-ups (ADR-0019): Mimir's store-gateway read path for aged blocks is untested; nothing alerts if Grafana, Alloy or Mimir itself is down (consider a Pushover heartbeat or an external check); metrics volumes are included in the nightly Longhorn backups.
4. Paperless 3.3.1 is deployed (ADR-0020, ADR-0021, `.okf/paperless.md`) at `https://paperless.4jp.de` and holds one real document (scanned through the QNAP intake); it is backed up and a disaster-recovery import was verified on v3. The Grafana alert `paperless-backup-stale` (CronJob not succeeded for 36 hours) exists (PR #22). **Waiting on the user for single sign-on** through the shared Authentik (`https://id.jaypee.solutions`); on 2026-10-17 AX41 PR #97 was still open and the 1Password item `Paperless OIDC` did not exist in `Homelab`. Needed: merge AX41 PR #97, create the Authentik application and provider (slug `paperless`, redirect URI `https://paperless.4jp.de/accounts/oidc/authentik/login/callback/`, settings in the AX41 note), deploy the AX41 role, put users into the groups `paperless` / `paperless-admins`, and create the item. Then a separate JP change adds the OIDC settings (`PAPERLESS_SOCIAL_ACCOUNT_SYNC_*`), the `paperless-admins` superuser mapping, keeps local login, and creates the Paperless group `paperless`. Mail (ingestion and notifications) is postponed. The other donor stacks (`n8n`, `monitoring`, `backup`, `iot`) still carry donor values (`tobiash.net`, `op://Pulumi/...`, Synology endpoints) and have not been previewed.
5. Nodes 2 and 3 are unmapped; Phase 1 is explicitly non-HA. The API endpoint `10.10.8.1` must become a load-balanced VIP before Phase 3 (ADR-0008). Increase Longhorn replicas after node 2 joins.
6. Public exposure: static IPv4 with Caddy on OPNsense (ADR-0011).
7. sshd on `k0s0` still allows password authentication globally.
8. Housekeeping: after the PR stack merges, delete the merged branches (`git branch -d`, refuses unmerged work) and sync `main`. Decide whether `docs/.obsidian/` is tracked or ignored (it is neither today; 31 untracked files); set the primary MAC on the `enp6s0` interface in NetBox (cosmetic); add a Longhorn mount check (`findmnt /var/lib/longhorn`) to a runbook; optionally disable Mimir's `usage_stats` (its reports to `stats.grafana.org` resolve to `0.0.0.0` and log `connection refused` every minute).

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
- Object-store trouble on the NAS shows as CNPG backups failing with `NoSuchUpload ... bucket does not exist`. Diagnose with an on-demand plugin backup, `ContinuousArchiving` and `pg_stat_archiver`; retried WAL files catch up by themselves.
- Paperless holds real data (a scanned document, id 2). The live delete-and-restore test is no longer safe; use the scratch-instance disaster-recovery test in `.okf/paperless.md`.
- Full list: `.okf/operational-lessons.md`.

## Starter prompt for the next session

```text
Continue the bare-metal k0s homelab work. Read HANDOFF.md, AGENTS.md, and .okf/index.md first, and run the donor pull (`scripts/pull-donors`, or the `git show chore/pull-donors:...` form in the Git row until PR #18 merges; donors move daily). Check the CloudNativePG base backups of the last night (`kubectl get backup.postgresql.cnpg.io -A`; they ran at 21:00 UTC) and the `paperless-backup` CronJob. The cluster has a verified PostgreSQL pilot (scheduled backups, restore and time-targeted PITR), a verified Longhorn restore, a running LGTM observability stack with 9 dashboards, 16 alert rules and Pushover alerting at https://g.4jp.de (ADR-0019), and Paperless 3.3.1 at https://paperless.4jp.de (ADR-0020, ADR-0021, `.okf/paperless.md`; CloudNativePG database, restic to an off-site Nextcloud, QNAP intake). It holds one real document and is backed up. Check on GitHub which of the stacked JP pull requests (#17, #19, #20, #21, docs PR on top) and the independent #18 and #22 have merged, and retarget the rest. Next: finish Paperless single sign-on once the user has merged AX41 PR #97, created the Authentik application and the 1Password item `Paperless OIDC` (check both first; on 2026-10-17 neither existed); the code change adds the OIDC settings, group sync and the `paperless-admins` superuser mapping, keeps local login, and needs the Paperless group `paperless` created. The encrypted off-site HBS 3 backup and restore test is deferred until the remote NAS is back online; it still gates other applications. After 2026-10-25 (DST) move the CloudNativePG schedule to `0 0 22 * * *`. Ask before destructive actions, preview before applies, record decisions in ADRs and insights in .okf, stage explicit file paths only, and warn before any command that may require biometric approval.
```
