# Handoff: bare-metal k0s homelab

Last session: 2026-10-11. Knowledge lives in `.okf/` (start at `.okf/index.md`) and decisions in `docs/08-Decisions/` (ADR-0004 to ADR-0015). Read `AGENTS.md` first.

## Where things stand

| Area | State |
| --- | --- |
| Cluster | k0s `v1.36.4+k0s.1` on `k0s0` (`10.10.8.1/16`, VLAN 10), one controller+worker, no taints, API `https://10.10.8.1:6443` |
| Node access | `k0sctl@10.10.8.1` with the agent-held `k0s` key and passwordless sudo; `alten` is for humans only |
| Kubernetes stack | `jaypee-solutions/kubernetes/prod` applied, 112 resources, `pulumi preview --expect-no-changes` clean |
| Add-ons | MetalLB (`10.10.88.1`-`.250`), NFS CSI, cert-manager (DNS-01 via Cloudflare), Traefik at `10.10.88.1`, CloudNativePG operator, OpenEBS LVM LocalPV, Longhorn 1.13.0 (1 replica, default StorageClass `longhorn`) |
| TLS / DNS | Wildcard `*.4jp.de` issued by Let's Encrypt; dnsmasq record `k8s-ingress-prod.4jp.de` via the OPNsense API |
| Storage | `postgres` VG on the WDC 256 GB NVMe (StorageClass `openebs-lvm-postgres`); Kingston 1 TB NVMe is ext4 at `/var/lib/longhorn` for Longhorn (ADR-0014), no backup target yet |
| Repo | On `main` via PRs #3 and #4. `svn`, `obsidian`, `ollama`, `ingress`, `s3` (MinIO) workspaces removed; `monitoring`, `backup`, `iot`, `n8n`, `paperless` remain. `services/paperless` and `services/monitoring` `Pulumi.prod.yaml` are intentionally untracked (donor-encrypted values) |
| Inventory | `k0s0` is documented in NetBox (device, `enp6s0` with MAC, `10.10.8.1/16`, platform Ubuntu 24.04), verified 2026-10-11; nodes 2 and 3 need the same records once mapped |
| Security | OPNsense API user holds only "Services: Dnsmasq DNS/DHCP: Settings" (verified: Unbound returns 403) |

## Working in this repo

- Enter the directory with direnv. `.envrc` asks for one biometric approval, then loads `OP_SERVICE_ACCOUNT_TOKEN`, `OPNSENSE_*`, and writes `KUBECONFIG` to `.direnv/kubeconfig`. `kubectl`, `k9s`, and `helm` then work. Warn the user before the first load and before the first SSH use of the `k0s` key (1Password agent).
- Git: `main` changes only through feature-branch PRs. Pre-commit hooks scan the whole directory, so untracked files can block a commit. Never commit APM-managed skills (`.agents/skills/`, `.claude/skills/`); `apm.yml` and `apm.lock.yaml` are tracked.
- Pulumi: `cd services/kubernetes && pulumi preview --stack prod`. Do not interrupt `pulumi up`; clear leftovers with `pulumi refresh --clear-pending-creates`. A preview can fail on a transient chart download from `github.com`; retry before assuming drift.
- Node changes go in `services/k0s` (`k0sctl/cluster.yaml`, `ansible/`); cluster add-ons go in Pulumi.
- NetBox (`https://netbox.4jp.de`, NetBox 4.2): `nbcli` is configured in `~/.nbcli/user_config.yml`; its Python (`~/.local/share/uv/tools/nbcli/bin/python`) has `pynetbox`.
- Checks: `uv run ./scripts/run-all-checks.sh` (needs `alloy` from brew), `uv run /Users/alten/.agents/skills/okf-validate/scripts/okf_validate.py .okf --strict`.
- Secrets: all in the `Homelab` vault, `my.1password.eu`. Pulumi's resolver looks items up by title; the `op` CLI needs the item ID for `Cloudflare [4jp.de]` (`b6i34pfgjitlzneedilxq47lxa`).

## Open items (in suggested order)

1. Confirm the ACME contact email: `support@jaypee.solutions` in `services/kubernetes/Pulumi.prod.yaml` (earlier notes said `github@jaypee.solutions`).
2. Choose the backup target for Longhorn and PostgreSQL, record it as an ADR, then add Longhorn backup settings and recurring jobs to the Kubernetes stack (preview first). MinIO is removed (ADR-0015); IDrive E2 is already used by `backup` and `paperless`, NFS is another option. Longhorn runs with one replica, so there is no redundancy until this exists.
3. First CloudNativePG database cluster on `openebs-lvm-postgres`, then the Paperless database migration.
4. Map the donor values of the `paperless`, `n8n`, `monitoring`, `backup`, and `iot` stacks (`tobiash.net`, `op://Pulumi/...`, Synology endpoints); none has been previewed. Preview each after mapping and track its `Pulumi.prod.yaml`.
5. Nodes 2 and 3 are unmapped; Phase 1 is explicitly non-HA. Map them, add their NetBox records, raise Longhorn `replica-count` in `Pulumi.prod.yaml`, and turn the API endpoint `10.10.8.1` into a load-balanced VIP before Phase 3 (ADR-0008).
6. Public exposure: static IPv4 with Caddy on OPNsense. If Caddy can run the DNS challenge, certificates stay in the cluster; otherwise TLS terminates in Caddy (ADR-0011).
7. sshd on `k0s0` still allows password authentication globally.
8. Housekeeping: delete merged local branches (`claude/unruffled-perlman`, `docs/netbox-k0s0`, `docs/handoff-next-session`, `feature/track-k0s-services`, `jp/action`) and review the stale remote branches `origin/feat/workspace-foundation` and `origin/jp/action`; decide whether `docs/.obsidian/` is tracked or ignored; set the primary MAC on the `enp6s0` interface in NetBox (cosmetic); add a Longhorn mount check (`findmnt /var/lib/longhorn`) to a runbook.

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
- Full list: `.okf/operational-lessons.md`.

## Starter prompt for the next session

```text
Continue the bare-metal k0s homelab work in this repository. Read HANDOFF.md, AGENTS.md, and .okf/index.md first, then summarize the current state in five lines.

Start with the open items in this order:
1. Ask me to confirm the ACME contact email in services/kubernetes/Pulumi.prod.yaml, and change it if needed.
2. Help me choose the backup target for Longhorn and PostgreSQL (present the options with tradeoffs), record the decision as an ADR, then add Longhorn backups to the Kubernetes Pulumi stack (preview first).
3. Then deploy the first CloudNativePG database cluster on the openebs-lvm-postgres StorageClass.

Rules: ask before destructive actions, never guess hostnames, IPs, or disk serials, preview before every apply, record decisions as ADRs, and persist knowledge in .okf. Every change goes through a feature branch and a PR; never commit APM-managed skills. Enter the repo through direnv so KUBECONFIG and the 1Password service account are loaded; warn me before any command that needs a biometric approval.
```
