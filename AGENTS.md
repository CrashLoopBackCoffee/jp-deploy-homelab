# Agent Instructions for deploy-homelab

This document provides guidance for AI assistants working with code in this repository.

## Project Overview

This is a Kubernetes-focused homelab infrastructure-as-code project. Pulumi with Python manages Kubernetes add-ons and workloads on k0s, which is planned for bare-metal nodes and bootstrapped externally with k0sctl. Existing Proxmox VMs and UniFi remain outside this repository; Immich runs on the QNAP. Cloudflare provides DNS for `4jp.de` (including DNS-01 certificates) but not ingress; public exposure will go through Caddy on OPNsense.

The project follows a microservices architecture with each service in its own workspace. It emphasizes code quality, using tools like `ruff` for linting and `pyright` for type checking.

### Pet vs Cattle

Infrastructure is divided into two categories:

- **Pets** — long-lived, high-touch systems managed with **Ansible** or **k0sctl**: OPNsense, network switches, and the bare-metal k0s cluster bootstrap.
- **Cattle** — reproducible Kubernetes workloads managed with **Pulumi (Python)**.

Never use OpenTofu or Terraform. Pulumi is the exclusive IaC tool for cattle.

## Project Structure

### Core Architecture

- **Language**: Python 3.11+
- **Infrastructure**: Pulumi (Infrastructure as Code)
- **Package Management**: UV (Python package manager)
- **Environment Management**: Multiple Pulumi stacks (dev, test, prod)

### Service Organization

```
services/
├── backup/           # Restic and Rclone backup management
├── k0s/              # k0sctl bootstrap configuration and Ansible node storage preparation
├── kubernetes/       # Kubernetes add-ons and workloads on k0s
├── n8n/              # n8n service
├── paperless/        # Document management system
```

### Additional Repository Structure

- **`docs/`**: Contains example code and documentation for common patterns (e.g., `cnpg_postgres.py`)
- **`utils/`**: Shared utility modules for common functionality across services
- **`dockerhost`** (legacy Docker host `192.168.178.125`) was decommissioned on 2026-11-06 (ADR-0054): powered off, disk kept as cold fallback, archive on the QNAP share `backups/dockerhost`; its Ansible repo `/Users/alten/Documents/dockerhost` is kept read-only as history. `~/GitHub/stefan_raspberry` is not part of this homelab; never use it for homelab work.
- **`scripts/`**: Helper scripts for development and maintenance
- **`renovate.json5`**: Automated dependency update configuration

## Critical Development Rules

### 1. Shell Commands
Run commands in another directory with the bash tool's `cwd` parameter or a subshell, `(cd foo && command)`; the shell session keeps its working directory.

### 2. Code Quality & Linting
- **ALWAYS** run `uv run ./scripts/run-all-checks.sh` before making any commit to ensure code quality.
- **CRITICAL**: Run linting checks BEFORE manually fixing any code issues - many linters auto-fix problems automatically.
- The project uses multiple linting tools configured via pre-commit:
  - **Ruff**: Python code formatting (`ruff format`) and linting (`ruff check --fix`).
  - **Pyright**: Python type checking.
  - **Yamllint**: YAML file linting.
  - **Pre-commit hooks**: Various file checks (TOML, whitespace, etc.).
  - **Alloy format**: Grafana Alloy configuration formatting.
- **NEVER** commit code that fails linting checks.

### 3. Pulumi Commands & Safety

See the **`pulumi-operations`** skill for safety rules, all deployment commands, stack management, and resource rename patterns.

A preview that shows changes you did not make (another PR merged meanwhile): apply your own resource with `--target <urn>` and report the rest. See "Pulumi preview drift" in `.okf/operational-lessons.md`.

### 4. Python Code Style

See the **`python-pulumi-patterns`** skill for import conventions, type annotation rules, `LocalBaseModel` config patterns, and Kubernetes typed-dict notation.

### 5. Container Image Management

See the **`container-image-management`** skill for version field patterns, renovate annotation formats (github-releases, helm, endoflife-date), and config model conventions.

### 6. Helm Chart Management

See the **`helm-chart-management`** skill for the Chart vs Release decision rule, hook detection, and code examples.

### 7. Git Workflow
- Every change must happen on a feature branch and be performed via pull request.
- Use descriptive branch names (e.g., `feature/add-prometheus-monitoring`).
- Use `hub sync` to keep branches clean.
- Never commit directly to the main branch.

### 8. Kubernetes

See the **`python-pulumi-patterns`** skill for Kubernetes typed-dict notation and CPU limit rules.

### 9. Donor Repositories

`mp-deploy-homelab` and `th-deploy-homelab` (sibling directories of this repository) are the reference for new work, and they change daily. **Run `scripts/pull-donors` at least once a day and before reading them.** It fast-forwards both on `main`, skips any that are dirty or on another branch, and lists the changed services and commits. Never judge a donor from a stale clone: on 2026-10-15 an outdated clone hid MP's Paperless client blueprint for Authentik and TH's working Paperless 3.x settings.

### 10. Home Assistant Repository

Home Assistant is configured in `/Users/alten/GitHub/deploy-home-assistant` (its own repo, outside this one). **Whenever a task touches Home Assistant** (automations and alerts, entities, integrations, MQTT, the `prometheus:` allowlist `config/prometheus_entities.yaml`, dashboards that read HA entities, Shelly/MyPV/Solax devices, HA network or firewall), check that repo first and make HA-side changes there, never only here:

- Read its `AGENTS.md`, `HANDOFF.md`, `.okf/` and `docs/adr/` before concluding what HA does or does not do. Its ADRs are numbered separately from this repo's; cross-reference both ways (example: ADR-0046 here, commits in the HA repo).
- `git -C /Users/alten/GitHub/deploy-home-assistant pull --ff-only` before reading, if the clone is clean and on `main`. Never judge HA from a stale clone or from this repo's OKF alone: on 2026-11-05 this repo's OKF still listed `ZweiradGarage` and `WarmWaterOutage` as legacy-only although HA had owned them since 2026-11-03.
- Its changes follow its own workflow (`just check`, `just doctor`, drift guard). Use its `just` recipes for HA state, logs and deploys (`just states`, `just logs`, `just ssh`).
- Its remote is Forgejo (`code.jaypee.solutions`), not GitHub: `gh` does not work there, and no PR tool or token was found on 2026-11-06 (its history is direct commits to `main`). Push the branch and ask the user to open the PR.
- Changes that cross both repos (a new archived entity, a renamed sensor, an alert moved to HA) land as one branch per repo with a link in each description.

## Common Commands

`uv run ./scripts/generate-config-schema` regenerates the config schemas; `uv sync` and `uv add <package>` manage dependencies.

## Environment Management (Pulumi Stacks)

- **Production (`prod`)**: Primary homelab environment for most services.
- **Development (`dev`)**: Legacy service configurations.
- **Test (`test`)**: Experimental environment, especially for `kubernetes` changes.

## AI Assistant Guidelines

1.  **🚨 CRITICAL - Pulumi Safety**: See the **`pulumi-operations`** skill — always preview before deploying.
2.  **🚨 CRITICAL - Code Quality**: **ALWAYS** run `uv run ./scripts/run-all-checks.sh` before committing.
3.  **Understand Service Context**: Each service in `services/` is self-contained but may have dependencies.
4.  **Follow Patterns**: Use the topic-specific skills for Pulumi, container images, Helm, and Python code style.
5.  **Configuration**: Remember to configure python runtime options in `Pulumi.yaml` using `uv` and the `venv` in the root of the repository.
6.  **Preflight**: before a plan that touches several systems goes to the user, probe write access to each target (see "Preflight external access" in `.okf/operational-lessons.md`).
