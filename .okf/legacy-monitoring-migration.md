---
type: Runbook
title: Retiring the legacy dockerhost monitoring stack
description: Inventory of the old Ansible-managed monitoring on dockerhost, how each part maps to the k0s observability stack, what is stale or blocked, and the gated migration plan (ADR-0023).
timestamp: 2026-10-26T00:00:00Z
tags: [homelab, observability, migration, prometheus, grafana, loki, mimir, dockerhost]
resource: /Users/alten/Documents/dockerhost
---

# What the legacy stack is

Ansible repository `/Users/alten/Documents/dockerhost` (local git, no remote; its own `CLAUDE.md`, `handoff.md` and `.okf`). One host, `dockerhost` at `192.168.178.125` (Ubuntu, user `alten`, key auth, passwordless sudo). Role `ansible/roles/monitoring` renders a Docker Compose project into `/opt/monitoring/` and runs it as the systemd unit `monitoring` (`docker-compose rm --force` then `up`, so **applying the role restarts every container**). Two vault passwords are needed (`~/.vault/dockerhost` and `~/.vault/ax41`); on macOS export `no_proxy=*`. `./deploy` also runs `basics.yml`, which upgrades every package.

The host stays in service after the retirement, until its other services have moved: Traefik, NetBox, InfluxDB, mosquitto, `mqtt2influxdb`, `tesla-logger`, Portainer, Watchtower and Tandoor run there too (a Home Assistant role exists, but no container runs). Only the monitoring role is retired; its node exporter role is separate. The host has no backup; see [dockerhost-services](./dockerhost-services.md).

| Legacy component | Configuration worth knowing |
| --- | --- |
| Prometheus | 13 scrape jobs, about 55 targets; retention 365 days (`--storage.tsdb.retention.size=256GB` is not a real guard); about 93 GB in August; `external_labels: monitor=dockerhost`; remote write and read are commented out |
| Alertmanager | Pushover; legacy config sets no explicit priority, so Alertmanager defaults to priority-2 emergency while firing, retries every minute for up to an hour, and sends priority 0 when resolved; route `notification=none` goes to a muted receiver; `qnap:9100` is muted 00:00-04:10 and 22:00-24:00 (UTC unless configured otherwise); `QNAPPowerOff` inhibits `Target unreachable` for other instances |
| Grafana | Entra ID login (unused since 2025-03-31), 5 datasources (Prometheus, Loki, InfluxDB `vzlogger`, InfluxDB `home_assistant`, InfluxDB `influxdb-pve`), 25 dashboards (19 file-provisioned, 6 created in the UI), plugins piechart, clock, simple-json |
| Loki 2.4.1 + Promtail | 14-day compactor retention; Promtail reads `/var/log/*log`, the journal, and receives syslog on `1514` (the `BackupNAS` host sends its HBS sync logs there); 2 Loki ruler rules |
| blackbox-exporter | modules `http_2xx`, `icmp_ipv4`, `tcp_connect` and others; 32 HTTP targets (27 public, 5 `*.4jp.de`), 2 slow, 4 ICMP, 2 TCP (TeamSpeak) |
| fritz-exporter | two devices: Fritz!Box `192.168.178.1` and the modem `192.168.1.1` |
| cAdvisor | dockerhost containers |
| `jpspeedtest` (systemd, Poetry) | speedtest every 30 minutes into InfluxDB `vzlogger` |
| `ts3_exporter` | templates exist but nothing deploys them |

Scrape jobs: `prometheus`, `cadvisor`, `node-exporter` (6 targets: `dockerhost`, `jp-altens-de`, QNAP `192.168.178.60`, `wireguard`, `192.168.178.125:8080`, `JPM1`), `ax51` (3 HTTPS targets with basic auth), `pretix` (HTTPS, basic auth), `blackbox`, `blackbox-slow`, `blackbox-icmp`, `check_teamspeak`, `jexporter` (`192.168.178.171:9303`: mypv, SwitchBot, Zweiradgarage), `watchtower`, `fritz-exporter`, `ohmgraphite` (`192.168.178.28:4445`, the Windows desktop).

# Findings

Live results of the read-only discovery on `dockerhost` (2026-10-17, script output; the host has been up 236 days, root disk 215 GB of 503 GB used):

- **Versions and flags.** Prometheus is **3.15.0** (image tag `latest`), retention `1y` and `256GiB`, admin API and lifecycle API off, head 40,366 series. Docker 28.0.1 with Compose v1.29.2 and v2.33.1 side by side.
- **Prometheus data** is 90 GB in 24 blocks (95.4 GB by file size). Block spans are 2 h, 6 h, **162 h and 486 h**. The oldest block starts 2025-10-10 12:00 UTC; the largest is 7.7 GB with 9.8 million series (heavy churn). Grafana's data is 515 MB, Loki's 542 MB.
- **Targets.** All 13 jobs are up except three long-dead ones that the `Target unreachable` rule excludes: `node-exporter` `jp-altens-de:9100` (DNS lookup fails) and `JPM1:9100` (`192.168.178.49` unreachable), and `ohmgraphite` `JP` (the desktop). The `node-exporter` job also scrapes `192.168.178.125:8080`, which is dockerhost's own Traefik metrics endpoint (29 `traefik_*` series), not a node exporter; cAdvisor is published on 8090 and has its own job.
- **Alerts.** All 18 alert rules are `inactive` and healthy; Alertmanager has 0 active alerts and 0 silences.
- **`InternalServerErrors` and `RunningOutOfDiskSpace` are dead:** `up{job="ax41"}` has 0 series. The 29 `traefik_entrypoint_requests_total` series come from dockerhost's own Traefik, scraped under the misnamed job `node-exporter` (`192.168.178.125:8080`), so the 5xx rule's intent is valid but it watches a job that does not exist. The `Traefik2` and `Traefik3` dashboards do have data and show dockerhost's Traefik, which is LAN-bound. Whether AX51's Traefik is scraped at all is unknown.
- **`switchbot_*` has 0 series** (SwitchBot moved to Home Assistant on Proxmox), so the `SwitchBot Meter` and `Temperature` dashboards show nothing. `mypv_temp1` and `zweiradgarage_locked` have 1 series each, so `WarmWaterOutage` and `ZweiradGarage` are live. `jexporter` exports 110 series (`mypv_*` and, [INFERENCE], `water_level` and `measuring_error_count` for the coffee dashboard) and runs on the host `wireguard` (`192.168.178.171`), which also has a node exporter. `wordpress_core_*` has 40 series.
- **The QNAP has no nightly shutdown, but it was badly overloaded on the night of the outage.** Its node exporter was up in every 15-minute sample over 14 days. The 2026-10-22 QNAP syslog records RAID group 1 scrubbing from 20:00:03 UTC to 2026-10-23 06:04:52 UTC (0 blocks repaired), likely the cause of that overload and the 10-22 backup failure. The same Thursday 20:00 start coincides with the 2026-10-15 overload associated with the 10-16 outage, but that remains uncertain because the syslog receiver was not deployed then. The QNAP's scheduled `DataVol1` snapshot normally starts at 21:00 UTC and takes about 45 seconds; on 10-22 it ran from 21:00:01 to 21:34:05, overlapping CloudNativePG backups. `paperless-db-backup-20261022210000` failed with `NoSuchUpload ... CompleteMultipartUpload: The specified bucket does not exist`, followed by WAL archiving errors until recovery. The 10-22/23 evidence points to the scrub, not HBS, as the likely cause. The QNAP's own logs should identify the job.
- **`BackupNAS` sent 0 syslog lines in the last 7 days**, and the Loki rule `sum(count_over_time(...)) < 11` returns no data when no lines arrive, so it cannot alert on silence. The replacement must alert on absence.
- **Grafana's database holds things that are not in Ansible:** 6 dashboards created in the UI: `Docker and system monitoring` (2021, old Singlestat panels), `Traefik3` (2021), `Prometheus Blackbox Exporter` (11 panels on `probe_*`), `Status` (one stat panel on `probe_http_status_code`), `coffee` (`water_level`, `measuring_error_count`) and `Pretix` (8 panels on `pretix_*`, including Celery queue age); 1 Grafana-managed alert rule `Low Water Level` (`water_level < 25` for 5 minutes; its contact point was not inspected); a datasource `influxdb-pve` pointing at `http://pve.4jp.de:8089` although the dockerhost InfluxDB has no database `pve` and no UI-only dashboard uses it ([INFERENCE] unused); 1 playlist and 4,655 annotations. 19 of 25 dashboards are file-provisioned. There are two users: `admin` (last seen 2026-10-15) and `microsoft@alten.de`, whose last login was **2025-03-31**; Entra ID is effectively unused.
- `bearer_token: TOP_SECRET` for Watchtower sits in plain text in `prometheus.yml`.
- **Containers on the host** (`sudo docker ps`): the monitoring stack (Prometheus, Alertmanager, Grafana and Promtail, Loki 2.4.1, cAdvisor v0.47.0, blackbox-exporter, fritz-exporter), `traefik` v3.2, `influxdb` 1.8.6 (databases `vzlogger`, `home_assistant`, `node`, `default`, `_internal`; `vzlogger` holds `current_power`, `bkw_current_power`, `meter1`, `meter2`, `coffee`, `rolladen_position`, `shellies` and more), `mosquitto`, `mqtt2influxdb`, NetBox 4.2 with PostgreSQL and Redis, Portainer, Tandoor, `tesla-logger` (with its own Grafana 10.0.1 and MariaDB) and Watchtower, which keeps the `latest` monitoring images current. **No `home-assistant` container runs.** The provisioned dashboard directory on the host also holds three stale files that are not in the repository (`fritz-box-router-status_rev1.json`, `fritz-box-status_rev1.json`, `internet-dashboard-prometheus_rev1.json`).

# Network gate

From a pod on k0s, every probe to `192.168.178.0/24` timed out on 2026-10-17 (dockerhost ports 9090, 9100, 8080, 8086 and 1514, FritzBox 49000, QNAP `.60:9100`, `.171:9303`, `.28:4445`). The modem `192.168.1.1:49000` answered `404`. The workstation (`192.168.178.192`) reaches the cluster, so that direction works; whether OPNsense or the FritzBox drops the reverse is not known (the OPNsense API user cannot read firewall rules). **Decision: LAN targets are deferred** ([[ADR-0023 - Retire the legacy dockerhost monitoring stack]]).

# Stage 1 scope: what can move without the LAN

| Item | New home | Notes |
| --- | --- | --- |
| HTTP, TCP and public ICMP probes (27 public sites, `www.koeberle-schmid.com`, TeamSpeak ports, `mail.alten.de`, `heise.de`, `google.de`) | Alloy `prometheus.exporter.blackbox`, targets from config | Keep the modules. ICMP from a pod needs `NET_RAW` or the safe sysctl `net.ipv4.ping_group_range`; check at build time, or fall back to HTTP |
| `ax51` (3 HTTPS targets) and `pretix` | Alloy scrape with basic auth | The two passwords move from the Ansible vault into 1Password items created by the user |
| WordPress core update metrics | `ax51` node exporter textfile metrics, vendored dashboard | Arrive through the `ax51` job (see the legacy ADR-001) |
| Speedtest | in-cluster `prometheus-speedtest-exporter` | The donor `services/monitoring/monitoring/speedtest.py` already deploys billimek's exporter 1.3.1; rebuild the Internet Speed dashboard on Mimir. Note that it measures the new uplink path |
| Alert rules | `alert_rules.py` | Port `ServiceDown`, `ServiceDownSlow` and `SSLCertExpiringSoon`. The generic CPU, memory and disk rules already cover the cluster and cover `ax51` once it is scraped, which makes `RunningOutOfDiskSpace` redundant. `InternalServerErrors` watches dockerhost's Traefik and moves with the LAN work. Drop `QNAPPowerOff` with its mute and inhibit logic |
| Grafana login | Authentik OIDC | AX41 blueprint (groups `grafana-admins`, `grafana`, bindings) plus a UI-created application and a 1Password item; `auth.generic_oauth` in the Helm values with the secret from `grafana-secrets` |
| History | Mimir backfill | See below |
| Hostname | `grafana.4jp.de` | See below |
| QNAP logs | Alloy `loki.source.syslog` in Loki | Done 2026-10-17 (ADR-0024, PR #27): RFC 5424 and RFC 3164 over TCP and UDP on `10.10.88.2` / `syslog.4jp.de`; the QNAP's Log Sender still has to be configured by the user |

Dashboards, decided by the user on 2026-10-17: **keep and port** the UI-only `Prometheus Blackbox Exporter`, `Status` and `Pretix` (they use only `probe_*` and `pretix_*` metrics, so they work in stage 1) plus `WordPress Core Updates` and `Internet Speed` (rebuilt on Mimir). **Drop** `Docker and system monitoring`, `Traefik3` and `coffee` (with its alert `Low Water Level`: confirmed, Home Assistant handles the coffee machine now), the provisioned `Blackbox Exporter (HTTP prober)` (a duplicate of the kept one), `SwitchBot Meter` and `Temperature` (no data), the three stale files on the host, and the views the new stack already has (`Node Exporter Full`, the Docker and cAdvisor views for the cluster, `Loki Dashboard quick search`, a Traefik view). The UI dashboards use the datasource UID `PBFA97CFB590B2093` and the name `Prometheus`; the dashboard adapter must point them at the `mimir` datasource. Per the lessons file each ported dashboard is checked against live data before it is accepted.

# Deferred with the LAN (stays on the legacy stack)

dockerhost `node-exporter`, cAdvisor and its Traefik (`:8080`) with the `Traefik2` dashboard and `InternalServerErrors`, QNAP node metrics, `fritz-exporter` for the Fritz!Box (the modem device is reachable), `ohmgraphite` and the `Ohm Windows Desktop` dashboard, `jexporter` on `wireguard` with the `Solax` and `Warmwasser` dashboards, Watchtower, the `Power` and `Power small` dashboards (InfluxDB), the five `*.4jp.de` and the LAN probes (`192.168.178.222`, `192.168.178.1`), Promtail logs of dockerhost, and the `BackupNAS` syslog with its two Loki rules and the `Backup` dashboard (needs a syslog receiver such as Alloy `loki.source.syslog`, tied to the HBS 3 work).

**Alerts that exist only on the legacy stack until the LAN work: `ZweiradGarage` (the lock is open), `WarmWaterOutage` and the Grafana rule `Low Water Level`.** The user accepted on 2026-10-17 that the first two stay there. Switching the legacy stack off is therefore stage 2, after the LAN decision.

# Backfilling the history

Facts from the Mimir documentation (checked 2026-10-17): block upload is experimental and off by default (`limits.compactor_block_upload_enabled: true`); blocks longer than 24 hours, crossing a UTC-day boundary or outside the retention period are rejected; `mimirtool backfill --address=<mimir> --id=anonymous <block dirs>` uploads them and can be restarted; with nginx in front a block over the body limit returns 413 (Helm: `gateway.nginx.config.clientMaxBodySize`); after the upload the query results cache may need flushing.

Constraints specific to this setup:

1. The Prometheus blocks span 2 h to 486 h (about 20 days), so they must first be re-cut into daily UTC-aligned blocks. [INFERENCE] `promtool tsdb dump` into `promtool tsdb create-blocks-from openmetrics` with a 24-hour maximum block duration can do this (promtool is in the `prom/prometheus` image); it is slow for 95 GB, so prove it on one week first. A daily block averages about 0.25 GB; the largest source block is 7.7 GB with 9.8 million series.
2. Mimir currently keeps 30 days (`retention-days`) and has a 5 GiB store-gateway and a 10 GiB compactor volume. The oldest block starts on 2025-10-10, which is more than 365 days back, so retention must be **at least 372 days (use 400)** before the upload, or those blocks are rejected. Size the volumes and the QuObjects bucket for about 100 GB. The free space on the QNAP volume is not known to me.
3. The workstation has 43 GB free and neither tool installed, so the upload runs on `dockerhost` next to the data: a static `mimirtool` binary there, with `kubectl -n observability port-forward svc/mimir-gateway 18080:80` on the workstation and `ssh -R 18080:localhost:18080 alten@192.168.178.125`. Nothing new is exposed.
4. The last two to three hours sit in the head and in no block. Either accept the gap at the final cut or enable `--web.enable-admin-api` for a snapshot that includes the head (that is a legacy restart).
5. Run the backfill at the final cut (stage 2) so the legacy Prometheus has stopped writing; a test with one week runs earlier.
6. The query results cache must be flushed after the upload.

# Hostname and login

`grafana.4jp.de` is a public Cloudflare record pointing at `192.168.178.125`; the workstation resolves through `1.1.1.1`, so it follows the Cloudflare record, while LAN clients follow dnsmasq. Pointing the name at the new Grafana therefore needs both: a dnsmasq host record (the existing `utils.opnsense.dnsmasq.host.Host` pattern, as for `g`) and the Cloudflare A record changed to `10.10.88.1`, plus a second host on the IngressRoute (the wildcard certificate already covers it). An OIDC redirect URI follows the Grafana `root_url`, so one name must be canonical. **Decided 2026-10-17: `g.4jp.de` is canonical and `grafana.4jp.de` redirects to it** with a Traefik redirect middleware. The legacy names `prometheus`, `alertmanager`, `loki`, `cadvisor` and `blackbox-exporter` `.4jp.de` go with stage 2.

# Plan

Each phase ends with a verification; destructive steps need the user's approval; every Pulumi change is previewed first.

0. **Read-only discovery on the host: done 2026-10-17** (two scripts, results above). Optional leftovers: when the QNAP overload of 2026-10-15 began (query the legacy Prometheus from 12:00 UTC) and where `water_level` comes from.
1. **Prepare Mimir: done 2026-10-17.** Retention is 400 days (PR #26; one preview, one apply, ingestion continued). Block upload and the gateway body size stay for the backfill, when the real block file sizes are known.
2. **Port stage 1 targets: done 2026-10-17** (PR #28, ADR-0025, ADR-0026). 33 probes (27 http, 1 slow, 3 icmp, 2 tcp; all succeed) and the `ax51` and `pretix` scrapes run in Alloy, with three new Grafana rules. It needed the node's inotify limit raised to 1024 and the API server's histogram buckets dropped (Mimir's series limit was reached). The dual run with the legacy Prometheus starts now; the migrated jobs are removed from the legacy side in phase 5.
3. **Speedtest and dashboards: done 2026-10-17** (PR #29, ADR-0027). The exporter runs in `observability` (Alloy scrapes it every 30 minutes), `Internet Speed` is rebuilt in code, and `Prometheus Blackbox Exporter`, `Status`, `Pretix` and `WordPress Core Updates` are vendored from the legacy Grafana; 14 dashboards in Grafana and all 24 panel queries of the ported ones return data.
4. **Grafana login: paused by the user on 2026-10-17, to be started another day.** AX41 pull request (blueprint), the user creates the Authentik application and the 1Password item `Grafana OIDC`, then the Helm values change. The full plan and the two open questions (may the agent open the AX41 pull request; role mapping) are in HANDOFF open item 12.
5. **Cut over stage-1 monitoring jobs: done 2026-10-26.** After live replacement checks, the user approved ending the dual run early. Removed legacy `ax51`, `pretix`, `check_teamspeak` and migrated public probe targets; retained five local `*.4jp.de` probes, `dev.kinderreich-augsburg.de`, and LAN-only slow/ICMP targets with their legacy alerts. Prometheus config/rules passed `promtool` and reloaded with `SIGHUP`. DNS/name cutover (dnsmasq, Cloudflare, IngressRoute host, redirect) remains pending.
6. **Backfill test** with one week; if queries match the legacy Prometheus, continue later in stage 2.
7. **Stage 2 (later, after the LAN decision):** move the LAN targets, then stop the legacy stack, archive `data/prometheus` and `data/grafana` to the QNAP, run the full backfill, and, after the user's approval, remove `/opt/monitoring`, the `jpspeedtest` unit, the role and playbook import in the Ansible repository, the legacy DNS records and the vaulted secrets that are no longer used. The user also said the Home Assistant role on dockerhost is dead and can be deleted (no container runs; SwitchBot now lives in Home Assistant on Proxmox): remove the role, `/opt/home-assistant`, the `InfluxDBHomeAssistant` datasource, the blackbox target `home-assistant.4jp.de` and, after archiving, the InfluxDB database `home_assistant`, each with approval. Also decide the fate of the donor-derived `services/monitoring` Pulumi workspace in this repository (it targets `tobiash.net` and Synology values and is not the same thing).

# Open questions for the user

- The QNAP now sends its logs to the receiver (ADR-0024, test message arrived 2026-10-17). Once real events arrive, look in Loki (`{job="qnap-syslog"}`) and in the QNAP's own logs for what drove the load average to 112 on 2026-10-15 to 2026-10-16; the logs of that night predate the receiver.
- Mimir returned no `up` series for speed-related jobs on 2026-10-26 while the `speedtest-exporter` pod was Running. Verify the scrape before retiring legacy `jpspeedtest`/InfluxDB.
- Is the speed test cadence of 30 minutes acceptable? One test moves about 156 MB, so about 7.5 GB a day; 60 minutes would halve it (ADR-0027).
- Phase 4 (Grafana login) is paused until the user starts it: may the agent open the pull request in the AX41 repository, and which Grafana roles should the groups map to (proposal: `grafana-admins` Admin, `grafana` Viewer)?

Related: [Observability stack](./observability-stack.md), [Paperless](./paperless.md), ADR-0019, ADR-0021, ADR-0023.
