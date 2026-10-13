"""Provisioned Grafana dashboards, generated from compact panel definitions."""

import dataclasses
import json

MIMIR_DATASOURCE_UID = 'mimir'
LOKI_DATASOURCE_UID = 'loki'
PANEL_WIDTH = 12
PANEL_HEIGHT = 8


@dataclasses.dataclass(frozen=True)
class Panel:
    title: str
    expr: str
    unit: str = 'short'
    kind: str = 'timeseries'
    legend: str = ''


def _panel(panel: Panel, index: int) -> dict:
    return {
        'id': index + 1,
        'type': panel.kind,
        'title': panel.title,
        'datasource': {'type': 'prometheus', 'uid': MIMIR_DATASOURCE_UID},
        'gridPos': {
            'x': (index % 2) * PANEL_WIDTH,
            'y': (index // 2) * PANEL_HEIGHT,
            'w': PANEL_WIDTH,
            'h': PANEL_HEIGHT,
        },
        'fieldConfig': {'defaults': {'unit': panel.unit}, 'overrides': []},
        'targets': [
            {
                'refId': 'A',
                'expr': panel.expr,
                'legendFormat': panel.legend,
                'datasource': {'type': 'prometheus', 'uid': MIMIR_DATASOURCE_UID},
            },
        ],
    }


def _logs_panel(index: int) -> dict:
    return {
        'id': index + 1,
        'type': 'logs',
        'title': 'Warnings and errors in logs',
        'datasource': {'type': 'loki', 'uid': LOKI_DATASOURCE_UID},
        'gridPos': {'x': 0, 'y': (index // 2) * PANEL_HEIGHT, 'w': 2 * PANEL_WIDTH, 'h': 12},
        'targets': [
            {
                'refId': 'A',
                'expr': '{namespace=~".+"} |~ "(?i)(warn|error)"',
                'datasource': {'type': 'loki', 'uid': LOKI_DATASOURCE_UID},
            },
        ],
    }


OVERVIEW_PANELS = [
    Panel('Scrape targets up', 'sum(up)', kind='stat'),
    Panel('Scrape targets down', 'count(up == 0) or vector(0)', kind='stat'),
    Panel(
        'Node CPU used',
        '1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m]))',
        'percentunit',
        legend='{{instance}}',
    ),
    Panel(
        'Node memory used',
        '1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes',
        'percentunit',
        legend='{{instance}}',
    ),
    Panel(
        'Filesystem used',
        '1 - node_filesystem_avail_bytes{fstype=~"ext4|xfs", mountpoint!~"/var/lib/(k0s|kubelet)/.*"}'
        ' / node_filesystem_size_bytes{fstype=~"ext4|xfs", mountpoint!~"/var/lib/(k0s|kubelet)/.*"}',
        'percentunit',
        legend='{{mountpoint}}',
    ),
    Panel(
        'Persistent volume used',
        'kubelet_volume_stats_used_bytes / kubelet_volume_stats_capacity_bytes',
        'percentunit',
        legend='{{namespace}}/{{persistentvolumeclaim}}',
    ),
    Panel(
        'Pod restarts (last hour)',
        'topk(10, increase(kube_pod_container_status_restarts_total[1h]) > 0)',
        legend='{{namespace}}/{{pod}}',
    ),
    Panel(
        'Pods not running',
        'sum by (phase) (kube_pod_status_phase{phase=~"Pending|Failed|Unknown"} == 1)',
        legend='{{phase}}',
    ),
]

BACKUP_PANELS = [
    Panel(
        'PostgreSQL base backup age',
        'time() - max by (cluster) (cnpg_backup_stopped_at_seconds{phase="completed"})',
        's',
        kind='stat',
    ),
    Panel(
        'PostgreSQL WAL seconds since last archival',
        'cnpg_pg_stat_archiver_seconds_since_last_archival',
        's',
        legend='{{pod}}',
    ),
    Panel(
        'PostgreSQL WAL archive failures (15 min)',
        'increase(cnpg_pg_stat_archiver_failed_count[15m])',
        legend='{{pod}}',
    ),
    Panel(
        'Certificate days until expiry',
        '(certmanager_certificate_expiration_timestamp_seconds - time()) / 86400',
        legend='{{namespace}}/{{name}}',
    ),
    Panel(
        'Longhorn disk used',
        'longhorn_disk_usage_bytes / longhorn_disk_capacity_bytes',
        'percentunit',
        legend='{{node}} {{disk}}',
    ),
    Panel(
        'Longhorn volume robustness (1 healthy, 2 degraded, 3 faulted)',
        'longhorn_volume_robustness',
        legend='{{volume}}',
    ),
]


def _dashboard(uid: str, title: str, panels: list[Panel], with_logs: bool = False) -> str:
    rendered = [_panel(panel, index) for index, panel in enumerate(panels)]
    if with_logs:
        rendered.append(_logs_panel(len(panels)))
    return json.dumps(
        {
            'uid': uid,
            'title': title,
            'tags': ['homelab'],
            'timezone': 'browser',
            'schemaVersion': 39,
            'refresh': '1m',
            'time': {'from': 'now-6h', 'to': 'now'},
            'panels': rendered,
        },
        indent=2,
    )


def provisioning_files() -> dict[str, str]:
    """File name to dashboard JSON, ready for a ConfigMap."""
    return {
        'overview.json': _dashboard('homelab-overview', 'Cluster overview', OVERVIEW_PANELS, True),
        'backups.json': _dashboard('homelab-backups', 'Backups and storage', BACKUP_PANELS),
    }
