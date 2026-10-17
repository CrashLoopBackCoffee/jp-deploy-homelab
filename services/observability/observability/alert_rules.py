"""Grafana-managed alert rules, provisioned from code.

Each expression uses a `bool` comparison, so it returns 1 for series in a bad state and 0
otherwise; the shared reduce and threshold nodes alert on a last value above zero.
"""

import dataclasses
import typing as t

MIMIR_DATASOURCE_UID = 'mimir'
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
    AlertRule(
        uid='certificate-expiring',
        title='Certificate expires within 14 days',
        expr='(certmanager_certificate_expiration_timestamp_seconds - time()) < bool 1209600',
        summary='Certificate {{ $labels.namespace }}/{{ $labels.name }} expires in under 14 days; renewal is failing',
        for_='1h',
        severity='critical',
    ),
]


def _rule(rule: AlertRule) -> dict[str, t.Any]:
    return {
        'uid': rule.uid,
        'title': rule.title,
        'condition': 'C',
        'data': [
            {
                'refId': 'A',
                'relativeTimeRange': {'from': 600, 'to': 0},
                'datasourceUid': MIMIR_DATASOURCE_UID,
                'model': {
                    'refId': 'A',
                    'expr': rule.expr,
                    'instant': True,
                    'intervalMs': 1000,
                    'maxDataPoints': 43200,
                },
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
        # Grafana expands $VAR in provisioning files; `$$` yields a literal `$` for templates.
        'annotations': {'summary': rule.summary.replace('$', '$$')},
        'labels': {'severity': rule.severity},
    }


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
                'rules': [_rule(rule) for rule in RULES],
            },
        ],
    }
