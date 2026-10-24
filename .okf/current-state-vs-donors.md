---
type: Repository Review
title: JP current state versus adjacent donor repositories
description: Captures integration and reliability findings from comparing the JP worktree with adjacent MP and TH homelab repositories.
timestamp: 2026-10-03T00:00:00Z
tags: [homelab, repository-review, pulumi, migration]
---

# Scope

Compared the current `jp-deploy-homelab` worktree with the adjacent `mp-deploy-homelab` and `th-deploy-homelab` repositories. JP's service layout is closer to TH's than MP's, but JP is not a current mirror of either donor: the service implementations and deployment configurations differ. MP uses a distinct workspace shape, including `observability` where JP/TH use `monitoring`.

At review time, the JP service tree, workspace manifests, scripts, utilities, and environment bootstrap were untracked; only documentation changes were tracked modifications. These findings describe the current worktree, not a committed change set.

# Findings

## Production environment values still need the JP mapping

JP's active network baseline documents `4jp.de`. The Kubernetes stack is now mapped for JP: zone `4jp.de`, a Cloudflare account token from the `Homelab` vault (`docs/08-Decisions/ADR-0010 - Cloudflare account token for the Kubernetes stack.md`), ACME email `github@jaypee.solutions` (the git identity; not confirmed as the desired contact), and MetalLB pool `10.10.88.1`–`10.10.88.250` (chosen by the user). `.envrc` loads a read-only 1Password service account token (item `Pulumi Service Account`, `docs/08-Decisions/ADR-0013 - 1Password service account for Pulumi.md`) plus the OPNsense API key and secret into environment variables on entering the repository, at the cost of one biometric approval. OPNsense is `https://router.4jp.de` with the `Homelab` item `OPNsense` (username is the API key, password is the API secret). Local DNS records are dnsmasq host records, not Unbound overrides (`docs/08-Decisions/ADR-0012 - Local DNS records through dnsmasq on OPNsense.md`); the API user needs the privilege "Services: Dnsmasq DNS/DHCP: Settings". The other stacks (paperless, n8n, monitoring, s3, backup, iot) still contain donor values (`tobiash.net`, `op://Pulumi/...`, Synology endpoints).

The Kubernetes Pulumi stack consumes the kubeconfig from the `op://Homelab/Kubeconfig prod/password` item, as do the backup, iot, and paperless stacks. It was moved from the donor's `Pulumi` vault to the user's `Homelab` vault on 2026-10-10; other `op://Pulumi/...` references (Cloudflare, Restic, Mosquitto, and others) were not migrated. k0sctl's output is published to that item manually. Before the first Pulumi update, inspect the old Kubernetes stack state: the previous program declared a Pulumi-managed OnePassword item, and removing it from the program could otherwise plan deletion of the shared item.

## Immich remains external on QNAP

The user confirmed Immich already runs on the QNAP and should remain there. The Immich Pulumi workspace and its Kubernetes/NFS configuration were removed from this repository. `PostgresDatabase` was used only by Immich and is also removed; Paperless still uses `utils.postgres.create_postgres`. No Immich deployment, data movement, or Pulumi state operation was performed.

## Bare-metal k0s and external infrastructure scope

The k0s cluster is planned for bare-metal nodes. k0sctl owns bootstrap and lifecycle outside Pulumi; the Kubernetes Pulumi stack consumes the shared kubeconfig and manages platform add-ons. Proxmox management, the UniFi Pulumi workspace, and the unused Z-Wave VM/configuration were removed. Existing Proxmox VMs and UniFi remain external and were not changed. The monitoring legacy remote-Docker workspace is retained; the Obsidian, Ollama, Subversion, and Cloudflared-ingress workspaces were removed on 2026-10-10 (`docs/08-Decisions/ADR-0011 - LAN-first ingress and service cleanup.md`), and the S3/MinIO workspace on 2026-10-11 (`docs/08-Decisions/ADR-0015 - Remove MinIO and the s3 workspace.md`).

The target topology is now three bare-metal k0s controller+workers plus one separate Proxmox host; the rollout and HA gates are captured in the [k0s cluster plan](./k0s-cluster-plan.md). Exact host mapping, specifications, disk inventory, and addressing remain open. No hardware operation or deployment was performed.

## Workspace scope was clarified

The root workspace now excludes the removed Immich, Proxmox, and UniFi packages and the Proxmox provider. IoT remains Kubernetes-only for Mosquitto and MQTT-to-Prometheus; Z-Wave settings and scrape targets are removed. The root workspace keeps the unrelated remote-Docker service packages by explicit scope choice.

## Paperless secondary backup failures now fail the job — resolved

The IDrive backup and maintenance paths previously suppressed command failures and could still log success. Secondary failures now make the CronJob fail, successful completion is logged only after success, and primary maintenance still runs. The README now tells operators to alert on CronJob failures.

## Restic repository initialization now distinguishes missing repositories — resolved

Paperless now checks repository configuration, initializes only on Restic's missing-repository exit code, reports other access errors, and unlocks stale locks. Smoke runs covered a non-initialization access error, the missing-repository initialization path, and a failed secondary backup.

## 1Password bootstrap selects an installed CLI — resolved

`.envrc` now uses native `op` when available and retains `op.exe` as a fallback. `bash -n .envrc` passed on the Darwin workstation.

# Verification

- `uv lock` resolved 57 packages and removed the Immich, Proxmox, and UniFi workspaces and their exclusive dependencies; `uv sync --locked` passed.
- `uv run ./scripts/generate-config-schema` regenerated schemas for all 11 remaining configured stacks.
- The IoT smoke run parsed `services/iot/Pulumi.prod.yaml` with `PulumiConfigRoot`, validated the shared kubeconfig reference, and retained the Shelly and Zigbee exporters without Z-Wave instances.
- `uv run --locked pyright --warnings` passed with 0 errors, warnings, or information messages.
- Targeted Ruff lint and formatting passed for the four changed Python modules; `yamllint` passed for the changed IoT/Paperless/workflow YAML.
- Strict OKF validation passed with no errors or warnings.
- Full Ruff lint still reports four baseline diagnostics: Obsidian `PLC0207` and Paperless `PLW0108` in the main tree and the untouched `docs/.claude/worktrees` copy. Full format check reports 20 existing files needing formatting; changed Python files pass targeted checks.
- `pytest` was not run: the repository has no `tests/` directory, and the prior `uv run --locked pytest` attempt could not start because pytest is not installed.
- No Pulumi preview, deployment, or state operation was run. Existing Proxmox VMs and UniFi remain unchanged; bare-metal node inventory/addressing and any old-stack state review remain open.

# Citations

- JP addressing baseline: `docs/01-Foundation/Addressing and Domains.md`.
- JP IaC decision record: `docs/08-Decisions/ADR-0003 - Pet vs Cattle and IaC tooling.md`.
- [k0s directory defaults](https://docs.k0sproject.io/head/directories/)
- [JP root workspace manifest](../pyproject.toml)
- [JP lockfile](../uv.lock)
- [JP environment bootstrap](../.envrc)
- [JP Kubernetes entrypoint](../services/kubernetes/__main__.py)
- [JP Kubernetes stack configuration](../services/kubernetes/Pulumi.prod.yaml)
- [JP NFS CSI chart configuration](../services/kubernetes/kubernetes/csi_nfs.py)
- ADR-0004: `docs/08-Decisions/ADR-0004 - Bare-metal k0s and external infrastructure scope.md`
- JP hardware inventory: `docs/01-Foundation/Hardware Inventory.md`
- [JP IoT stack configuration](../services/iot/Pulumi.prod.yaml)
- [JP IoT configuration model](../services/iot/iot/config.py)
- [JP Postgres helper](../utils/src/utils/postgres.py)
- [JP Paperless backup orchestration](../services/paperless/paperless/backup.py)
- [TH Paperless backup orchestration](../../th-deploy-homelab/services/paperless/paperless/backup.py)
