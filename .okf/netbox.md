---
type: Service
title: NetBox (Pulumi, applied, legacy data imported, cut over)
description: Migration of the NetBox inventory from dockerhost to k0s with the official chart, a dedicated CloudNativePG database and a Longhorn media volume, the discovery results, and the import and cutover runbook (ADR-0030).
timestamp: 2026-10-20T00:00:00Z
tags: [homelab, kubernetes, netbox, cloudnativepg, longhorn, migration]
resource: https://app.pulumi.com/jaypee-solutions/netbox/prod
---

# State

Applied on 2026-10-20 from branch `feature/netbox` (ADR-0030): stack `jaypee-solutions/netbox/prod`, 31 resources. NetBox 4.7.3 runs at `https://netbox.4jp.de` with the legacy data (imported from 4.2.8, migrations ran at startup). The user confirmed the browser login and the 13 devices; the Cloudflare A record `netbox.4jp.de` was changed by the user from `192.168.178.125` to `10.10.88.1` and is now managed by the stack (imported once with `import_`, removed afterwards; preview then 31 unchanged). `~/.nbcli/user_config.yml` is unchanged (same URL and token): `pynetbox` lists 13 devices. The legacy containers on `dockerhost` are stopped, not deleted.

# Discovery results (dockerhost, 2026-10-20)

NetBox 4.2.8 (`netboxcommunity/netbox:v4.2-3.2.0`, netbox-docker 3.2.0), no unapplied migrations, no plugins, default auth backends (the `ldap/` files are inert), `LOGIN_REQUIRED True`, `METRICS_ENABLED False`, `TIME_ZONE UTC`, `ALLOWED_HOSTS ['*']`, CORS open, `ADMINS []`. Containers `netbox-netbox-1`, `netbox-netbox-housekeeping-1`, `netbox-postgres-1` (PostgreSQL 17.11, 26 MB, only `plpgsql`) and `netbox-redis-cache-1`; **no worker and no task Valkey existed**. Media, reports and scripts were empty. Baseline counts: `dcim_site 1`, `dcim_rack 1`, `dcim_device 13`, `dcim_interface 63`, `dcim_macaddress 1`, `dcim_cable 11`, `ipam_prefix 4`, `ipam_ipaddress 49`, `ipam_vlan 6`, `virtualization_virtualmachine 0`, `users_user 1`, `users_token 2`, `core_objectchange 12`.

The safety copy is in `~/netbox-migration/` on the workstation: `netbox-safety.dump` (sha256 `94072bce…c325`, 185 tables with data) and `netbox-safety-files.tar` (configuration only). Keep both until the user agrees to delete them. The final import used this dump, because the user stated that nothing changed on the legacy instance afterwards (no fresh dump was taken).

# What the stack creates

Namespace `netbox`; CloudNativePG cluster `netbox-db` (PostgreSQL 17, owner and database `netbox`, Barman plugin to `cnpg-backups/netbox-db/`, 21:00 UTC, covered by `cnpg-backup-stale`); Secrets `netbox-config` (generated `secret_key`, explicit `api_token_peppers`, empty `email_password`) and `netbox-superuser` (generated, only satisfies the chart); Deployment and Service `netbox-valkey` (`valkey/valkey:9.1.2-alpine`, no persistence, DB 0 tasks and DB 1 cache); the Helm chart `netbox` 8.3.92 as `helm.v4.Chart` (Deployment `netbox`, Deployment `netbox-worker`, Service `netbox` on port 80, PVC `netbox-media` 1 Gi on Longhorn, in the default recurring group so backed up nightly); IngressRoute `ingress` (`Host(...) && !PathPrefix('/metrics')`); the Cloudflare A record `netbox-dns`.

Chart facts that mattered:

- Peppers must be explicit: the chart generates them with Helm `lookup`, which does not work under `helm.v4.Chart`.
- `SKIP_SUPERUSER=true` (`extraEnvs`): the imported superuser is the only account; the chart still needs the secret `netbox-superuser`.
- The chart itself renders a secret `netbox-kv` with empty `tasks_password` and `cache_password`, so a password-less Valkey needs no extra config.
- `metrics.enabled: true` with `metrics.granian.enabled: false` serves django-prometheus `/metrics` on the application port (140 `django_*` lines, HTTP 200 inside the pod even with `loginRequired`); the Service name `netbox.netbox.svc` is in `allowedHosts` for Alloy.
- Resource presets set a CPU limit on the init containers (`init-dirs`, `wait-for-backend`); both get explicit resources (`init.resources`, `worker.waitForBackend.resources`), so no container has a CPU limit.
- The chart's `test-connection` hook Pod does not appear under `helm.v4.Chart`; nothing to filter.
- NetBox 4.7 logs `FutureWarning: LOGIN_REQUIRED is deprecated and will be removed in NetBox v5.0`.
- The first start of the empty database took about 4 minutes (migrations plus initial data), the start on the imported 4.2.8 data about 2 minutes (migrations, `trace_paths`, `reindex`); the startup probe did not need a larger `failureThreshold`.
- In 4.7 the MAC address of an interface is in `mac_addresses` (a separate object), not in `mac_address` (null in the API).

# Runbook: import and cutover

1. Deploy with `pulumi up` (preview first); the first start migrates an empty database and creates no user.
2. `kubectl -n netbox scale deploy/netbox deploy/netbox-worker --replicas=0`; wait for the pods to go; check `select count(*) from pg_stat_activity where datname='netbox'` is `0`.
3. `kubectl -n netbox exec -i netbox-db-1 -c postgres -- psql -c 'DROP DATABASE netbox' -c 'CREATE DATABASE netbox OWNER netbox'`, then `pg_restore --no-owner --role=netbox --single-transaction --exit-on-error -d netbox < ~/netbox-migration/netbox-safety.dump` the same way. Never `--clean` (see `.okf/tandoor.md`).
4. `kubectl -n netbox rollout restart deploy/netbox-valkey` (drops the cache), scale `netbox` to 1, wait for Ready (migrations run at startup), then scale `netbox-worker` to 1.
5. Verify: row counts equal the baseline, `showmigrations --plan | grep -c '\[ \]'` is `0`, the extensions are `plpgsql` and `ltree` (NetBox created `ltree` itself), the API with the existing token returns `k0s0`, its interface with the MAC, `10.10.8.1/16`, and `status/` reports `4.7.3` with one RQ worker.
6. Apply an on-demand `Backup` (`method: plugin`, `barman-cloud.cloudnative-pg.io`) and wait for `completed`.
7. The user changes the Cloudflare A record to `10.10.88.1`. Read the zone and record IDs with the service-account token (`op://Homelab/b6i34pfgjitlzneedilxq47lxa/password`), add the DNS block with `import_='<zone>/<record>'`, preview (must show `import` without a diff), `pulumi up`, remove `import_`, preview again (no changes).

# Verification evidence (2026-10-20)

- Pods `netbox`, `netbox-worker`, `netbox-valkey`, `netbox-db-1` Ready; `netbox-media` bound; `netbox-db` healthy. Through the ingress `/login/` returned 200 and `/metrics` 404.
- Rehearsal and final import (same dump, sha256 checked before each): all 13 baseline counts equal, 0 unapplied migrations, `ltree` present, API token works, `core_objectchange` stayed at 12.
- On-demand backup `netbox-db-after-import` `completed` after the final import; the first scheduled backup is the night of 2026-10-20.
- Mimir: `up{job="netbox"} == 1`, 63 series names; Grafana has the dashboard `NetBox` and the rules `netbox-down` and `netbox-server-errors` provisioned (from the ConfigMaps in the cluster).
- After the cutover: `dig +short netbox.4jp.de @1.1.1.1` returns `10.10.88.1`; the API without `--resolve` returns NetBox 4.7.3 with `rq-workers-running` 1; `pynetbox` counts 13 devices; previews of `netbox` (31) and `observability` (27) show no changes.

# Open points

- The first scheduled `netbox-db` backup and the Longhorn backup of `netbox-media` (about 02:00 UTC) are still to be seen; after 2026-10-25 set the schedule `0 0 22 * * *` in `Pulumi.prod.yaml`.
- `nbcli` uses a **v1 token** (deprecated in 4.6, removed in v5.0): create a v2 token before then. `LOGIN_REQUIRED` is deprecated and goes away in v5.0; plan the replacement with permissions. Both in `HANDOFF.md` item 17(n).
- Stage 2 (removing `/opt/netbox`, the Ansible role and the stopped containers) needs the user's approval.
- A restore of `netbox-db` from its QNAP backup has not been rehearsed for this cluster; the method is the verified one of ADR-0017 and ADR-0018.

Related: ADR-0030, ADR-0028, ADR-0029, [Tandoor](./tandoor.md), [dockerhost-services](./dockerhost-services.md), [Observability stack](./observability-stack.md).
