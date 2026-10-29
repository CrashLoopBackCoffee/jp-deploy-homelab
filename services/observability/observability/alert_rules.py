"""Grafana-managed alert rules, provisioned from code.

Each expression uses a `bool` comparison, so it returns 1 for series in a bad state and 0
otherwise; the shared reduce and threshold nodes alert on a last value above zero.
"""

import dataclasses
import typing as t

MIMIR_DATASOURCE_UID = 'mimir'
LOKI_DATASOURCE_UID = 'loki'
FOLDER = 'Homelab'
EXPRESSION_DATASOURCE = {'type': '__expr__', 'uid': '__expr__'}

# Longhorn exposes volume robustness as one 0/1 series per state, and its backup target as a
# 0/1 `unavailable` condition.
# Node filesystems below k0s' kubelet directory are per-pod mounts, not capacity concerns.
_NODE_FILESYSTEM = (
    'fstype=~"ext4|xfs|btrfs", mountpoint!~"/var/lib/(k0s|kubelet)/.*", mountpoint!~"/run/.*"'
)

# Grafana never deletes a provisioned rule just because its file entry disappeared.
REMOVED_RULE_UIDS = ('longhorn-backup-failed',)


@dataclasses.dataclass(frozen=True)
class AlertRule:
    uid: str
    title: str
    expr: str
    summary: str
    for_: str = '5m'
    severity: str = 'warning'
    # State when the query returns no series. Alerting when the thing that must exist is absent.
    no_data_state: str = 'OK'


@dataclasses.dataclass(frozen=True)
class LokiAlertRule:
    """A Grafana alert rule evaluated by Loki's LogQL datasource."""

    uid: str
    title: str
    expr: str
    summary: str
    for_: str = '0s'
    severity: str = 'warning'
    no_data_state: str = 'OK'


LOKI_RULES = [
    LokiAlertRule(
        uid='wazuh-critical-finding-active',
        title='New Active Critical vulnerability finding',
        expr=(
            'sum by (agent_id, cve, package) (count_over_time('
            '{namespace="wazuh",job="wazuh-alerts"} | json '
            'rule_id="rule.id", agent_id="agent.id", cve="data.vulnerability.cve", '
            'package="data.vulnerability.package.name", '
            'status="data.vulnerability.status", '
            'severity="data.vulnerability.severity" '
            '| rule_id=~"2350[2-6]" | status="Active" | severity="Critical" [5m])) '
            '> bool 0'
        ),
        summary=(
            'New Active Critical finding on agent {{ $labels.agent_id }}: '
            '{{ $labels.cve }} / {{ $labels.package }}'
        ),
    ),
    LokiAlertRule(
        uid='wazuh-feed-error',
        title='Wazuh vulnerability feed error',
        expr=(
            'sum(count_over_time({namespace="wazuh",job="wazuh-ossec-log"} '
            '|~ "Error updating feed" [5m])) > bool 0 '
            'or sum(count_over_time({namespace="wazuh",job="wazuh-cti-freshness"} '
            '| json | event="cti_freshness_error" [5m])) > bool 0'
        ),
        summary='Wazuh scanner feed or CTI freshness probe reported an error',
    ),
    LokiAlertRule(
        uid='wazuh-cti-probe-silent',
        title='Wazuh CTI freshness probe is silent',
        expr=(
            'absent_over_time({namespace="wazuh",job="wazuh-cti-freshness"} '
            '| json | event="cti_freshness" [30m]) or (sum(count_over_time('
            '{namespace="wazuh",job="wazuh-cti-freshness"} '
            '| json | event="cti_freshness" [30m])) * 0)'
        ),
        summary=(
            'No Wazuh CTI freshness heartbeat has reached Loki for 30 minutes; '
            'this also detects a stopped manager log pipeline'
        ),
        no_data_state='Alerting',
    ),
]


RULES = [
    AlertRule(
        uid='target-down',
        title='Scrape target down',
        expr='up == bool 0',
        summary='{{ $labels.job }} on {{ $labels.instance }} is not reachable by Alloy',
    ),
    AlertRule(
        uid='node-not-ready',
        title='Node not ready',
        expr='kube_node_status_condition{condition="Ready", status="true"} == bool 0',
        summary='Node {{ $labels.node }} is not Ready',
        severity='critical',
    ),
    AlertRule(
        uid='node-cpu-high',
        title='Node CPU above 90%',
        expr='(1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))) > bool 0.9',
        summary='CPU of {{ $labels.instance }} has been above 90% for 15 minutes',
        for_='15m',
    ),
    AlertRule(
        uid='node-memory-high',
        title='Node memory above 90%',
        expr='(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) > bool 0.9',
        summary='Memory of {{ $labels.instance }} has been above 90% for 10 minutes',
        for_='10m',
    ),
    AlertRule(
        uid='node-filesystem-full',
        title='Node filesystem above 85%',
        expr=(
            f'(1 - node_filesystem_avail_bytes{{{_NODE_FILESYSTEM}}}'
            f' / node_filesystem_size_bytes{{{_NODE_FILESYSTEM}}}) > bool 0.85'
        ),
        summary='{{ $labels.mountpoint }} on {{ $labels.instance }} is above 85% full',
        for_='15m',
    ),
    AlertRule(
        uid='pvc-nearly-full',
        title='Persistent volume above 85%',
        expr='(kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes) > bool 0.85',
        summary='PVC {{ $labels.namespace }}/{{ $labels.persistentvolumeclaim }} is above 85% full',
        for_='15m',
    ),
    AlertRule(
        uid='pod-crash-looping',
        title='Pod crash looping',
        expr='kube_pod_container_status_waiting_reason{reason="CrashLoopBackOff"} == bool 1',
        summary='{{ $labels.namespace }}/{{ $labels.pod }} ({{ $labels.container }}) is crash looping',
        for_='10m',
    ),
    AlertRule(
        uid='longhorn-volume-unhealthy',
        title='Longhorn volume degraded or faulted',
        expr='longhorn_volume_robustness{state=~"degraded|faulted"} == bool 1',
        summary='Longhorn volume {{ $labels.volume }} is degraded or faulted',
        severity='critical',
    ),
    AlertRule(
        uid='longhorn-disk-nearly-full',
        title='Longhorn disk above 80%',
        expr='(longhorn_disk_usage_bytes / longhorn_disk_capacity_bytes) > bool 0.8',
        summary='Longhorn disk {{ $labels.disk }} on {{ $labels.node }} is above 80% full',
        for_='15m',
    ),
    AlertRule(
        uid='longhorn-backup-target-unavailable',
        title='Longhorn backup target unavailable',
        expr='longhorn_backup_target_status{condition="unavailable"} == bool 1',
        summary='Longhorn backup target {{ $labels.backup_target }} is unavailable',
        for_='10m',
        severity='critical',
    ),
    AlertRule(
        uid='longhorn-volume-backup-stale',
        title='Longhorn volume not backed up for 30 hours',
        expr='(time() - longhorn_volume_last_backup_at) > bool 108000',
        # A value of 0 means never backed up. A new volume therefore stays pending until the
        # first nightly job has run, so the delay must exceed the 24 hour job interval.
        summary='Volume {{ $labels.pvc_namespace }}/{{ $labels.pvc }} has no recent Longhorn backup',
        for_='26h',
        severity='critical',
    ),
    AlertRule(
        uid='cnpg-instance-down',
        title='PostgreSQL instance down',
        expr='cnpg_collector_up == bool 0',
        summary='PostgreSQL cluster {{ $labels.cluster }} instance is not serving',
        severity='critical',
    ),
    AlertRule(
        uid='cnpg-wal-archiving-failing',
        title='PostgreSQL WAL archiving failing',
        expr='increase(cnpg_pg_stat_archiver_failed_count[15m]) > bool 0',
        summary='WAL archiving of {{ $labels.pod }} to the object store failed in the last 15 minutes',
        severity='critical',
    ),
    AlertRule(
        uid='cnpg-backup-stale',
        title='No PostgreSQL base backup for 36 hours',
        expr=(
            '(time() - max by (cluster) (cnpg_backup_stopped_at_seconds{phase="completed"}))'
            ' > bool 129600'
        ),
        summary='Cluster {{ $labels.cluster }} has no completed base backup in 36 hours, or none at all',
        for_='0s',
        severity='critical',
        no_data_state='Alerting',
    ),
    AlertRule(
        uid='paperless-backup-stale',
        title='No Paperless restic backup for 36 hours',
        expr=(
            '(time() - max by (namespace, cronjob)'
            ' (kube_cronjob_status_last_successful_time{namespace="paperless", cronjob="paperless-backup"}))'
            ' > bool 129600'
        ),
        summary='The {{ $labels.cronjob }} CronJob has not succeeded in 36 hours, or does not exist',
        for_='0s',
        severity='critical',
        no_data_state='Alerting',
    ),
    # Mimir rejects a write (HTTP 400) for too many labels, a series limit or old samples, and Alloy
    # then drops the whole batch of 2,000 samples without any other sign. This went unnoticed for a
    # day on 2026-10-17 (about 1% of all samples, see ADR-0026).
    AlertRule(
        uid='mimir-samples-discarded',
        title='Mimir is discarding samples',
        expr='sum by (reason) (increase(cortex_discarded_samples_total[10m])) > bool 0',
        summary='Mimir discarded samples (reason {{ $labels.reason }}) in the last 10 minutes; Alloy drops whole batches',
        for_='10m',
        severity='critical',
    ),
    # The scrape-down rule cannot fire when the pod is gone, because then no `up` series exists.
    # Tandoor's backups are covered by `cnpg-backup-stale` (`tandoor-db`) and
    # `longhorn-volume-backup-stale` (`mediafiles`).
    AlertRule(
        uid='tandoor-down',
        title='Tandoor is not serving',
        expr='up{job="tandoor"} == bool 0',
        summary='Tandoor does not answer its metrics scrape, or its pod does not exist',
        for_='5m',
        severity='critical',
        no_data_state='Alerting',
    ),
    AlertRule(
        uid='tandoor-server-errors',
        title='Tandoor returns server errors',
        expr=(
            'sum(rate(django_http_responses_total_by_status_total{job="tandoor", status=~"5.."}[5m]))'
            ' > bool 0.05'
        ),
        summary='Tandoor answers more than one request in 20 seconds with a 5xx status',
        for_='10m',
    ),
    # NetBox's backups are covered by `cnpg-backup-stale` (`netbox-db`) and
    # `longhorn-volume-backup-stale` (`netbox-media`).
    AlertRule(
        uid='netbox-down',
        title='NetBox is not serving',
        expr='up{job="netbox"} == bool 0',
        summary='NetBox does not answer its metrics scrape, or its pod does not exist',
        for_='5m',
        severity='critical',
        no_data_state='Alerting',
    ),
    AlertRule(
        uid='netbox-server-errors',
        title='NetBox returns server errors',
        expr=(
            'sum(rate(django_http_responses_total_by_status_total{job="netbox", status=~"5.."}[5m]))'
            ' > bool 0.05'
        ),
        summary='NetBox answers more than one request in 20 seconds with a 5xx status',
        for_='10m',
    ),
    # Every MariaDB from `utils.mariadb` has a `<name>-mariadb-backup` CronJob. A CronJob that
    # never succeeded has no success time, so its creation time stands in.
    AlertRule(
        uid='mariadb-backup-stale',
        title='No MariaDB backup for 36 hours',
        expr=(
            '(time() - max by (namespace, cronjob) ('
            'kube_cronjob_status_last_successful_time{cronjob=~".+-mariadb-backup"}'
            ' or kube_cronjob_created{cronjob=~".+-mariadb-backup"})) > bool 129600'
        ),
        summary='The {{ $labels.namespace }}/{{ $labels.cronjob }} CronJob has not succeeded in 36 hours',
        for_='0s',
        severity='critical',
    ),
    # TeslaLogger has no metrics endpoint; kube-state-metrics shows whether its workloads serve.
    # Missed drives cannot be backfilled. Backups: `mariadb-backup-stale`, `longhorn-volume-backup-stale`.
    AlertRule(
        uid='teslalogger-down',
        title='TeslaLogger is not running',
        expr=(
            'kube_deployment_status_replicas_available{namespace="teslalogger"} == bool 0'
            ' or kube_statefulset_status_replicas_ready{namespace="teslalogger"} == bool 0'
        ),
        summary='TeslaLogger workload {{ $labels.deployment }}{{ $labels.statefulset }} has no ready replica; drives are not logged',
        for_='10m',
        no_data_state='Alerting',
    ),
    # Absence of agent-status buckets is normal when no agents are enrolled; scrape failures
    # are separately reported by the generic target-down rule.
    AlertRule(
        uid='wazuh-agent-disconnected',
        title='Wazuh agent disconnected',
        expr='wazuh_agent_status_count{status="disconnected"} > bool 0',
        summary='One or more Wazuh agents have been disconnected from the manager',
        for_='1h',
        no_data_state='OK',
    ),
    AlertRule(
        uid='wazuh-indexer-red',
        title='Wazuh indexer cluster is red',
        expr='elasticsearch_cluster_health_status{color="red"} == bool 1',
        summary='Wazuh indexer cluster health is red',
        for_='10m',
        no_data_state='OK',
    ),
    AlertRule(
        uid='wazuh-indexer-disk-low',
        title='Wazuh indexer disk below 20% available',
        expr=(
            '(kubelet_volume_stats_available_bytes{namespace="wazuh",'
            ' persistentvolumeclaim="data-wazuh-indexer-0"}'
            ' / kubelet_volume_stats_capacity_bytes{namespace="wazuh",'
            ' persistentvolumeclaim="data-wazuh-indexer-0"}) < bool 0.2'
        ),
        summary='Wazuh indexer PVC has less than 20% disk space available',
        for_='30m',
        no_data_state='OK',
    ),
    # This workload must exist; no kube-state-metrics series is treated as an outage.
    AlertRule(
        uid='wazuh-manager-down',
        title='Wazuh manager is not ready',
        expr=(
            'kube_statefulset_status_replicas_ready{namespace="wazuh",'
            ' statefulset="wazuh-manager"} == bool 0'
        ),
        summary='Wazuh manager StatefulSet has no ready replica',
        for_='10m',
        no_data_state='Alerting',
    ),
    # The exporter reports zero when no recent high-level events exist; lack of events is healthy.
    AlertRule(
        uid='wazuh-high-level-event',
        title='Wazuh high-level alert event',
        expr='wazuh_high_level_events > bool 0',
        summary='Wazuh indexed a rule-level 12+ alert in the last 15 minutes',
        for_='1m',
        no_data_state='OK',
    ),
    AlertRule(
        uid='certificate-expiring',
        title='Certificate expires within 14 days',
        expr='(certmanager_certificate_expiration_timestamp_seconds - time()) < bool 1209600',
        summary='Certificate {{ $labels.namespace }}/{{ $labels.name }} expires in under 14 days; renewal is failing',
        for_='1h',
        severity='critical',
    ),
    # Ported from the legacy Prometheus (ServiceDown, ServiceDownSlow, SSLCertExpiringSoon). The
    # probes come from Alloy's blackbox exporter, with the legacy job names.
    AlertRule(
        uid='probe-failing',
        title='Website or service probe failing',
        expr='probe_success{job="blackbox"} == bool 0',
        summary='{{ $labels.instance }} has failed its probe for 10 minutes',
        for_='10m',
        severity='critical',
        # No series at all means the target list or the probes themselves are broken.
        no_data_state='Alerting',
    ),
    AlertRule(
        uid='probe-failing-slow',
        title='Slow-probed website failing',
        expr='probe_success{job="blackbox-slow"} == bool 0',
        summary='{{ $labels.instance }} has failed its probe for 15 minutes',
        for_='15m',
        severity='critical',
    ),
    AlertRule(
        uid='probe-certificate-expiring',
        title='Probed certificate expires within 7 days',
        expr='(probe_ssl_earliest_cert_expiry{job=~"blackbox|blackbox-slow"} - time()) < bool 604800',
        summary='The certificate of {{ $labels.instance }} expires in under 7 days',
        for_='10m',
    ),
    # A firewall that is down cannot page while it is the only uplink; `Scrape target down` covers
    # both OPNsense scrape jobs.
    AlertRule(
        uid='opnsense-api-down',
        title='OPNsense API not answering the exporter',
        expr='opnsense_up == bool 0',
        summary='The OPNsense exporter cannot read the firewall API (down, wrong key or missing privilege)',
        for_='10m',
        no_data_state='Alerting',
    ),
    AlertRule(
        uid='opnsense-gateway-unhealthy',
        title='OPNsense gateway offline or degraded',
        expr=(
            '(opnsense_gateways_status == bool 0) + (opnsense_gateways_status == bool 4)'
            ' + (opnsense_gateways_status == bool 5)'
        ),
        summary='Gateway {{ $labels.name }} ({{ $labels.address }}) is offline, losing packets or above its latency threshold',
        for_='5m',
    ),
    AlertRule(
        uid='opnsense-pf-states-high',
        title='OPNsense state table above 80%',
        expr='(opnsense_pf_states_current / opnsense_pf_states_limit) > bool 0.8',
        summary='The pf state table of OPNsense is above 80% of its limit',
        for_='10m',
    ),
]


def _render_rule(
    rule: AlertRule | LokiAlertRule,
    *,
    datasource_uid: str,
    relative_time_range: dict[str, int],
    model: dict[str, t.Any],
) -> dict[str, t.Any]:
    return {
        'uid': rule.uid,
        'title': rule.title,
        'condition': 'C',
        'data': [
            {
                'refId': 'A',
                'relativeTimeRange': relative_time_range,
                'datasourceUid': datasource_uid,
                'model': model,
            },
            {
                'refId': 'B',
                'datasourceUid': '__expr__',
                'model': {
                    'refId': 'B',
                    'type': 'reduce',
                    'expression': 'A',
                    'reducer': 'last',
                    'settings': {'mode': 'dropNN'},
                    'datasource': EXPRESSION_DATASOURCE,
                },
            },
            {
                'refId': 'C',
                'datasourceUid': '__expr__',
                'model': {
                    'refId': 'C',
                    'type': 'threshold',
                    'expression': 'B',
                    'conditions': [{'evaluator': {'type': 'gt', 'params': [0]}}],
                    'datasource': EXPRESSION_DATASOURCE,
                },
            },
        ],
        'noDataState': rule.no_data_state,
        'execErrState': 'Error',
        'for': rule.for_,
        'annotations': {'summary': rule.summary.replace('$', '$$')},
        'labels': {'severity': rule.severity},
    }


def _loki_rule(rule: LokiAlertRule) -> dict[str, t.Any]:
    """Render an alert rule whose query is evaluated by Loki."""
    return _render_rule(
        rule,
        datasource_uid=LOKI_DATASOURCE_UID,
        relative_time_range={'from': 1800, 'to': 0},
        model={
            'refId': 'A',
            'expr': rule.expr,
            'queryType': 'instant',
            'editorMode': 'code',
            'direction': 'backward',
            'intervalMs': 1000,
            'maxDataPoints': 43200,
        },
    )


def _rule(rule: AlertRule) -> dict[str, t.Any]:
    # Keep the Mimir provisioning model byte-for-byte stable.
    return _render_rule(
        rule,
        datasource_uid=MIMIR_DATASOURCE_UID,
        relative_time_range={'from': 600, 'to': 0},
        model={
            'refId': 'A',
            'expr': rule.expr,
            'instant': True,
            'intervalMs': 1000,
            'maxDataPoints': 43200,
        },
    )


def provisioning() -> dict[str, t.Any]:
    """Alert rule provisioning document (apiVersion 1 file format)."""
    return {
        'apiVersion': 1,
        'deleteRules': [{'orgId': 1, 'uid': uid} for uid in REMOVED_RULE_UIDS],
        'groups': [
            {
                'orgId': 1,
                'name': 'homelab',
                'folder': FOLDER,
                'interval': '1m',
                'rules': (
                    [_rule(rule) for rule in RULES] + [_loki_rule(rule) for rule in LOKI_RULES]
                ),
            },
        ],
    }
