"""Provisioned Grafana dashboards.

Generated dashboards are built from compact panel definitions. Community dashboards are vendored
unchanged under `assets/grafana/dashboards` (source and revision below) and adapted when rendered:
their datasource inputs and variables are pointed at the provisioned datasources.
"""

import dataclasses
import json
import pathlib
import re
import typing as t

MIMIR_DATASOURCE_UID = 'mimir'
LOKI_DATASOURCE_UID = 'loki'
WAZUH_VULNERABILITIES_UID = 'wazuh-live-vulnerabilities'
WAZUH_INVENTORY_UID = 'wazuh-live-inventory'
WAZUH_PROCESSES_UID = 'wazuh-live-processes'
WAZUH_PORTS_UID = 'wazuh-live-ports'
WAZUH_SYSTEM_UID = 'wazuh-live-system'
WAZUH_AGENT_STATUS_UID = 'wazuh-live-agent-status'
WAZUH_ALERTS_UID = 'wazuh-live-alerts'
EXPRESSION_DATASOURCE = {'type': '__expr__', 'uid': '__expr__'}
PANEL_WIDTH = 12
PANEL_HEIGHT = 8
LOGS_HEIGHT = 14

COMMUNITY_DIR = pathlib.Path(__file__).parent.parent / 'assets' / 'grafana' / 'dashboards'
# The CloudNativePG dashboard reads a kube-prometheus recording rule that this stack does not run,
# so it is replaced by the raw cAdvisor expression it is defined from.
_CPU_RECORDING_RULE = re.compile(
    r'node_namespace_pod_container:container_cpu_usage_seconds_total:sum_irate\{([^}]*)\}'
)
# File name -> grafana.com dashboard id and revision it was downloaded at.
COMMUNITY_DASHBOARDS = {
    'node-exporter-full.json': (1860, 101),
    'cloudnativepg.json': (20417, 4),
    'longhorn.json': (16888, 35),
    'traefik.json': (17347, 7),
}
# Dashboards exported from the legacy Grafana (ADR-0023). They name their datasource by its old name
# or UID, which is pointed at Mimir when they are rendered.
LEGACY_DASHBOARDS = (
    'blackbox-exporter.json',  # "Prometheus Blackbox Exporter"
    'status.json',  # "Status"
    'pretix.json',  # "Pretix"
    'wordpress-core-updates.json',  # "WordPress Core Updates"
)
_LEGACY_PROMETHEUS_DATASOURCES = {'Prometheus', 'PBFA97CFB590B2093'}


@dataclasses.dataclass(frozen=True)
class Panel:
    title: str
    expr: str
    unit: str = 'short'
    kind: str = 'timeseries'
    legend: str = ''
    datasource: str = 'prometheus'
    stack: bool = False
    # Further series for the same panel as (expression, legend) pairs.
    extra: tuple[tuple[str, str], ...] = ()
    width: int = PANEL_WIDTH
    height: int = PANEL_HEIGHT
    description: str = ''
    # Legend as a table of mean and max sorted by mean, tooltip sorted by value.
    ranked: bool = False


@dataclasses.dataclass(frozen=True)
class Column:
    title: str
    expr: str
    unit: str
    # Draw the value as a bar relative to the column's maximum.
    bar: bool = False


@dataclasses.dataclass(frozen=True)
class LabelColumn:
    label: str
    title: str
    # Data link on the cell; Grafana interpolates `${__value.raw}` and `${__url_time_range}`.
    link: str = ''


@dataclasses.dataclass(frozen=True)
class Table:
    """Instant queries joined on their labels into one row per series, sorted by the first column."""

    title: str
    labels: tuple[LabelColumn, ...]
    columns: tuple[Column, ...]
    description: str = ''
    width: int = 2 * PANEL_WIDTH
    height: int = 12


def _datasource(kind: str) -> dict[str, str]:
    datasources = {
        'loki': ('loki', LOKI_DATASOURCE_UID),
        'opensearch-vulnerabilities': (
            'grafana-opensearch-datasource',
            WAZUH_VULNERABILITIES_UID,
        ),
        'opensearch-inventory': ('grafana-opensearch-datasource', WAZUH_INVENTORY_UID),
        'opensearch-processes': ('grafana-opensearch-datasource', WAZUH_PROCESSES_UID),
        'opensearch-ports': ('grafana-opensearch-datasource', WAZUH_PORTS_UID),
        'opensearch-system': ('grafana-opensearch-datasource', WAZUH_SYSTEM_UID),
        'opensearch-agent-status': (
            'grafana-opensearch-datasource',
            WAZUH_AGENT_STATUS_UID,
        ),
        'opensearch-alerts': ('grafana-opensearch-datasource', WAZUH_ALERTS_UID),
        'prometheus': ('prometheus', MIMIR_DATASOURCE_UID),
    }
    plugin_type, uid = datasources[kind]
    return {'type': plugin_type, 'uid': uid}


def _panel(panel: Panel, index: int, grid_pos: dict[str, int]) -> dict:
    datasource = _datasource(panel.datasource)
    definition: dict[str, t.Any] = {
        'id': index + 1,
        'type': panel.kind,
        'title': panel.title,
        'datasource': datasource,
        'gridPos': grid_pos,
        'targets': [
            {
                'refId': chr(ord('A') + offset),
                'expr': expr,
                'legendFormat': legend,
                'datasource': datasource,
            }
            for offset, (expr, legend) in enumerate(((panel.expr, panel.legend), *panel.extra))
        ],
    }
    if panel.description:
        definition['description'] = panel.description
    if panel.kind != 'logs':
        defaults: dict[str, t.Any] = {'unit': panel.unit}
        if panel.stack:
            defaults['custom'] = {'stacking': {'mode': 'normal'}, 'fillOpacity': 30}
        definition['fieldConfig'] = {'defaults': defaults, 'overrides': []}
    if panel.ranked:
        definition['options'] = {
            'legend': {
                'showLegend': True,
                'displayMode': 'table',
                'placement': 'right' if panel.width == 2 * PANEL_WIDTH else 'bottom',
                'calcs': ['mean', 'max'],
                'sortBy': 'Mean',
                'sortDesc': True,
            },
            'tooltip': {'mode': 'multi', 'sort': 'desc'},
        }
    return definition


def _table(table: Table, index: int, grid_pos: dict[str, int]) -> dict:
    datasource = _datasource('prometheus')
    refs = [chr(ord('A') + offset) for offset in range(len(table.columns))]
    label_names = [label.label for label in table.labels]
    overrides: list[dict[str, t.Any]] = []
    for column in table.columns:
        properties: list[dict[str, t.Any]] = [{'id': 'unit', 'value': column.unit}]
        if column.bar:
            properties += [
                {
                    'id': 'custom.cellOptions',
                    'value': {'type': 'gauge', 'mode': 'basic', 'valueDisplayMode': 'text'},
                },
                {'id': 'min', 'value': 0},
                # Scale the bar to this column's maximum rather than the maximum of all columns.
                {'id': 'fieldMinMax', 'value': True},
            ]
        overrides.append(
            {'matcher': {'id': 'byName', 'options': column.title}, 'properties': properties}
        )
    for label in table.labels:
        if label.link:
            overrides.append(
                {
                    'matcher': {'id': 'byName', 'options': label.title},
                    'properties': [
                        {
                            'id': 'links',
                            'value': [{'title': f'Filter by {label.title}', 'url': label.link}],
                        }
                    ],
                }
            )
    return {
        'id': index + 1,
        'type': 'table',
        'title': table.title,
        'description': table.description,
        'datasource': datasource,
        'gridPos': grid_pos,
        'targets': [
            {
                'refId': ref,
                'expr': column.expr,
                'instant': True,
                'range': False,
                'format': 'table',
                'datasource': datasource,
            }
            for ref, column in zip(refs, table.columns, strict=True)
        ],
        'transformations': [
            {'id': 'merge', 'options': {}},
            {
                'id': 'organize',
                'options': {
                    'excludeByName': {'Time': True},
                    'renameByName': {
                        **{label.label: label.title for label in table.labels},
                        **{
                            f'Value #{ref}': column.title
                            for ref, column in zip(refs, table.columns, strict=True)
                        },
                    },
                    'indexByName': {
                        name: position
                        for position, name in enumerate(
                            [*label_names, *(f'Value #{ref}' for ref in refs)]
                        )
                    },
                },
            },
        ],
        'fieldConfig': {'defaults': {}, 'overrides': overrides},
        'options': {
            'showHeader': True,
            'cellHeight': 'sm',
            'sortBy': [{'displayName': table.columns[0].title, 'desc': True}],
        },
    }


def _layout(panels: t.Sequence[Panel | Table]) -> list[dict]:
    """Panels flow left to right in rows of 24 units; a logs panel takes the full width."""
    rendered = []
    x = y = row_height = 0
    for index, panel in enumerate(panels):
        if isinstance(panel, Panel) and panel.kind == 'logs':
            width, height = 2 * PANEL_WIDTH, LOGS_HEIGHT
        else:
            width, height = panel.width, panel.height
        if x + width > 2 * PANEL_WIDTH:
            y += row_height
            x = row_height = 0
        grid_pos = {'x': x, 'y': y, 'w': width, 'h': height}
        if isinstance(panel, Table):
            rendered.append(_table(panel, index, grid_pos))
        else:
            rendered.append(_panel(panel, index, grid_pos))
        x += width
        row_height = max(row_height, height)
    return rendered


def _query_variable(
    name: str, query: str, datasource: str = 'prometheus', all_value: str = '.+'
) -> dict:
    return {
        'name': name,
        'type': 'query',
        'datasource': _datasource(datasource),
        'query': query,
        'refresh': 2,
        'multi': True,
        'includeAll': True,
        'allValue': all_value,
        'current': {'selected': True, 'text': 'All', 'value': '$__all'},
    }


def _textbox_variable(name: str, label: str) -> dict:
    return {'name': name, 'label': label, 'type': 'textbox', 'query': '', 'current': {'value': ''}}


def _dashboard(
    uid: str,
    title: str,
    panels: t.Sequence[Panel | Table],
    variables: list[dict] | None = None,
) -> str:
    return json.dumps(
        {
            'uid': uid,
            'title': title,
            'tags': ['homelab'],
            'timezone': 'browser',
            'schemaVersion': 39,
            'refresh': '1m',
            'time': {'from': 'now-6h', 'to': 'now'},
            'templating': {'list': variables or []},
            'panels': _layout(panels),
        },
        indent=2,
    )


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
        'Longhorn volume backup age',
        'time() - longhorn_volume_last_backup_at',
        's',
        legend='{{pvc_namespace}}/{{pvc}}',
    ),
]

_WORKLOAD_SELECTOR = 'namespace=~"$namespace", container!="", pod!=""'
WORKLOAD_VARIABLES = [_query_variable('namespace', 'label_values(kube_pod_info, namespace)')]
WORKLOAD_PANELS = [
    Panel(
        'Pods by phase',
        'sum by (phase) (kube_pod_status_phase{namespace=~"$namespace"} == 1)',
        legend='{{phase}}',
        stack=True,
    ),
    Panel(
        'Deployments and StatefulSets missing replicas',
        'sum by (namespace, deployment) (kube_deployment_spec_replicas{namespace=~"$namespace"}'
        ' - kube_deployment_status_replicas_available{namespace=~"$namespace"}) > 0'
        ' or sum by (namespace, statefulset) (kube_statefulset_replicas{namespace=~"$namespace"}'
        ' - kube_statefulset_status_replicas_ready{namespace=~"$namespace"}) > 0',
        legend='{{namespace}}/{{deployment}}{{statefulset}}',
    ),
    Panel(
        'CPU used by pod (top 15)',
        f'topk(15, sum by (namespace, pod) (rate(container_cpu_usage_seconds_total{{{_WORKLOAD_SELECTOR}}}[5m])))',
        legend='{{namespace}}/{{pod}}',
    ),
    Panel(
        'CPU used vs requested by namespace (cores)',
        f'sum by (namespace) (rate(container_cpu_usage_seconds_total{{{_WORKLOAD_SELECTOR}}}[5m]))',
        legend='used {{namespace}}',
        extra=(
            (
                'sum by (namespace) (kube_pod_container_resource_requests'
                '{resource="cpu", namespace=~"$namespace"})',
                'requested {{namespace}}',
            ),
        ),
    ),
    Panel(
        'Memory working set by pod (top 15)',
        f'topk(15, sum by (namespace, pod) (container_memory_working_set_bytes{{{_WORKLOAD_SELECTOR}}}))',
        'bytes',
        legend='{{namespace}}/{{pod}}',
    ),
    Panel(
        'Memory working set vs requested by namespace',
        f'sum by (namespace) (container_memory_working_set_bytes{{{_WORKLOAD_SELECTOR}}})',
        'bytes',
        legend='used {{namespace}}',
        extra=(
            (
                'sum by (namespace) (kube_pod_container_resource_requests'
                '{resource="memory", namespace=~"$namespace"})',
                'requested {{namespace}}',
            ),
        ),
    ),
    Panel(
        'Container restarts (last hour)',
        'topk(15, increase(kube_pod_container_status_restarts_total{namespace=~"$namespace"}[1h]) > 0)',
        legend='{{namespace}}/{{pod}} {{container}}',
    ),
    Panel(
        'Persistent volume used',
        'kubelet_volume_stats_used_bytes{namespace=~"$namespace"}'
        ' / kubelet_volume_stats_capacity_bytes{namespace=~"$namespace"}',
        'percentunit',
        legend='{{namespace}}/{{persistentvolumeclaim}}',
    ),
    Panel(
        'Network received by pod (top 15)',
        'topk(15, sum by (namespace, pod) (rate(container_network_receive_bytes_total{namespace=~"$namespace", pod!=""}[5m])))',
        'Bps',
        legend='{{namespace}}/{{pod}}',
    ),
    Panel(
        'Network sent by pod (top 15)',
        'topk(15, sum by (namespace, pod) (rate(container_network_transmit_bytes_total{namespace=~"$namespace", pod!=""}[5m])))',
        'Bps',
        legend='{{namespace}}/{{pod}}',
    ),
]

# Alerting cannot report its own failure, so this is the place to see the pipeline itself fail.
SELF_HEALTH_PANELS = [
    Panel(
        'Mimir: samples received per second',
        'sum(rate(cortex_distributor_received_samples_total[5m]))',
        'ops',
    ),
    Panel('Mimir: active series', 'sum(cortex_ingester_active_series)'),
    Panel(
        'Mimir: discarded samples per second',
        'sum by (reason) (rate(cortex_discarded_samples_total[5m]))',
        'ops',
        legend='{{reason}}',
    ),
    Panel(
        'Mimir: 5xx responses per second',
        'sum by (route) (rate(cortex_request_duration_seconds_count{status_code=~"5.."}[5m]))',
        'ops',
        legend='{{route}}',
    ),
    Panel(
        'Mimir: object store failures per second (QuObjects)',
        'sum by (operation) (rate(thanos_objstore_bucket_operation_failures_total[5m]))',
        'ops',
        legend='{{operation}}',
    ),
    Panel(
        'Mimir: seconds since last block upload',
        'time() - max(cortex_ingester_shipper_last_successful_upload_timestamp_seconds)',
        's',
        legend='last block upload',
    ),
    Panel(
        'Mimir: compactor seconds since last successful run',
        'time() - max(cortex_compactor_last_successful_run_timestamp_seconds)',
        's',
    ),
    Panel(
        'Loki: log lines received per second',
        'sum(rate(loki_distributor_lines_received_total[5m]))',
        'ops',
    ),
    Panel(
        'Loki: 5xx responses per second',
        'sum by (route) (rate(loki_request_duration_seconds_count{status_code=~"5.."}[5m]))',
        'ops',
        legend='{{route}}',
    ),
    Panel(
        'Loki: chunk flush failures per second',
        'sum(rate(loki_ingester_chunks_flush_failures_total[5m]))',
        'ops',
    ),
    Panel(
        'Alloy: failed samples per second to Mimir',
        'sum(rate(prometheus_remote_storage_samples_failed_total[5m]))',
        'ops',
        legend='failed per second',
    ),
    Panel(
        'Alloy: dropped log entries per second',
        'sum by (reason) (rate(loki_write_dropped_entries_total[5m]))',
        'ops',
        legend='{{reason}}',
    ),
    Panel('Alloy: resident memory', 'alloy_resources_process_resident_memory_bytes', 'bytes'),
    Panel(
        'Scrape duration by job (top 10)',
        'topk(10, max by (job) (scrape_duration_seconds))',
        's',
        legend='{{job}}',
    ),
    Panel(
        'Samples scraped by job (top 10)',
        'topk(10, sum by (job) (scrape_samples_scraped))',
        legend='{{job}}',
    ),
]

# The exporter runs one real speed test per scrape (every 30 minutes), so the series are sparse. Its
# `speedtest_download_bytes` and `speedtest_upload_bytes` are bytes per second. Despite their names
# (and the typo `jittter`), `speedtest_latency_seconds` and `speedtest_jittter_seconds` are milliseconds:
# a test on 2026-10-17 reported 7.99 and 0.401 for a link with a latency of about 8 ms.
SPEEDTEST_PANELS = [
    Panel(
        'Download and upload',
        'speedtest_download_bytes * 8',
        'bps',
        legend='download',
        extra=(('speedtest_upload_bytes * 8', 'upload'),),
    ),
    Panel(
        'Latency and jitter',
        'speedtest_latency_seconds',
        'ms',
        legend='latency',
        extra=(('speedtest_jittter_seconds', 'jitter'),),
    ),
    Panel('Download, last test', 'speedtest_download_bytes * 8', 'bps', kind='stat'),
    Panel('Upload, last test', 'speedtest_upload_bytes * 8', 'bps', kind='stat'),
    Panel('Test duration', 'script_duration_seconds{job="speedtest"}', 's'),
    Panel('Last test succeeded', 'script_success{job="speedtest"}', kind='stat'),
]

# Tandoor (django-prometheus, ENABLE_METRICS=1) scraped from `tandoor.tandoor.svc` as job `tandoor`.
# Latency comes from the per-view histogram summed by bucket: the overall histogram
# (`..._including_middlewares_seconds`) never counts a request in Tandoor (checked 2026-10-18). The
# per-view histogram has 17 buckets per view and method, so its series count grows with the pages
# that are used (about 190 series for 11 views; a few thousand if every view is opened).
_TANDOOR = 'job="tandoor"'
_TANDOOR_LATENCY = 'django_http_requests_latency_seconds_by_view_method'
_TANDOOR_POD = 'namespace="tandoor", container="tandoor"'
TANDOOR_PANELS = [
    Panel('Scrape up', f'up{{{_TANDOOR}}}', kind='stat'),
    Panel(
        'Requests per second',
        f'sum(rate(django_http_requests_total_by_method_total{{{_TANDOOR}}}[5m]))',
        'reqps',
        legend='requests',
    ),
    Panel(
        'Responses by status',
        f'sum by (status) (rate(django_http_responses_total_by_status_total{{{_TANDOOR}}}[5m]))',
        'reqps',
        legend='{{status}}',
        stack=True,
    ),
    Panel(
        'Server errors per second (5xx)',
        'sum(rate(django_http_responses_total_by_status_total'
        f'{{{_TANDOOR}, status=~"5.."}}[5m])) or vector(0)',
        'reqps',
        legend='5xx',
    ),
    Panel(
        'Request latency',
        f'histogram_quantile(0.5, sum by (le) (rate({_TANDOOR_LATENCY}_bucket{{{_TANDOOR}}}[5m])))',
        's',
        legend='p50',
        extra=(
            (
                f'histogram_quantile(0.95, sum by (le) (rate({_TANDOOR_LATENCY}_bucket{{{_TANDOOR}}}[5m])))',
                'p95',
            ),
            (
                f'histogram_quantile(0.99, sum by (le) (rate({_TANDOOR_LATENCY}_bucket{{{_TANDOOR}}}[5m])))',
                'p99',
            ),
        ),
    ),
    Panel(
        'Requests by view (top 8)',
        'topk(8, sum by (view) (rate(django_http_requests_total_by_view_transport_method_total'
        f'{{{_TANDOOR}}}[5m])))',
        'reqps',
        legend='{{view}}',
    ),
    Panel(
        'Slowest views, mean latency (top 8)',
        f'topk(8, sum by (view) (rate({_TANDOOR_LATENCY}_sum{{{_TANDOOR}}}[5m]))'
        f' / (sum by (view) (rate({_TANDOOR_LATENCY}_count{{{_TANDOOR}}}[5m])) > 0))',
        's',
        legend='{{view}}',
    ),
    Panel(
        'Records created per hour by model (top 8)',
        f'topk(8, sum by (model) (increase(django_model_inserts_total{{{_TANDOOR}}}[1h])))',
        legend='{{model}}',
    ),
    Panel(
        'CPU used vs requested (cores)',
        f'sum(rate(container_cpu_usage_seconds_total{{{_TANDOOR_POD}}}[5m]))',
        legend='used',
        extra=(
            (
                f'sum(kube_pod_container_resource_requests{{resource="cpu", {_TANDOOR_POD}}})',
                'requested',
            ),
        ),
    ),
    # The memory limit matters because PDF export (ENABLE_PDF_EXPORT) runs a browser.
    Panel(
        'Memory working set vs limit',
        f'sum(container_memory_working_set_bytes{{{_TANDOOR_POD}}})',
        'bytes',
        legend='used',
        extra=(
            (
                f'sum(kube_pod_container_resource_limits{{resource="memory", {_TANDOOR_POD}}})',
                'limit',
            ),
        ),
    ),
    Panel(
        'Container restarts (last hour)',
        'sum(increase(kube_pod_container_status_restarts_total{namespace="tandoor"}[1h])) or vector(0)',
        kind='stat',
    ),
    Panel(
        'Media volume used',
        'kubelet_volume_stats_used_bytes{namespace="tandoor", persistentvolumeclaim="mediafiles"}'
        ' / kubelet_volume_stats_capacity_bytes{namespace="tandoor", persistentvolumeclaim="mediafiles"}',
        'percentunit',
        kind='stat',
    ),
    Panel(
        'Database size',
        'cnpg_pg_database_size_bytes{namespace="tandoor", datname="tandoor"}',
        'bytes',
        legend='{{datname}}',
    ),
    Panel(
        'Database base backup age',
        'time() - max(cnpg_backup_stopped_at_seconds{cluster="tandoor-db", phase="completed"})',
        's',
        kind='stat',
    ),
    Panel(
        'Media volume backup age (Longhorn)',
        'time() - longhorn_volume_last_backup_at{pvc_namespace="tandoor", pvc="mediafiles"}'
        ' and longhorn_volume_last_backup_at{pvc_namespace="tandoor", pvc="mediafiles"} > 0',
        's',
        kind='stat',
    ),
    Panel(
        'Errors in the log (per interval)',
        f'sum(count_over_time({{{_TANDOOR_POD}}} |~ "(?i)(error|fatal|traceback)" [$__interval]))',
        datasource='loki',
        legend='errors',
    ),
    Panel('Logs', f'{{{_TANDOOR_POD}}}', kind='logs', datasource='loki'),
]

# NetBox (django-prometheus, METRICS_ENABLED) scraped from `netbox.netbox.svc` as job `netbox`.
# Latency comes from the per-view histogram summed by bucket; it has 17 buckets per view and method,
# so its series count grows with the pages that are used.
_NETBOX = 'job="netbox"'
_NETBOX_LATENCY = 'django_http_requests_latency_seconds_by_view_method'
_NETBOX_POD = 'namespace="netbox", container="netbox"'
NETBOX_PANELS = [
    Panel('Scrape up', f'up{{{_NETBOX}}}', kind='stat'),
    Panel(
        'Requests per second',
        f'sum(rate(django_http_requests_total_by_method_total{{{_NETBOX}}}[5m]))',
        'reqps',
        legend='requests',
    ),
    Panel(
        'Responses by status',
        f'sum by (status) (rate(django_http_responses_total_by_status_total{{{_NETBOX}}}[5m]))',
        'reqps',
        legend='{{status}}',
        stack=True,
    ),
    Panel(
        'Server errors per second (5xx)',
        'sum(rate(django_http_responses_total_by_status_total'
        f'{{{_NETBOX}, status=~"5.."}}[5m])) or vector(0)',
        'reqps',
        legend='5xx',
    ),
    Panel(
        'Request latency',
        f'histogram_quantile(0.5, sum by (le) (rate({_NETBOX_LATENCY}_bucket{{{_NETBOX}}}[5m])))',
        's',
        legend='p50',
        extra=(
            (
                f'histogram_quantile(0.95, sum by (le) (rate({_NETBOX_LATENCY}_bucket{{{_NETBOX}}}[5m])))',
                'p95',
            ),
            (
                f'histogram_quantile(0.99, sum by (le) (rate({_NETBOX_LATENCY}_bucket{{{_NETBOX}}}[5m])))',
                'p99',
            ),
        ),
    ),
    Panel(
        'Requests by view (top 8)',
        'topk(8, sum by (view) (rate(django_http_requests_total_by_view_transport_method_total'
        f'{{{_NETBOX}}}[5m])))',
        'reqps',
        legend='{{view}}',
    ),
    Panel(
        'Slowest views, mean latency (top 8)',
        f'topk(8, sum by (view) (rate({_NETBOX_LATENCY}_sum{{{_NETBOX}}}[5m]))'
        f' / (sum by (view) (rate({_NETBOX_LATENCY}_count{{{_NETBOX}}}[5m])) > 0))',
        's',
        legend='{{view}}',
    ),
    Panel(
        'CPU used vs requested (cores)',
        f'sum(rate(container_cpu_usage_seconds_total{{{_NETBOX_POD}}}[5m]))',
        legend='used',
        extra=(
            (
                f'sum(kube_pod_container_resource_requests{{resource="cpu", {_NETBOX_POD}}})',
                'requested',
            ),
        ),
    ),
    Panel(
        'Memory working set vs limit',
        f'sum(container_memory_working_set_bytes{{{_NETBOX_POD}}})',
        'bytes',
        legend='used',
        extra=(
            (
                f'sum(kube_pod_container_resource_limits{{resource="memory", {_NETBOX_POD}}})',
                'limit',
            ),
        ),
    ),
    Panel(
        'Container restarts (last hour)',
        'sum(increase(kube_pod_container_status_restarts_total{namespace="netbox"}[1h])) or vector(0)',
        kind='stat',
    ),
    Panel(
        'Media volume used',
        'kubelet_volume_stats_used_bytes{namespace="netbox", persistentvolumeclaim="netbox-media"}'
        ' / kubelet_volume_stats_capacity_bytes{namespace="netbox", persistentvolumeclaim="netbox-media"}',
        'percentunit',
        kind='stat',
    ),
    Panel(
        'Database size',
        'cnpg_pg_database_size_bytes{namespace="netbox", datname="netbox"}',
        'bytes',
        legend='{{datname}}',
    ),
    Panel(
        'Database base backup age',
        'time() - max(cnpg_backup_stopped_at_seconds{cluster="netbox-db", phase="completed"})',
        's',
        kind='stat',
    ),
    Panel(
        'Media volume backup age (Longhorn)',
        'time() - longhorn_volume_last_backup_at{pvc_namespace="netbox", pvc="netbox-media"}'
        ' and longhorn_volume_last_backup_at{pvc_namespace="netbox", pvc="netbox-media"} > 0',
        's',
        kind='stat',
    ),
    Panel(
        'Errors in the log (per interval)',
        f'sum(count_over_time({{{_NETBOX_POD}}} |~ "(?i)(error|fatal|traceback)" [$__interval]))',
        datasource='loki',
        legend='errors',
    ),
    Panel('Logs', f'{{{_NETBOX_POD}}}', kind='logs', datasource='loki'),
]

# OPNsense (ADR-0038): `opnsense` is the API exporter, `opnsense-node` the os-node_exporter plugin

# (FreeBSD names: wired/active/inactive/laundry/cache/free memory, no MemAvailable), `opnsense-syslog`
# the remote log. Gateway status codes: 0 offline, 1 online, 2 unknown, 3 pending, 4 packet loss,
# 5 latency, 6 forced offline.
_OPN = 'job="opnsense"'
_OPN_NODE = 'job="opnsense-node"'
_OPN_LOGS = 'job="opnsense-syslog"'
_FILTERLOG = f'{_OPN_LOGS}, app="filterlog", interface=~"$interface", action=~"$action"'
_OPN_BLOCKED = f'{_OPN_LOGS}, app="filterlog", action="block", interface=~"$interface"'
_OPN_NODE_CPUS = f'count(node_cpu_seconds_total{{{_OPN_NODE}, mode="idle"}})'
_OPN_FILESYSTEM = f'{_OPN_NODE}, fstype=~"ufs|zfs"'
OPNSENSE_PANELS = [
    Panel('API reachable', 'opnsense_up', kind='stat', width=4, height=4),
    Panel('node_exporter up', f'up{{{_OPN_NODE}}}', kind='stat', width=4, height=4),
    Panel('Services stopped', 'opnsense_services_stopped_total', kind='stat', width=4, height=4),
    Panel(
        'pf state table used',
        'opnsense_pf_states_current / opnsense_pf_states_limit',
        'percentunit',
        kind='stat',
        width=4,
        height=4,
    ),
    Panel(
        'mbuf clusters used',
        'opnsense_mbuf_clusters_current / opnsense_mbuf_clusters_limit',
        'percentunit',
        kind='stat',
        width=4,
        height=4,
    ),
    Panel(
        'CPU used',
        f'1 - avg(rate(node_cpu_seconds_total{{{_OPN_NODE}, mode="idle"}}[5m]))',
        'percentunit',
        kind='stat',
        width=4,
        height=4,
    ),
    Panel(
        'Gateway status',
        'opnsense_gateways_status',
        legend='{{name}}',
        description='0 offline, 1 online, 2 unknown, 3 pending, 4 packet loss, 5 latency, '
        '6 forced offline',
    ),
    Panel('Gateway RTT', 'opnsense_gateways_rtt_milliseconds', 'ms', legend='{{name}}'),
    Panel('Gateway RTT deviation', 'opnsense_gateways_rttd_milliseconds', 'ms', legend='{{name}}'),
    Panel('Gateway packet loss', 'opnsense_gateways_loss_percentage', 'percent', legend='{{name}}'),
    Panel(
        'Interface traffic in',
        'rate(opnsense_interfaces_received_bytes_total[5m]) * 8',
        'bps',
        legend='{{interface}}',
    ),
    Panel(
        'Interface traffic out',
        'rate(opnsense_interfaces_transmitted_bytes_total[5m]) * 8',
        'bps',
        legend='{{interface}}',
    ),
    Panel(
        'Interface errors',
        'rate(opnsense_interfaces_input_errors_total[5m])',
        legend='{{interface}} in',
        extra=(('rate(opnsense_interfaces_output_errors_total[5m])', '{{interface}} out'),),
    ),
    Panel(
        'Firewall blocked packets (inbound)',
        'rate(opnsense_firewall_in_ipv4_block_packets[5m])',
        'pps',
        legend='{{interface}}',
        extra=(('rate(opnsense_firewall_in_ipv6_block_packets[5m])', '{{interface}} v6'),),
    ),
    Panel(
        'Firewall passed packets (inbound)',
        'rate(opnsense_firewall_in_ipv4_pass_packets[5m])',
        'pps',
        legend='{{interface}}',
        extra=(('rate(opnsense_firewall_in_ipv6_pass_packets[5m])', '{{interface}} v6'),),
    ),
    Panel(
        'pf states',
        'opnsense_pf_states_current',
        legend='current',
        extra=(('opnsense_pf_states_limit', 'limit'),),
    ),
    Panel(
        'CPU by mode',
        f'sum by (mode) (rate(node_cpu_seconds_total{{{_OPN_NODE}, mode!="idle"}}[5m]))'
        f' / scalar({_OPN_NODE_CPUS})',
        'percentunit',
        legend='{{mode}}',
        stack=True,
    ),
    Panel(
        'Memory',
        f'node_memory_wired_bytes{{{_OPN_NODE}}}',
        'bytes',
        legend='wired',
        stack=True,
        extra=tuple(
            (f'node_memory_{name}_bytes{{{_OPN_NODE}}}', name)
            for name in ('active', 'inactive', 'laundry', 'cache', 'free')
        ),
    ),
    Panel(
        'Load average',
        f'node_load1{{{_OPN_NODE}}}',
        legend='1m',
        extra=((f'node_load5{{{_OPN_NODE}}}', '5m'), (f'node_load15{{{_OPN_NODE}}}', '15m')),
    ),
    Panel(
        'Filesystem used',
        f'1 - node_filesystem_avail_bytes{{{_OPN_FILESYSTEM}}}'
        f' / node_filesystem_size_bytes{{{_OPN_FILESYSTEM}}}',
        'percentunit',
        legend='{{mountpoint}}',
    ),
    Panel(
        'WireGuard peer traffic',
        'rate(opnsense_wireguard_peer_received_bytes_total[5m]) * 8',
        'bps',
        legend='{{peer_name}} in',
        extra=(
            (
                'rate(opnsense_wireguard_peer_transmitted_bytes_total[5m]) * 8',
                '{{peer_name}} out',
            ),
        ),
    ),
    Panel(
        'WireGuard handshake age',
        'time() - opnsense_wireguard_peer_last_handshake_seconds',
        's',
        legend='{{peer_name}}',
    ),
    Panel(
        'Devices in ARP table',
        'count by (interface_description) (opnsense_arp_table_entries)',
        legend='{{interface_description}}',
    ),
    Panel(
        'Exporter API errors',
        'sum by (endpoint) (rate(opnsense_exporter_endpoint_errors_total[5m]))',
        legend='{{endpoint}}',
    ),
    Table(
        'Services',
        labels=(LabelColumn('name', 'Service'), LabelColumn('description', 'Description')),
        columns=(Column('Running', 'opnsense_services_status', 'short'),),
    ),
]

# Trivy Operator (vulnerability reports only; per-CVE metrics are deliberately not enabled).
_TRIVY = 'job="trivy-operator"'
TRIVY_PANELS = [
    Panel(
        'Vulnerabilities by namespace and severity',
        f'sum by (namespace, severity) (trivy_image_vulnerabilities{{{_TRIVY}}})',
        legend='{{namespace}} / {{severity}}',
        stack=True,
    ),
    Panel(
        'Vulnerabilities by namespace',
        f'sum by (namespace) (trivy_image_vulnerabilities{{{_TRIVY}}})',
        legend='{{namespace}}',
    ),
    Panel(
        'Vulnerabilities by severity',
        f'sum by (severity) (trivy_image_vulnerabilities{{{_TRIVY}}})',
        legend='{{severity}}',
        kind='stat',
    ),
]

OPNSENSE_LOG_VARIABLES = [
    _query_variable('app', f'label_values({{{_OPN_LOGS}}}, app)', 'loki'),
    _query_variable(
        'interface', f'label_values({{{_OPN_LOGS}, app="filterlog"}}, interface)', 'loki'
    ),
    _query_variable('action', f'label_values({{{_OPN_LOGS}, app="filterlog"}}, action)', 'loki'),
    _textbox_variable('search', 'Search (regex, case-insensitive)'),
]
# Addresses and ports of firewall events are structured metadata, not labels (alloy config).
OPNSENSE_LOG_PANELS = [
    Panel(
        'Firewall events by action',
        f'sum by (action) (count_over_time({{{_FILTERLOG}}} [$__interval]))',
        legend='{{action}}',
        datasource='loki',
        stack=True,
    ),
    Panel(
        'Blocked by interface',
        f'sum by (interface) (count_over_time({{{_OPN_BLOCKED}}} [$__interval]))',
        legend='{{interface}}',
        datasource='loki',
        stack=True,
    ),
    Panel(
        'Top blocked sources',
        f'topk(10, sum by (src) (count_over_time({{{_OPN_BLOCKED}}} [$__interval])))',
        legend='{{src}}',
        datasource='loki',
        ranked=True,
    ),
    Panel(
        'Top blocked destination ports',
        f'topk(10, sum by (proto, dst_port) (count_over_time({{{_OPN_BLOCKED}}} [$__interval])))',
        legend='{{dst_port}}/{{proto}}',
        datasource='loki',
        ranked=True,
    ),
    Panel(
        'Log lines by app',
        f'sum by (app) (count_over_time({{{_OPN_LOGS}, app=~"$app"}} |~ "(?i)$search" [$__interval]))',
        legend='{{app}}',
        datasource='loki',
        stack=True,
    ),
    Panel(
        'Errors and warnings by app',
        f'sum by (app) (count_over_time({{{_OPN_LOGS}, app=~"$app",'
        ' severity=~"emergency|alert|critical|error|warning"} [$__interval]))',
        legend='{{app}}',
        datasource='loki',
        stack=True,
    ),
    Panel(
        'Firewall log',
        f'{{{_FILTERLOG}}} |~ "(?i)$search"',
        kind='logs',
        datasource='loki',
    ),
    Panel(
        'System log',
        f'{{{_OPN_LOGS}, app!="filterlog", app=~"$app"}} |~ "(?i)$search"',
        kind='logs',
        datasource='loki',
    ),
]

# Docker containers on hosts outside the cluster, from cAdvisor (job `ax51`; the Docker hosts of
# dockerhost join when its LAN targets move). Only cAdvisor series carry the `name` label, so the
# selector also keeps the node exporter and Docker engine targets of the same job out. Alloy drops the
# `container_label_*` labels but keeps the Compose project as `stack` (the container name for
# containers started without Compose). Series from before 2026-10-25 have no `stack`, so its All value
# also matches an empty label. There are no per-container disk I/O series, and IO pressure is always 0.
_DOCKER = 'job="ax51", name!="", stack=~"$stack", name=~"$name"'
# Containers in host network mode see every host interface; only a container's own `eth*`
# interfaces can be attributed to it.
_DOCKER_NETWORK = f'{_DOCKER}, interface=~"eth[0-9]+"'
_AX51_CORES = 'count(node_cpu_seconds_total{job="ax51", mode="idle"})'
_DOCKER_CPU = 'container_cpu_usage_seconds_total'
_DOCKER_MEMORY = 'container_memory_working_set_bytes'
_DOCKER_LINK = '/d/homelab-docker-containers/?var-{label}=${{__value.raw}}&${{__url_time_range}}'
_HOST_NETWORK_NOTE = (
    'Containers in host network mode (minecraft, node-exporter, mailcow netfilter) see every host'
    " interface and are left out; their traffic is in the host's node exporter."
)


def _docker_rate(metric: str, window: str = '5m', by: str = 'name', selector: str = _DOCKER) -> str:
    return f'sum by ({by}) (rate({metric}{{{selector}}}[{window}]))'


def _docker_sum(metric: str, by: str = 'name') -> str:
    return f'sum by ({by}) ({metric}{{{_DOCKER}}})'


def _ranked(expr: str, k: int, by: str = 'name') -> str:
    """Keep the k series of `expr` with the highest mean over the whole dashboard range.

    A plain topk ranks at every step, so a chart over hours collects far more than k lines.
    """
    return (
        f'({expr}) and on ({by}) topk({k}, avg_over_time(({expr})[$__range:$__interval] @ end()))'
    )


_BY_CONTAINER = 'stack, name'
_SHARE_OF_HOST = f' / scalar({_AX51_CORES})'
_CONTAINER_MEMORY_OF_LIMIT = (
    f'{_docker_sum(_DOCKER_MEMORY, _BY_CONTAINER)}'
    f' / ({_docker_sum("container_spec_memory_limit_bytes", _BY_CONTAINER)} > 0)'
)

DOCKER_VARIABLES = [
    _query_variable(
        'stack',
        'label_values(container_last_seen{job="ax51", name!=""}, stack)',
        all_value='.*',
    ),
    _query_variable(
        'name',
        'label_values(container_last_seen{job="ax51", name!="", stack=~"$stack"}, name)',
    ),
]
DOCKER_PANELS: list[Panel | Table] = [
    Panel(
        'Host CPU used',
        '1 - avg(rate(node_cpu_seconds_total{job="ax51", mode="idle"}[5m]))',
        'percentunit',
        kind='stat',
        width=4,
        height=4,
    ),
    Panel(
        'Host memory used',
        '1 - sum(node_memory_MemAvailable_bytes{job="ax51"}) / sum(node_memory_MemTotal_bytes{job="ax51"})',
        'percentunit',
        kind='stat',
        width=4,
        height=4,
    ),
    Panel(
        'Host load per core (1 min)',
        f'sum(node_load1{{job="ax51"}}) / {_AX51_CORES}',
        kind='stat',
        width=4,
        height=4,
    ),
    Panel(
        'Running containers',
        'count(time() - container_last_seen{job="ax51", name!=""} < 120)',
        kind='stat',
        width=4,
        height=4,
    ),
    Panel(
        'Containers restarted (last hour)',
        f'count(changes(container_start_time_seconds{{{_DOCKER}}}[1h]) > 0) or vector(0)',
        kind='stat',
        width=4,
        height=4,
    ),
    Panel(
        'OOM kills (last hour)',
        f'sum(increase(container_oom_events_total{{{_DOCKER}}}[1h])) or vector(0)',
        kind='stat',
        width=4,
        height=4,
    ),
    Table(
        'Container load over the selected time range',
        labels=(
            LabelColumn('name', 'Container', _DOCKER_LINK.format(label='name')),
            LabelColumn('stack', 'Stack', _DOCKER_LINK.format(label='stack')),
        ),
        columns=(
            Column(
                'CPU mean (of host)',
                _docker_rate(_DOCKER_CPU, '$__range', _BY_CONTAINER) + _SHARE_OF_HOST,
                'percentunit',
                bar=True,
            ),
            Column(
                'CPU peak (of host)',
                f'max_over_time(({_docker_rate(_DOCKER_CPU, by=_BY_CONTAINER)})[$__range:$__interval])'
                + _SHARE_OF_HOST,
                'percentunit',
            ),
            Column(
                'Memory mean',
                f'avg_over_time(({_docker_sum(_DOCKER_MEMORY, _BY_CONTAINER)})[$__range:$__interval])',
                'bytes',
                bar=True,
            ),
            Column(
                'Memory of limit',
                f'avg_over_time(({_CONTAINER_MEMORY_OF_LIMIT})[$__range:$__interval])',
                'percentunit',
            ),
            Column(
                'Network in',
                _docker_rate(
                    'container_network_receive_bytes_total',
                    '$__range',
                    _BY_CONTAINER,
                    _DOCKER_NETWORK,
                ),
                'Bps',
            ),
            Column(
                'Network out',
                _docker_rate(
                    'container_network_transmit_bytes_total',
                    '$__range',
                    _BY_CONTAINER,
                    _DOCKER_NETWORK,
                ),
                'Bps',
            ),
            Column(
                'Waiting for CPU',
                _docker_rate(
                    'container_pressure_cpu_waiting_seconds_total', '$__range', _BY_CONTAINER
                ),
                'percentunit',
            ),
        ),
        description=(
            'Means over the selected time range, highest CPU first; click a header to sort by another'
            ' column, a container or stack to filter the dashboard. CPU is a share of the host cores.'
            ' Memory of limit is empty for containers without a limit. ' + _HOST_NETWORK_NOTE
        ),
    ),
    Panel(
        'CPU used by container (cores, top 10 by mean)',
        _ranked(_docker_rate(_DOCKER_CPU), 10),
        legend='{{name}}',
        width=24,
        height=10,
        ranked=True,
    ),
    Panel(
        'Memory working set by container (top 10 by mean)',
        _ranked(_docker_sum(_DOCKER_MEMORY), 10),
        'bytes',
        legend='{{name}}',
        width=24,
        height=10,
        ranked=True,
    ),
    Panel(
        'CPU used by stack (cores, top 10 by mean)',
        _ranked(_docker_rate(_DOCKER_CPU, by='stack'), 10, by='stack'),
        legend='{{stack}}',
        stack=True,
        height=12,
        ranked=True,
    ),
    Panel(
        'Memory working set by stack (top 10 by mean)',
        _ranked(_docker_sum(_DOCKER_MEMORY, by='stack'), 10, by='stack'),
        'bytes',
        legend='{{stack}}',
        stack=True,
        height=12,
        ranked=True,
    ),
    Panel(
        'Waiting for CPU (share of time, top 5)',
        _ranked(_docker_rate('container_pressure_cpu_waiting_seconds_total'), 5),
        'percentunit',
        legend='{{name}}',
        height=10,
        ranked=True,
        description=(
            'Pressure stall information: the share of time in which a runnable task of the container'
            ' waited for a CPU, because the host is busy or the container hit its CPU limit.'
        ),
    ),
    Panel(
        'CPU throttled (share of periods, top 5)',
        _ranked(
            f'{_docker_rate("container_cpu_cfs_throttled_periods_total")}'
            f' / {_docker_rate("container_cpu_cfs_periods_total")}',
            5,
        ),
        'percentunit',
        legend='{{name}}',
        height=10,
        ranked=True,
    ),
    Panel(
        'Memory used vs limit (containers with a limit, top 5)',
        _ranked(
            f'{_docker_sum(_DOCKER_MEMORY)}'
            f' / ({_docker_sum("container_spec_memory_limit_bytes")} > 0)',
            5,
        ),
        'percentunit',
        legend='{{name}}',
        height=10,
        ranked=True,
    ),
    Panel(
        'Memory pressure, time stalled (share of time, top 5)',
        _ranked(_docker_rate('container_pressure_memory_stalled_seconds_total'), 5),
        'percentunit',
        legend='{{name}}',
        height=10,
        ranked=True,
    ),
    Panel(
        'Network received (top 5)',
        _ranked(_docker_rate('container_network_receive_bytes_total', selector=_DOCKER_NETWORK), 5),
        'Bps',
        legend='{{name}}',
        height=10,
        ranked=True,
        description=_HOST_NETWORK_NOTE,
    ),
    Panel(
        'Network sent (top 5)',
        _ranked(
            _docker_rate('container_network_transmit_bytes_total', selector=_DOCKER_NETWORK), 5
        ),
        'Bps',
        legend='{{name}}',
        height=10,
        ranked=True,
        description=_HOST_NETWORK_NOTE,
    ),
    Panel(
        'Threads (top 5)',
        _ranked(_docker_sum('container_threads'), 5),
        legend='{{name}}',
        height=10,
        ranked=True,
    ),
    Panel(
        'Shortest uptime (bottom 15)',
        f'bottomk(15, time() - container_start_time_seconds{{{_DOCKER}}})',
        's',
        legend='{{name}}',
        height=10,
    ),
]

LOGS_VARIABLES = [
    _query_variable('namespace', 'label_values(namespace)', 'loki'),
    _query_variable('pod', 'label_values({namespace=~"$namespace"}, pod)', 'loki'),
    _textbox_variable('search', 'Search (regex, case-insensitive)'),
]
_LOG_SELECTOR = '{namespace=~"$namespace", pod=~"$pod"} |~ "(?i)$search"'
LOGS_PANELS = [
    Panel(
        'Log lines by namespace',
        f'sum by (namespace) (count_over_time({_LOG_SELECTOR} [$__interval]))',
        legend='{{namespace}}',
        datasource='loki',
        stack=True,
    ),
    Panel(
        'Errors and warnings by namespace',
        'sum by (namespace) (count_over_time({namespace=~"$namespace", pod=~"$pod"}'
        ' |~ "(?i)(error|fatal|panic|warn)" [$__interval]))',
        legend='{{namespace}}',
        datasource='loki',
        stack=True,
    ),
    Panel('Logs', _LOG_SELECTOR, kind='logs', datasource='loki'),
]


def _adapt_community(raw: str) -> str:
    """Point a downloaded dashboard at the provisioned datasources and return minified JSON."""
    raw = _CPU_RECORDING_RULE.sub(
        lambda match: (
            'sum by (namespace, pod, container) (irate(container_cpu_usage_seconds_total{'
            + match.group(1)
            + r', image!=\"\"}[5m]))'
        ),
        raw,
    )
    dashboard = json.loads(raw)
    expression_inputs = {'DS_EXPRESSION'}
    datasource_names = {
        variable['name']
        for variable in dashboard.get('templating', {}).get('list', [])
        if variable.get('type') == 'datasource'
    } | {item['name'] for item in dashboard.get('__inputs', [])}
    placeholder = re.compile(r'^\$\{?(\w+)\}?$')

    def resolve(value: t.Any) -> t.Any:
        uid = value.get('uid') if isinstance(value, dict) else value
        if uid in _LEGACY_PROMETHEUS_DATASOURCES:
            return _datasource('prometheus')
        match = placeholder.match(uid) if isinstance(uid, str) else None
        if not match or match.group(1) not in datasource_names:
            return value
        if match.group(1) in expression_inputs:
            return EXPRESSION_DATASOURCE
        kind = value.get('type', 'prometheus') if isinstance(value, dict) else 'prometheus'
        return _datasource(kind)

    def walk(node: t.Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == 'datasource':
                    node[key] = resolve(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(dashboard)
    dashboard.pop('__inputs', None)
    dashboard['id'] = None
    dashboard['editable'] = False
    templating = dashboard.get('templating', {})
    templating['list'] = [
        variable for variable in templating.get('list', []) if variable.get('type') != 'datasource'
    ]
    return json.dumps(dashboard, separators=(',', ':'))


def _wazuh_panel(
    panel_id: int,
    title: str,
    query: str,
    datasource_kind: str,
    kind: str = 'table',
    description: str = '',
    x: int = 0,
    y: int = 0,
    width: int = 12,
    height: int = 9,
    terms_field: str = '',
    terms_missing: str = '',
) -> dict[str, t.Any]:
    """Build a Wazuh panel using read-only Lucene queries."""
    datasource = _datasource(datasource_kind)
    target: dict[str, t.Any] = {
        'refId': 'A',
        'queryType': 'lucene',
        'query': query,
        'format': 'table',
        'datasource': datasource,
    }
    target.update(
        {
            'luceneQueryType': 'Metric' if terms_field else 'RawData',
            'metrics': (
                [{'id': '1', 'type': 'count'}] if terms_field else [{'id': '1', 'type': 'raw_data'}]
            ),
            'bucketAggs': (
                [
                    {
                        'id': '2',
                        'type': 'terms',
                        'field': terms_field,
                        'settings': {
                            'size': '20',
                            'order': 'desc',
                            'orderBy': '_count',
                            **({'missing': terms_missing} if terms_missing else {}),
                        },
                    }
                ]
                if terms_field
                else []
            ),
            'size': 200,
        }
    )
    return {
        'id': panel_id,
        'type': kind,
        'title': title,
        'description': description,
        'datasource': datasource,
        'gridPos': {'x': x, 'y': y, 'w': width, 'h': height},
        'targets': [target],
    }


def _wazuh_dashboard() -> str:
    """Build the Wazuh current-state and inventory dashboard."""
    panels = [
        {
            'id': 1,
            'type': 'text',
            'title': 'State versus event history',
            'options': {
                'mode': 'markdown',
                'content': '**Current state is authoritative.** Vulnerability transition events are '
                'best-effort history and do not represent a complete lifecycle ledger.',
            },
            'gridPos': {'x': 0, 'y': 0, 'w': 24, 'h': 4},
        },
        _wazuh_panel(
            2,
            'Current vulnerability findings — endpoint k0s0 (agent 001)',
            'agent.id:001',
            'opensearch-vulnerabilities',
            description='Current findings, not transition events. Unclassified severity is retained.',
            x=0,
            y=4,
            width=24,
            height=12,
        ),
        _wazuh_panel(
            3,
            'Current findings by severity (including unclassified)',
            'agent.id:001',
            'opensearch-vulnerabilities',
            kind='barchart',
            x=0,
            y=16,
            terms_field='vulnerability.severity',
            terms_missing='Untriaged',
        ),
        _wazuh_panel(
            4,
            'Agent status — manager monitoring index',
            'id:001',
            'opensearch-agent-status',
            description='Wazuh manager monitoring history is the source for Active/Disconnected status.',
            x=12,
            y=16,
        ),
        _wazuh_panel(
            5,
            'Top installed packages',
            '*',
            'opensearch-inventory',
            description='Current package inventory; names are grouped by document count.',
            x=0,
            y=25,
            width=24,
            height=10,
            terms_field='package.name',
        ),
        _wazuh_panel(
            6,
            'Package count by endpoint',
            '*',
            'opensearch-inventory',
            x=0,
            y=35,
            terms_field='agent.id',
        ),
        _wazuh_panel(
            7,
            'Process count by endpoint',
            '*',
            'opensearch-processes',
            x=12,
            y=35,
            terms_field='agent.id',
        ),
        _wazuh_panel(
            8,
            'Port inventory count by endpoint',
            '*',
            'opensearch-ports',
            x=0,
            y=44,
            terms_field='agent.id',
        ),
        _wazuh_panel(
            9,
            'Operating system',
            'agent.id:001',
            'opensearch-system',
            description='Operating system name from the current Wazuh inventory state.',
            x=12,
            y=44,
            terms_field='host.os.name',
        ),
        _wazuh_panel(
            10,
            'Recent Wazuh alerts (best-effort events)',
            'agent.id:001',
            'opensearch-alerts',
            description='Security events are not a complete vulnerability lifecycle ledger; current state is authoritative.',
            x=0,
            y=53,
            width=24,
            height=10,
        ),
        {
            'id': 11,
            'type': 'logs',
            'title': 'Vulnerability transitions (best-effort)',
            'datasource': _datasource('loki'),
            'targets': [
                {'expr': '{namespace="wazuh", job="wazuh-alerts"} | json | rule_id=~"2350[2-6]"'}
            ],
            'gridPos': {'x': 0, 'y': 63, 'w': 24, 'h': 10},
            'description': 'Selected Active/Solved transition alerts. CVE, agent and package remain log fields, not labels.',
        },
        {
            'id': 12,
            'type': 'logs',
            'title': 'CTI feed completion and errors',
            'datasource': _datasource('loki'),
            'targets': [
                {
                    'expr': '{namespace="wazuh", job="wazuh-ossec-log"} |~ "(Feed update process completed|Error updating feed)"'
                }
            ],
            'gridPos': {'x': 0, 'y': 73, 'w': 24, 'h': 8},
            'description': 'Completion indicates that new content was applied, not a periodic heartbeat; absence is not proof of staleness.',
        },
        {
            'id': 13,
            'type': 'logs',
            'title': 'CTI catalog freshness signal (remote offset)',
            'datasource': _datasource('loki'),
            'targets': [
                {
                    'expr': '{namespace="wazuh", job="wazuh-cti-freshness"} | json | event="cti_freshness"'
                }
            ],
            'gridPos': {'x': 0, 'y': 81, 'w': 24, 'h': 8},
            'description': 'Read-only CTI catalog consumer offset sampled every 10 minutes. This measures remote catalog metadata, not proof of local manager application.',
        },
    ]
    # Inventory state has no date field; its configured time field is numeric
    # wazuh.schema.version. Keep these current-state metrics independent of the
    # dashboard time picker while allowing the plugin's required range filter.
    for panel in panels:
        if 5 <= panel['id'] <= 9:
            panel['timeFrom'] = '100y'
    return json.dumps(
        {
            'uid': 'homelab-wazuh',
            'title': 'Wazuh',
            'tags': ['homelab', 'security', 'wazuh'],
            'timezone': 'browser',
            'schemaVersion': 39,
            'refresh': '5m',
            'time': {'from': 'now-24h', 'to': 'now'},
            'panels': panels,
        },
        indent=2,
    )


def provisioning_files() -> dict[str, str]:
    """File name to dashboard JSON, ready for a ConfigMap."""
    files = {
        'overview.json': _dashboard('homelab-overview', 'Cluster overview', OVERVIEW_PANELS),
        'backups.json': _dashboard('homelab-backups', 'Backups and storage', BACKUP_PANELS),
        'workloads.json': _dashboard(
            'homelab-workloads', 'Kubernetes workloads', WORKLOAD_PANELS, WORKLOAD_VARIABLES
        ),
        'self-health.json': _dashboard(
            'homelab-self-health', 'Observability self-health', SELF_HEALTH_PANELS
        ),
        'logs.json': _dashboard('homelab-logs', 'Logs explorer', LOGS_PANELS, LOGS_VARIABLES),
        'internet-speed.json': _dashboard(
            'homelab-internet-speed', 'Internet Speed', SPEEDTEST_PANELS
        ),
        'tandoor.json': _dashboard('homelab-tandoor', 'Tandoor', TANDOOR_PANELS),
        'netbox.json': _dashboard('homelab-netbox', 'NetBox', NETBOX_PANELS),
        'trivy-operator.json': _dashboard('homelab-trivy-operator', 'Trivy Operator', TRIVY_PANELS),
        'opnsense.json': _dashboard('homelab-opnsense', 'OPNsense', OPNSENSE_PANELS),
        'opnsense-logs.json': _dashboard(
            'homelab-opnsense-logs',
            'OPNsense logs',
            OPNSENSE_LOG_PANELS,
            OPNSENSE_LOG_VARIABLES,
        ),
        'docker-containers.json': _dashboard(
            'homelab-docker-containers', 'Docker containers', DOCKER_PANELS, DOCKER_VARIABLES
        ),
        'wazuh.json': _wazuh_dashboard(),
    }
    for name in (*COMMUNITY_DASHBOARDS, *LEGACY_DASHBOARDS):
        files[name] = _adapt_community((COMMUNITY_DIR / name).read_text())
    return files
