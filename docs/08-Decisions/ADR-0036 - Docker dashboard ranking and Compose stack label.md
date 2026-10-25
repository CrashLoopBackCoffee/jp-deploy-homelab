---
tags: [homelab, adr, observability, grafana, docker, alloy]
type: adr
status: accepted
date: 2026-10-25
created: 2026-10-25
updated: 2026-10-25
adr: 36
---

# ADR-0036 - Docker dashboard ranking and Compose stack label

## Status

Accepted on 2026-10-25. Builds on the label drop of [ADR-0026](ADR-0026%20-%20Mimir%20series%20budget%20and%20API%20server%20buckets.md).

## Context

The `Docker containers` dashboard (AX51 cAdvisor, job `ax51`) did not show which containers cause the most load. `topk(15, …)` ranks at every step, so over 6 hours the CPU panel drew 29 lines, memory 22, network 25 and memory pressure 28, with unsorted legends. There was no ranking view, no host context (16 cores, 64 GiB) and no grouping by Compose stack (mailcow alone is 18 small containers). Network panels were topped by host-network containers (`minecraft-minecraft-1`, `node-exporter`, mailcow netfilter), which report every host interface. There are no per-container disk I/O series (no blkio or filesystem series) and `container_pressure_io_*` is 0 for every container.

## Decision

- Rank over the whole dashboard range: `_ranked` keeps the k series with the highest mean via `and on (…) topk(k, avg_over_time((expr)[$__range:$__interval] @ end()))`. A chart then keeps the same k lines at every step; legends are tables of mean and max sorted by mean.
- A ranking table lists every container over the selected range (CPU as a share of host cores, memory, memory of limit, network, CPU pressure) with data links that filter the dashboard.
- Host stats (CPU, memory, load per core) sit on top for context; stack-level CPU and memory panels use the new `stack` label.
- Network panels select `interface=~"eth[0-9]+"`: host-network containers are left out, their traffic is in the host node exporter.
- Alloy keeps `container_label_com_docker_compose_project` as `stack` before the `container_label_.+` drop; containers without Compose get their container name. One extra label stays well under Mimir's limit of 30.
- No disk panel: the series do not exist, and IO pressure is always 0.

## Consequences

- Alloy's relabel change re-creates about 11.3k `ax51` series once (new label set).
- Series from before the deploy have no `stack`; the variable's All value is `.*` so they still match. Until the range no longer reaches back before 2026-10-25 11:30 UTC, the table lists each container twice (with and without stack) and the stack panels show an extra empty-stack series that sums all containers.
- Range-ranked panels evaluate a subquery per refresh; acceptable on the current series count.

## Alternatives considered

- Plain `topk` with a smaller k: still ranks per step and drops short spikes.
- Grouping by `image` or name prefix: unreliable for Compose projects.
- Keeping all `container_label_*` labels: exceeds the 30-label limit (ADR-0026).

## Related

- [ADR-0026](ADR-0026%20-%20Mimir%20series%20budget%20and%20API%20server%20buckets.md)

## Verification

On 2026-10-25: every query of the 19 panels ran on live Mimir without error. Over 6 hours the CPU and memory panels return 10 series (29 and 22 with `topk`), the top-5 panels return 5, the table returns one row per container with `cadvisor-cadvisor-1` first, and the network panels contain none of the host-network containers. After `pulumi up` (ConfigMap `grafana-dashboards` replaced, Helm releases `grafana` and `alloy` updated, 24 unchanged), `stack` was present on all 71 containers (`mailcowdockerized` 19, `traefik`, `forgejo`, `pretix` as own stacks), series without `stack` were 0 after 10 minutes, `cortex_discarded_samples_total` did not increase and Alloy logged no `err-mimir`. The dashboard rendered in Grafana, and the container-name link set `var-name`.
