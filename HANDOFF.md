# Handoff: bare-metal k0s homelab

Last updated: 2026-10-13. Knowledge lives in `.okf/` (start at `.okf/index.md`) and decisions in `docs/08-Decisions/` (ADR-0004 to ADR-0018). Read `AGENTS.md` first.

## Where things stand

| Area | State |
| --- | --- |
| Cluster | k0s `v1.36.4+k0s.1` on `k0s0` (`10.10.8.1/16`, VLAN 10), one controller+worker, no taints, API `https://10.10.8.1:6443` |
| Node access | `k0sctl@10.10.8.1` with the agent-held `k0s` key and passwordless sudo; `alten` is for humans only |
| Kubernetes stack | `jaypee-solutions/kubernetes/prod` applied, 133 resources; preview clean after the CNPG backup compatibility update |
| Add-ons | MetalLB (`10.10.88.1`-`.250`), NFS CSI, cert-manager (DNS-01 via Cloudflare), Traefik at `10.10.88.1`, CloudNativePG operator and Barman plugin, OpenEBS LVM LocalPV, Longhorn 1.13.0 (1 replica, default StorageClass `longhorn`) |
| TLS / DNS | Wildcard `*.4jp.de` issued by Let's Encrypt; dnsmasq record `k8s-ingress-prod.4jp.de` via the OPNsense API |
| Storage | `postgres` VG on the WDC 256 GB NVMe (`openebs-lvm-postgres`); Kingston 1 TB NVMe is ext4 at `/var/lib/longhorn` for Longhorn. Both have QuObjects backup targets; PostgreSQL base+WAL and Longhorn disposable backup restores succeeded (ADR-0016, ADR-0017). The temporary PostgreSQL restore Cluster/PVC/PV was deleted after explicit approval. |
| Repo | `svn`, `obsidian`, `ollama`, `ingress`, `s3` (MinIO) workspaces removed; `monitoring`, `backup`, `iot`, `n8n`, `paperless` remain |
| Git | Longhorn backup PR #8 and CloudNativePG pilot PR #9 are merged; local `main` was fast-forwarded to `origin/main` on 2026-10-12. Further edits belong on feature branches and go through PRs. |
| Inventory | `k0s0` is documented in NetBox (device, `enp6s0` with MAC, `10.10.8.1/16`, platform Ubuntu 24.04), verified 2026-10-11; nodes 2 and 3 need the same records once mapped |

## Working in this repo

- Enter with direnv. `.envrc` loads `OP_SERVICE_ACCOUNT_TOKEN`, `OPNSENSE_*`, and writes the admin `KUBECONFIG` to `.direnv/kubeconfig`. Warn before commands that might request biometric approval.
- Pulumi: from `services/kubernetes`, run `direnv exec ../.. pulumi preview --stack prod --non-interactive` before every `pulumi up`; do not interrupt updates.
- Node changes go in `services/k0s` (`k0sctl/cluster.yaml`, `ansible/`); cluster add-ons go in Pulumi.
- Checks: `uv run ./scripts/run-all-checks.sh`, `uv run /Users/alten/.agents/skills/okf-validate/scripts/okf_validate.py .okf --strict`. Ruff has one existing `PLW0108` finding in `paperless.py`.
- Secrets: all in the `Homelab` vault, `my.1password.eu`. Pulumi's resolver looks items up by title; the `op` CLI needs the item ID for `Cloudflare [4jp.de]` (`b6i34pfgjitlzneedilxq47lxa`).

## Open items

1. The first scheduled CloudNativePG backup ran (`postgres-pilot-backup-20261013030000`, completed 2026-10-13 03:00 UTC). Longhorn's scheduled job has not been exercised: no Longhorn volumes exist yet. Verify it with the first real Longhorn workload volume.
2. ADR-0018 (accepted): time-targeted PITR is **verified** on the pilot (2026-10-13) and its temporary restore Cluster/PVC/PV were removed with explicit approval. The encrypted HBS 3 off-site backup and restore are deferred by the user and must pass before any application migration.
3. Other stacks still carry donor values (`tobiash.net`, `op://Pulumi/...`, Synology endpoints); none has been previewed. Each needs a JP mapping first. Paperless migration is not started.
4. Nodes 2 and 3 are unmapped; Phase 1 is explicitly non-HA. The API endpoint `10.10.8.1` must become a load-balanced VIP before Phase 3 (ADR-0008). Increase Longhorn replicas after node 2 joins.
5. Public exposure: static IPv4 with Caddy on OPNsense (ADR-0011).
6. sshd on `k0s0` still allows password authentication globally.

## Gotchas

- `op` prompts time out when run headless; use the service account. Never write secrets to 1Password from Pulumi (the service account is read-only).
- The LAN resolver is authoritative for `4jp.de`, so ACME self-checks use public nameservers (configured in `certmanager.py`).
- Delete PVCs before uninstalling the OpenEBS driver, otherwise logical volumes and kubelet mounts are orphaned.
- Volume expansion needs a pod restart.
- Never address disks by `/dev/...` names; use by-id paths and serials.
- k0sctl needs all three host key types of `10.10.8.1` in `known_hosts`.
- Full list: `.okf/operational-lessons.md`.

## Starter prompt for the next session

```text
Continue the bare-metal k0s homelab work. Read HANDOFF.md, AGENTS.md, and .okf/index.md first. Longhorn backups (PR #8) and the CloudNativePG pilot (PR #9) are merged into local `main`. The pilot has a verified scheduled backup, a base-backup-plus-WAL restore, and a time-targeted PITR restore (ADR-0018); the temporary restore resources were removed with explicit approval. Next: the encrypted off-site HBS 3 backup and restore test (needs the user on the QNAPs), then plan the Paperless migration. Ask before destructive actions, preview before applies, record decisions in ADRs and insights in .okf, and warn before any command that may require biometric approval.
```
