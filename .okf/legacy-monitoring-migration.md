---
type: Runbook
title: Retiring the legacy dockerhost monitoring stack
description: Inventory of the old Ansible-managed monitoring on dockerhost, how each part maps to the k0s observability stack, what is stale or blocked, and the gated migration plan (ADR-0023).
timestamp: 2026-10-17T00:00:00Z
tags: [homelab, observability, migration, prometheus, grafana, loki, mimir, dockerhost]
resource: /Users/alten/Documents/dockerhost
---

# What the legacy stack is

Ansible repository `/Users/alten/Documents/dockerhost` (local git, no remote; its own `CLAUDE.md`, `handoff.md` and `.okf`). One host, `dockerhost` at `192.168.178.125` (Ubuntu, user `alten`, key auth, passwordless sudo). Role `ansible/roles/monitoring` renders a Docker Compose project into `/opt/monitoring/` and runs it as the systemd unit `monitoring` (`docker-compose rm --force` then `up`, so **applying the role restarts every container**). Two vault passwords are needed (`~/.vault/dockerhost` and `~/.vault/ax41`); on macOS export `no_proxy=*`. `./deploy` also runs `basics.yml`, which upgrades every package.

The host stays in service after the retirement: Traefik, NetBox, InfluxDB, Home Assistant, mosquitto, `mqtt2influxdb`, `tesla-logger`, Watchtower and Tandoor run there too. Only the monitoring role is retired; its node exporter role is separate.

| Legacy component | Configuration worth knowing |
| --- | --- |
| Prometheus | 13 scrape jobs, about 55 targets; retention 365 days (`--storage.tsdb.retention.size=256GB` is not a real guard); about 93 GB in August; `external_labels: monitor=dockerhost`; remote write and read are commented out |
| Alertmanager | Pushover; route `notification=none` goes to a muted receiver; `qnap:9100` is muted 00:00-04:10 and 22:00-24:00 (UTC unless configured otherwise); `QNAPPowerOff` inhibits `Target unreachable` for other instances |
| Grafana | Entra ID login, 4 datasources (Prometheus, Loki, InfluxDB `vzlogger`, InfluxDB `home_assistant`), 18 file-provisioned dashboards, plugins piechart, clock, simple-json; the database in `data/grafana` was not inspected |
| Loki 2.4.1 + Promtail | 14-day compactor retention; Promtail reads `/var/log/*log`, the journal, and receives syslog on `1514` (the `BackupNAS` host sends its HBS sync logs there); 2 Loki ruler rules |
| blackbox-exporter | modules `http_2xx`, `icmp_ipv4`, `tcp_connect` and others; 32 HTTP targets (27 public, 5 `*.4jp.de`), 2 slow, 4 ICMP, 2 TCP (TeamSpeak) |
| fritz-exporter | two devices: Fritz!Box `192.168.178.1` and the modem `192.168.1.1` |
| cAdvisor | dockerhost containers |
| `jpspeedtest` (systemd, Poetry) | speedtest every 30 minutes into InfluxDB `vzlogger` |
| `ts3_exporter` | templates exist but nothing deploys them |

Scrape jobs: `prometheus`, `cadvisor`, `node-exporter` (6 targets: `dockerhost`, `jp-altens-de`, QNAP `192.168.178.60`, `wireguard`, `192.168.178.125:8080`, `JPM1`), `ax51` (3 HTTPS targets with basic auth), `pretix` (HTTPS, basic auth), `blackbox`, `blackbox-slow`, `blackbox-icmp`, `check_teamspeak`, `jexporter` (`192.168.178.171:9303`: mypv, SwitchBot, Zweiradgarage), `watchtower`, `fritz-exporter`, `ohmgraphite` (`192.168.178.28:4445`, the Windows desktop).

# Findings in the configuration

- `InternalServerErrors` and `RunningOutOfDiskSpace` select `job="ax41"`, but no scrape job has that name (it is `ax51`), so by the config they can never fire. Confirm against the live rule list before dropping them.
- The `Traefik2` dashboard needs `traefik_*` series and no job in the config scrapes a Traefik. [INFERENCE] it shows no data.
- `bearer_token: TOP_SECRET` for Watchtower sits in plain text in `prometheus.yml`.
- The Loki rules `Finished backup job lower than 10` and `Failed backup` watch the HBS sync logs of `BackupNAS`. This is the monitoring of HBS jobs that ADR-0016 asks for.
- `QNAPPowerOff` (`hour() >= 20 or hour() < 4`) plus the mute window suggest the QNAP once powered off nightly. The new stack shows no WAL archiving failures on `postgres-pilot` in the last five days (`paperless-db` had failures from 2026-10-15 21:18 to 2026-10-16 01:48 UTC), so there is no sign of a nightly shutdown now. [INFERENCE] ask the user whether the schedule still exists.

# Network gate

From a pod on k0s, every probe to `192.168.178.0/24` timed out on 2026-10-17 (dockerhost ports 9090, 9100, 8080, 8086 and 1514, FritzBox 49000, QNAP `.60:9100`, `.171:9303`, `.28:4445`). The modem `192.168.1.1:49000` answered `404`. The workstation (`192.168.178.192`) reaches the cluster, so that direction works; whether OPNsense or the FritzBox drops the reverse is not known (the OPNsense API user cannot read firewall rules). **Decision: LAN targets are deferred** ([[ADR-0023 - Retire the legacy dockerhost monitoring stack]]).

# Stage 1 scope: what can move without the LAN

| Item | New home | Notes |
| --- | --- | --- |
| HTTP, TCP and public ICMP probes (27 public sites, `www.koeberle-schmid.com`, TeamSpeak ports, `mail.alten.de`, `heise.de`, `google.de`) | Alloy `prometheus.exporter.blackbox`, targets from config | Keep the modules. ICMP from a pod needs `NET_RAW` or the safe sysctl `net.ipv4.ping_group_range`; check at build time, or fall back to HTTP |
| `ax51` (3 HTTPS targets) and `pretix` | Alloy scrape with basic auth | The two passwords move from the Ansible vault into 1Password items created by the user |
| WordPress core update metrics | `ax51` node exporter textfile metrics, vendored dashboard | Arrive through the `ax51` job (see the legacy ADR-001) |
| Speedtest | in-cluster `prometheus-speedtest-exporter` | The donor `services/monitoring/monitoring/speedtest.py` already deploys billimek's exporter 1.3.1; rebuild the Internet Speed dashboard on Mimir. Note that it measures the new uplink path |
| Alert rules | `alert_rules.py` | Port `ServiceDown`, `ServiceDownSlow`, `SSLCertExpiringSoon`; node CPU, memory and disk rules are already covered for the cluster and need only the `ax51` target added; drop the dead `ax41` rules |
| Grafana login | Authentik OIDC | AX41 blueprint (groups `grafana-admins`, `grafana`, bindings) plus a UI-created application and a 1Password item; `auth.generic_oauth` in the Helm values with the secret from `grafana-secrets` |
| History | Mimir backfill | See below |
| Hostname | `grafana.4jp.de` | See below |

Community dashboards the new stack already has replace `Node Exporter Full`, the Docker and cAdvisor views (for the cluster) and `Loki Dashboard quick search` (the new Logs explorer). `Blackbox Exporter (HTTP prober)` and `WordPress Core Updates` are ported; per the lessons file each is checked against live data before it is accepted.

# Deferred with the LAN (stays on the legacy stack)

dockerhost `node-exporter` and cAdvisor, QNAP node metrics, `fritz-exporter` for the Fritz!Box (the modem device is reachable), `ohmgraphite` and the `Ohm Windows Desktop` dashboard, `jexporter` with the `Solax`, `Warmwasser`, `Temperature` and `SwitchBot` dashboards, Watchtower, the `Power` and `Power small` dashboards (InfluxDB), the five `*.4jp.de` and the LAN probes (`192.168.178.222`, `192.168.178.1`), Promtail logs of dockerhost, and the `BackupNAS` syslog with its two Loki rules and the `Backup` dashboard (needs a syslog receiver such as Alloy `loki.source.syslog`, tied to the HBS 3 work).

**Alerts that exist only on the legacy stack and are lost if it is switched off before the LAN work: `ZweiradGarage` (the lock is open) and `WarmWaterOutage`.** Switching the legacy stack off is therefore stage 2, after the LAN decision or with an explicit acceptance of these losses.

# Backfilling the history

Facts from the Mimir documentation (checked 2026-10-17): block upload is experimental and off by default (`limits.compactor_block_upload_enabled: true`); blocks longer than 24 hours, crossing a UTC-day boundary or outside the retention period are rejected; `mimirtool backfill --address=<mimir> --id=anonymous <block dirs>` uploads them and can be restarted; with nginx in front a block over the body limit returns 413 (Helm: `gateway.nginx.config.clientMaxBodySize`); after the upload the query results cache may need flushing.

Constraints specific to this setup:

1. Prometheus with 365 days of retention writes blocks of up to 31 days, so they must first be re-cut into daily UTC-aligned blocks. [INFERENCE] `promtool tsdb dump` into `promtool tsdb create-blocks-from openmetrics` with a 24-hour maximum block duration can do this (promtool is in the `prom/prometheus` image); it is slow for 93 GB, so prove it on one week first.
2. Mimir currently keeps 30 days (`retention-days`) and has a 5 GiB store-gateway and a 10 GiB compactor volume; raise retention to 365 days before the upload (older blocks would be rejected) and size the volumes and the QuObjects bucket for about 100 GB. The free space on the QNAP volume is not known to me.
3. The workstation has 43 GB free and neither tool installed, so the upload runs on `dockerhost` next to the data: a static `mimirtool` binary there, with `kubectl -n observability port-forward svc/mimir-gateway 18080:80` on the workstation and `ssh -R 18080:localhost:18080 alten@192.168.178.125`. Nothing new is exposed.
4. The last two to three hours sit in the head and in no block. Either accept the gap at the final cut or enable `--web.enable-admin-api` for a snapshot that includes the head (that is a legacy restart).
5. Run the backfill at the final cut (stage 2) so the legacy Prometheus has stopped writing; a test with one week runs earlier.
6. The query results cache must be flushed after the upload.

# Hostname and login

`grafana.4jp.de` is a public Cloudflare record pointing at `192.168.178.125`; the workstation resolves through `1.1.1.1`, so it follows the Cloudflare record, while LAN clients follow dnsmasq. Pointing the name at the new Grafana therefore needs both: a dnsmasq host record (the existing `utils.opnsense.dnsmasq.host.Host` pattern, as for `g`) and the Cloudflare A record changed to `10.10.88.1`, plus a second host on the IngressRoute (the wildcard certificate already covers it). An OIDC redirect URI follows the Grafana `root_url`, so one name must be canonical. Recommended: `g.4jp.de` canonical and `grafana.4jp.de` redirecting to it with a Traefik redirect middleware. The legacy names `prometheus`, `alertmanager`, `loki`, `cadvisor` and `blackbox-exporter` `.4jp.de` go with stage 2.

# Plan

Each phase ends with a verification; destructive steps need the user's approval; every Pulumi change is previewed first.

0. **Read-only discovery on the host (needs a terminal with LAN access or the user).** This terminal gets `No route to host` to `192.168.178.125` (known macOS Local Network permission gotcha, or the host is off; undetermined). Collect: `curl :9090/api/v1/targets` (which targets are down), `/api/v1/rules` and `/api/v1/alerts` (what fires, which rules are dead), `du -sh /opt/monitoring/data/*`, the Grafana database (users, orgs, annotations, dashboards not provisioned from files, API keys), where `jexporter` runs and what feeds `zweiradgarage_locked`, which dashboards were opened lately, and whether the QNAP still has a power schedule.
1. **Prepare Mimir** (the `observability` stack): retention 365 days, block upload enabled, gateway body size, volume sizes. One preview, one apply; check ingestion and queries afterwards.
2. **Port stage 1 targets** into Alloy and `alert_rules.py` in small steps; each step is compared with the legacy value (`probe_success` parity, target health) during a dual run of about two weeks, with a deliberate alert test through the Pushover contact point.
3. **Speedtest and dashboards**: deploy the exporter, port the two dashboards, drop the replaced ones.
4. **Grafana login**: AX41 pull request (blueprint), the user creates the Authentik application and the 1Password item `Grafana OIDC`, then the Helm values change.
5. **Cut over the names** (dnsmasq record, Cloudflare record, IngressRoute host, redirect) and remove the migrated jobs and rules from the legacy Prometheus (an Ansible apply that restarts the legacy stack).
6. **Backfill test** with one week; if queries match the legacy Prometheus, continue later in stage 2.
7. **Stage 2 (later, after the LAN decision):** move the LAN targets, then stop the legacy stack, archive `data/prometheus` and `data/grafana` to the QNAP, run the full backfill, and, after the user's approval, remove `/opt/monitoring`, the `jpspeedtest` unit, the role and playbook import in the Ansible repository, the legacy DNS records and the vaulted secrets that are no longer used. Also decide the fate of the donor-derived `services/monitoring` Pulumi workspace in this repository (it targets `tobiash.net` and Synology values and is not the same thing).

# Open questions for the user

- Which hostname is canonical for Grafana (recommended `g.4jp.de`)?
- Is it acceptable that `ZweiradGarage` and `WarmWaterOutage` live only on the legacy stack until the LAN work?
- How much free space does the QNAP volume behind the `mimir-metrics` bucket have, and is that bucket part of the HBS 3 off-site job?
- Does the QNAP still have a power schedule?

Related: [Observability stack](./observability-stack.md), [Paperless](./paperless.md), ADR-0019, ADR-0021, ADR-0023.
