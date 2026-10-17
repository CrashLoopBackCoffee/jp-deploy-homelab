---
tags:
  - homelab
  - adr
  - kubernetes
  - observability
  - migration
type: adr
status: accepted
date: 2026-10-17
created: 2026-10-17
updated: 2026-10-17
adr: 25
---

# ADR-0025 - Probe and scrape targets from 1Password

## Status

Accepted on 2026-10-17 and **applied the same day**, after two corrections (see the first-apply consequence below): all 33 probes succeed, `ax51` and `pretix` are scraped, ICMP works from a pod without extra privileges.

## Context

Phase 2 of [[ADR-0023 - Retire the legacy dockerhost monitoring stack]] moves the internet-facing probes and scrapes of the legacy Prometheus into Alloy: 27 website probes, one slow probe, three ICMP and two TCP probes, three AX51 endpoints and one Pretix endpoint. About 20 of the probed sites are customer domains, and this repository is public. The user decided that the target list must not be in git.

The legacy values came from an Ansible vault (the two basic-auth passwords) and from `prometheus.yml`. Alloy's embedded blackbox exporter accepts targets from `discovery.file`, which re-reads a changed file without a restart.

## Decision

- **Everything about the targets lives in three 1Password items** in the `Homelab` vault: the Secure Note `Monitoring Targets` (one `<group> <target>` per line; groups `http`, `slow`, `icmp`, `tcp`, `ax51`, `pretix`) and the Logins `Prometheus AX51 Scrape` and `Prometheus Pretix Scrape` (username and password).
- **Pulumi reads them and writes one Secret**, `alloy-targets` (`observability/targets.py`), with a fixed name so that Kubernetes updates the mounted files in place. Alloy mounts it read-only, so `config.alloy` contains no target or credential and stays reviewable.
- **Probes** use `discovery.file`, then `prometheus.exporter.blackbox`, then a relabel step that sets `instance` to the probed address and `job` to the legacy job names (`blackbox`, `blackbox-slow`, `blackbox-icmp`, and `blackbox-tcp` for the former `check_teamspeak`). Two scrape components keep the legacy intervals (60 s and 120 s). `ax51` (30 s) and `pretix` (60 s) are scraped over HTTPS with basic auth read from the mounted files.
- **Three alert rules** are ported: `probe-failing` (10 minutes, and it also alerts when there are no probe series at all), `probe-failing-slow` (15 minutes) and `probe-certificate-expiring` (7 days). The generic `Scrape target down` rule already covers `ax51` and `pretix`.
- The shared 1Password resolver gets `note_value`, the Secure Note content, as a standard field. Its former `notes` field could never work: the provider exposes no such attribute.
- Not migrated here: five local `*.4jp.de` probes and two LAN probes (deferred with the LAN work), the legacy node-exporter, cAdvisor, Watchtower and Fritz targets.

## Consequences

- Changing a target is an edit of the Secure Note, followed by a Pulumi run (the Secret is rewritten, Alloy re-reads it within about a minute); it is not a reviewable code change.
- The note is parsed strictly: an unknown group or a line without a target fails the Pulumi run instead of silently dropping a probe.
- Pulumi marks the 1Password values as secrets, so a preview shows `[secret]` for the Secret's content; the Alloy config diff stays visible.
- ICMP probes from a pod need either `NET_RAW` or an allowed unprivileged ping socket; whether they work is verified after the first apply, and a failing module is replaced by HTTP or TCP probes rather than given extra privileges.
- During the dual run both the legacy Prometheus and Alloy alert on the same targets; migrated jobs are removed from the legacy Prometheus when they are cut over.
- **First apply, 2026-10-17:** the Secret and the Grafana rules were applied, but the new Alloy pod crash-looped with `too many open files` (the per-user inotify instance limit of 128 on `k0s0` was exhausted), and the run was killed at the tool's 290 s limit. The old Alloy pod kept serving. Alloy's Helm release was rolled back to its last deployed revision and a 3-hour Grafana silence covered `Website or service probe failing`, which alerts on no data and had no probes yet. The fix is the kernel setting in `services/k0s/ansible/tune-kernel-inotify.yaml` (1024 instances), to be run by the user because the SSH key sits behind a 1Password approval; the credential files are also polled instead of watched.

## Alternatives considered

- **Targets in `Pulumi.prod.yaml`:** reviewable and simple, but publishes the customer list.
- **Own targets in the repository, customer domains in 1Password:** the recommended split, declined by the user in favour of one place.
- **A Kubernetes Secret created by hand:** outside code and not reproducible.
- **Rendering the targets into the Alloy config through Helm values:** Pulumi would show the whole config diff as `[secret]`, and every change would restart Alloy.

## Related notes

- [[ADR-0023 - Retire the legacy dockerhost monitoring stack]]
- [[ADR-0024 - QNAP syslog into Loki]]
- [[ADR-0013 - 1Password service account for Pulumi]]
