# Handoff: bare-metal k0s homelab

Last session: 2026-10-11. Knowledge lives in `.okf/` (start at `.okf/index.md`) and decisions in `docs/08-Decisions/` (ADR-0004 to ADR-0014). Read `AGENTS.md` first.

## Where things stand

| Area | State |
| --- | --- |
| Cluster | k0s `v1.36.4+k0s.1` on `k0s0` (`10.10.8.1/16`, VLAN 10), one controller+worker, no taints, API `https://10.10.8.1:6443` |
| Node access | `k0sctl@10.10.8.1` with the agent-held `k0s` key and passwordless sudo; `alten` is for humans only |
| Kubernetes stack | `jaypee-solutions/kubernetes/prod` applied, 112 resources, `pulumi preview --expect-no-changes` clean |
| Add-ons | MetalLB (`10.10.88.1`-`.250`), NFS CSI, cert-manager (DNS-01 via Cloudflare), Traefik at `10.10.88.1`, CloudNativePG operator, OpenEBS LVM LocalPV, Longhorn 1.13.0 (1 replica, default StorageClass `longhorn`) |
| TLS / DNS | Wildcard `*.4jp.de` issued by Let's Encrypt; dnsmasq record `k8s-ingress-prod.4jp.de` via the OPNsense API |
| Storage | `postgres` VG on the WDC 256 GB NVMe (StorageClass `openebs-lvm-postgres`); Kingston 1 TB NVMe is ext4 at `/var/lib/longhorn` for Longhorn (ADR-0014), no backup target yet |
| Repo | `svn`, `obsidian`, `ollama`, `ingress` workspaces removed; `s3`, `monitoring`, `backup`, `iot`, `n8n`, `paperless` remain |

## Working in this repo

- Enter the directory with direnv. `.envrc` asks for one biometric approval, then loads `OP_SERVICE_ACCOUNT_TOKEN`, `OPNSENSE_*`, and writes `KUBECONFIG` to `.direnv/kubeconfig`. `kubectl`, `k9s`, and `helm` then work.
- Pulumi: `cd services/kubernetes && pulumi preview --stack prod`. Do not interrupt `pulumi up`; clear leftovers with `pulumi refresh --clear-pending-creates`.
- Node changes go in `services/k0s` (`k0sctl/cluster.yaml`, `ansible/`); cluster add-ons go in Pulumi.
- Checks: `uv run ./scripts/run-all-checks.sh`, `uv run /Users/alten/.agents/skills/okf-validate/scripts/okf_validate.py .okf --strict`. Ruff has one existing `PLW0108` finding in `paperless.py`.
- Secrets: all in the `Homelab` vault, `my.1password.eu`. Pulumi's resolver looks items up by title; the `op` CLI needs the item ID for `Cloudflare [4jp.de]` (`b6i34pfgjitlzneedilxq47lxa`).

## Open items

1. Push `feature/track-k0s-services` (commits `4766a01`, `9d58b68`) and open the PR. `services/paperless` and `services/monitoring` `Pulumi.prod.yaml` are intentionally untracked (donor-encrypted values).
2. Remove the trial "Services: Unbound" privilege from the OPNsense API user in the UI (System > Access > Users). On 2026-10-11 the API key still read Unbound settings (HTTP 200); the key cannot read users, so this cannot be verified through the API.
3. Other stacks still carry donor values (`tobiash.net`, `op://Pulumi/...`, Synology endpoints); none has been previewed. Each needs a JP mapping first.
4. ACME contact email is `support@jaypee.solutions` in `services/kubernetes/Pulumi.prod.yaml` (earlier notes said `github@jaypee.solutions`); confirm or change it.
5. Longhorn is running; remaining work is a backup target and schedule, then a second replica once node 2 joins (raise `replica-count` in `Pulumi.prod.yaml`). Do not add a second snapshot controller; OpenEBS already installs one.
6. First CloudNativePG database on `openebs-lvm-postgres`, then the Paperless database migration.
7. Backups for Longhorn and PostgreSQL; decide whether `s3` (MinIO) is kept.
8. Nodes 2 and 3 are unmapped; Phase 1 is explicitly non-HA. The API endpoint `10.10.8.1` must become a load-balanced VIP before Phase 3 (ADR-0008).
9. Public exposure: static IPv4 with Caddy on OPNsense. If Caddy can run the DNS challenge, certificates stay in the cluster; otherwise TLS terminates in Caddy (ADR-0011).
10. sshd on `k0s0` still allows password authentication globally.

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
Continue the bare-metal k0s homelab work in this repository. Read HANDOFF.md, AGENTS.md, and .okf/index.md first, then summarize the current state in five lines.

Start with the open items in this order:
1. Check whether the repository is committed to git; if not, help me create a feature branch and commit services/ and the docs, following the Git workflow in AGENTS.md.
2. Confirm the OPNsense API user only has "Services: Dnsmasq DNS/DHCP: Settings".
3. Then prepare the Kingston NVMe for Longhorn with Ansible and add Longhorn to the Kubernetes Pulumi stack (preview first).

Rules: ask before destructive actions, never guess hostnames, IPs, or disk serials, preview before every apply, record decisions as ADRs, and persist knowledge in .okf. Enter the repo through direnv so KUBECONFIG and the 1Password service account are loaded; warn me before any command that needs a biometric approval.
```
