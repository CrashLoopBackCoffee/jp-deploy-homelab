---
tags:
  - homelab
  - adr
  - migration
  - dockerhost
  - observability
type: adr
status: accepted
date: 2026-11-05
created: 2026-11-05
updated: 2026-11-06
adr: 54
---

# ADR-0054 - Decommission dockerhost

## Status

Accepted on 2026-11-05; executed on 2026-11-06 (see the update at the end). Every destructive or service-stopping step (G1 to G6) waited for the user's explicit approval in chat. Completes stage 2 of [[ADR-0023 - Retire the legacy dockerhost monitoring stack]]. Open: Home Assistant entities `device_tracker.dockerhost` and `switch.dockerhost_internet_access`, and the HA pull request (see the update).

## Context

`dockerhost` (`192.168.178.125`, Ubuntu 22.04, ASRock board, 1 TB NVMe) is the last legacy bare-metal Docker host. It runs the legacy monitoring stack (Prometheus, Alertmanager, Grafana, Loki, Promtail, blackbox-exporter, cAdvisor, fritz-exporter), Traefik, Portainer and Watchtower. Mosquitto and mqtt2influxdb have been stopped since 2026-11-03. No backup of the host exists.

Findings on 2026-11-05:

- The only established connections are the workstation's SSH and internal container traffic. Traefik saw only blackbox self-probes and occasional Grafana views in the last 7 days. The legacy Loki holds only dockerhost's own logs.
- Cloudflare `4jp.de` has 10 hand-made A records to `192.168.178.125` (`alertmanager`, `blackbox-exporter`, `cadvisor`, `chat`, `grafana`, `loki`, `portainer`, `prometheus`, `mqtt2influxdb`, `adminer.tandoor`); none are in Pulumi.
- The Wazuh agent source range still allows `192.168.178.125/32`, but the only agents are `000`, `001 k0s0` and `003 ax51`.
- The legacy Prometheus holds 87 GB of history (2025-10-30 onward, 1 year retention). Mimir has no data before 2026-10-13. The oldest legacy block (`01KAFK8VR0AE76K04YY0D02DRP`, up to 2025-11-20) is deleted by retention on about 2026-11-20, so the Prometheus stop (G1) must happen before 2026-11-19.
- The legacy Prometheus is the only monitor of three probes that the replacement stack lacks: `https://tandoor.4jp.de`, `https://netbox.4jp.de`, `https://dev.kinderreich-augsburg.de`.

## Decision

- **Archive first.** All host state goes to the QNAP share `backups`, directory `dockerhost` (`/share/backups/dockerhost/`), by rsync over SSH to `qnap.4jp.de`. The user supplies the QNAP SSH user. Layout:
  - `host/`: `prometheus-tsdb.tar.zst`, `monitoring-other-data.tar.zst`, `opt-configs.tar.zst`, `home-alten.tar.zst`, `root.tar.zst`, `etc.tar.zst`, `var-log.tar.zst`, `etc-systemd-units.tar.zst`, `docker-images.tar.zst`, `inventory/` (docker, systemd, dpkg, network and disk listings, `restart-policies.txt`, `cloudflare-records.tsv`) and `MANIFEST.sha256`. `/opt/go`, `/opt/poetry`, `/home/alten/.cache` and `/home/alten/.vscode-server` are excluded as reproducible.
  - `workstation-legacy/`: the workstation's `~/dockerhost-legacy-*` files (about 6.1 GB) with a manifest.
  - `ansible/`: a git bundle of `/Users/alten/Documents/dockerhost`.
  - Every upload is verified with `sha256sum -c` on the QNAP before any later gate starts.
- **Prometheus history: backfill into Mimir and archive the raw TSDB** (ADR-0023 decision kept). Method: `mimirtool blocks split` into UTC-aligned 24 h blocks, then `mimirtool backfill` straight to the `mimir-compactor` service (port-forward plus a reverse SSH tunnel), so the gateway body size does not matter. Block upload needs `limits.compactor_block_upload_enabled: true`, set in PR 1 and removed again in PR 2. A test week is uploaded first and compared against reference values queried from the legacy Prometheus; then all blocks.
- **LAN-only monitoring:** port the three probes (`tandoor`, `netbox`, `dev.kinderreich-augsburg.de`) to Alloy through the 1Password note `Monitoring Targets`. Accept the loss of fritz-exporter (Fritz!Box and modem), the `wireguard:9100` node exporter, ICMP to `192.168.178.1`, and dockerhost's own host, container and Traefik metrics.
- **`grafana.4jp.de`:** delete the record, no redirect (amends ADR-0023; the `g.4jp.de` canonical name stays).
- **On-host data:** stop and disable only, keep all data on disk, power off. The user wipes the disk later; it stays a cold fallback until then.
- **Ansible repo** `/Users/alten/Documents/dockerhost`: commit the pending changes locally, bundle it into the archive, keep the repo read-only on the workstation.
- **Also in scope:** move `~/dockerhost-legacy-*` into the archive and delete it locally; remove the Wazuh `192.168.178.125/32` source range; update NetBox (device offline, IP deleted); remove workstation SSH config and `known_hosts` entries; a cross-repo PR in `deploy-home-assistant`.
- **Out of scope by the user's choice:** revoking host credentials (GitHub `.netrc` token, Docker Hub, Traefik Cloudflare token, Watchtower SMTP password) and the QNAP registry mirror `qnap:32769`.
- **Gates**, each needing an explicit "approved" in chat:

  |Gate|Step|Rollback|
  |---|---|---|
  |G1|Stop Watchtower and the monitoring stack|`systemctl start watchtower monitoring`|
  |G2|Disable all host services, set restart policy `no`, stop containers, delete the temporary archive key|`systemctl enable --now` for the units; restore policies from `restart-policies.txt`|
  |G3|Delete the 10 Cloudflare records|POST them again from `cloudflare-records.tsv`|
  |G4|Power off|The user powers it on physically|
  |G5|NetBox changes|Revert from the changelog|
  |G6|Workstation cleanup|Restore from the QNAP archive|

## Rejected

- A QuObjects bucket or NFS as archive target: the QNAP share is closer, simpler and already trusted for backups.
- Archive-only history: the user wants the history in Mimir with the rest of the metrics.
- A redirect for `grafana.4jp.de`: nobody uses it; the replacement already lives at `g.4jp.de`.
- Wiping the disk now: keeping it intact gives a cold fallback for the price of one shelf slot.
- Deleting data on the host: not needed once the archive is verified, and it removes the fallback.

## Consequences

- The archive holds plaintext secrets (compose environment, `acme.json`, `.netrc`, `.docker/config.json`), so the share must stay private.
- There is no off-site copy of the archive or of the backfilled `mimir-metrics`.
- The user excluded credential revocation: the GitHub token, Docker Hub login, Traefik Cloudflare token and Watchtower SMTP password on the host stay valid until revoked by hand. The QNAP registry mirror stays as is.
- Mimir's 400-day retention starts deleting the oldest backfilled days from 2026-12-04.
- The Fritz!Box, modem and `wireguard` host lose their monitoring.
- Reverting after the Cloudflare deletion needs the records restored from `cloudflare-records.tsv`.
- The Fritz!Box and OPNsense (Caddy upstreams, aliases, rules, NAT, DNS overrides) cannot be read through the API (the `OPNsense Metrics Exporter` key gets 403), so the user checks them by hand.

## Related notes

- [[ADR-0023 - Retire the legacy dockerhost monitoring stack]]
- [[ADR-0019 - LGTM observability stack on k0s]]
- [[ADR-0016 - QuObjects backup target and encrypted offsite copy]]
- `deploy-home-assistant` ADR-0010 (single Mosquitto broker)

## Update 2026-11-06 (executed)

Deviations from the plan above:

- **Archive route.** SSH key login to `qnap.4jp.de` was denied, so the host files were pulled from dockerhost to the workstation and written to the SMB mount `/Volumes/backups/dockerhost/` (about 33 MB/s). Verification is `shasum -a 256 -c` on the mount, not `sha256sum` on the QNAP. The temporary key `/root/.ssh/archive_ed25519` was never installed on the QNAP and was deleted at G2.
- **Probes.** Two probes were ported, not three: `https://tandoor.4jp.de` and `https://netbox.4jp.de` (both 1 in Mimir). `dev.kinderreich-augsburg.de` was removed by the user after an emergency cutover and is not monitored.
- **Vault edit.** The `op` service account here cannot write; the user edited `Monitoring Targets` by hand.
- **Backfill upload.** `mimirtool blocks split` needs `--max-block-duration` (not `--block-duration`) and produced 392 UTC-aligned blocks (all at most 24 h, none crossing 00:00 UTC) from 26 sources. Uploads ran in 2 shards. `kubectl port-forward` to the service dropped connections; a watchdog on `pod/mimir-compactor-0` fixed it. The compactor validates one upload at a time (HTTP 429 otherwise). A QNAP S3 outage (HTTP 503) on 2026-11-05 around 22:00 UTC left block `01M6PHA700EY9SY86PKB9N80SD` in a `validation failed` state; the same data was uploaded again under the new ULID `01M6R0GYPHDYK5VBJAX64DG36C`. The dead partial block stays in the bucket for the cleaner.

Results:

|Step|Result|
|---|---|
|Archive|`prometheus-tsdb.tar.zst` 42.9 GB, 9 tarballs and inventory in `host/` (about 44.6 GB); `host/` 22/22, `workstation-legacy/` 820/820 and `ansible/` 1/1 `OK`; `zstd -t` passed on all tarballs|
|Backfill|392/392 blocks (`already_exists=392 failed=0` in the final pass); test week 21 comparisons and all 19 reference timestamps (57 comparisons, `count(up)`, MemTotal, CPU `increase`) with 0 mismatches and 0 empty|
|Mimir storage|store-gateway PVC 388 MB of 5 Gi after the backfill; no expansion needed|
|tcpdump|33 minutes after G2: 0 inbound packets from any client except the workstation and the Fritz!Box|
|Cloudflare|exactly the 10 expected records deleted; 0 left; every name empty on 1.1.1.1, AdGuard `.171` and OPNsense `10.1.0.1`|
|NetBox|device 55 `offline`, IP 30 deleted, interface 114 and MAC 43 kept|

Gate dates (UTC): G1 2026-11-05 19:00 (stop of the monitoring stack); G2 2026-11-06 10:16 (tcpdump start); G3 and G4 the same morning after the capture was stopped at 10:49 (poweroff: 100 % ping loss, port 22 closed); G5 and G6 the same day. The user did the Fritz!Box and OPNsense steps by hand and reported hits removed without detail.

Open items:

- **Home Assistant.** After the Fritz!Box entry was deleted, the Fritz cleanup button (pressed again 2026-11-06 14:14 UTC) and a config-entry reload left `device_tracker.dockerhost` (`home`) and `switch.dockerhost_internet_access` in place. The HA PR `jaypee/deploy-home-assistant#1` (ADR 0010 update) was merged on 2026-11-06 and is linked from PR #157. The user chose to ignore the leftover entities: no snapshot commit follows. Never press `button.dockerhost_wake_on_lan`.
- **Mimir compaction.** Checksum mismatches came from six damaged compactor-written blocks (zero-filled 16 MiB part in `chunks/000001`, ETag differs from upload); all six carry a no-compact mark and the compactor runs clean. The damage is ongoing (a block uploaded 2026-11-06 14:53 UTC) and five blocks already lost their parents. Details, evidence and the open `deletion_delay` decision: [[ADR-0056 - No-compact marks for Mimir blocks with checksum mismatches]].
- **Backfilled history** exists only in `mimir-metrics` on the QNAP, next to the raw TSDB archive on the same device. Mimir's retention starts deleting the oldest backfilled days on 2026-12-04. The user declined an off-site copy ([[ADR-0057 - No off-site copy of the dockerhost archive and Mimir history]]).
- **`syslog-unbound`** (PR #156 leftover) was applied on 2026-11-06 with `--target`: the only diff was the `__provider` secret, `dig syslog.4jp.de @10.10.0.1` still answers `10.10.88.2`, the full preview shows 39 unchanged.
- **Disk wipe.** The user reported on 2026-11-06 that the wipe of the dockerhost disk is done or under way (not verified by the agent). The cold fallback is gone; the QNAP archive is the only copy.
