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


def _datasource(kind: str) -> dict[str, str]:
    uid = LOKI_DATASOURCE_UID if kind == 'loki' else MIMIR_DATASOURCE_UID
    return {'type': kind, 'uid': uid}


def _panel(panel: Panel, index: int, position: int) -> dict:
    full_width = panel.kind == 'logs'
    datasource = _datasource(panel.datasource)
    definition: dict[str, t.Any] = {
        'id': index + 1,
        'type': panel.kind,
        'title': panel.title,
        'datasource': datasource,
        'gridPos': {
            'x': 0 if full_width else (position % 2) * PANEL_WIDTH,
            'y': (position // 2) * PANEL_HEIGHT,
            'w': 2 * PANEL_WIDTH if full_width else PANEL_WIDTH,
            'h': LOGS_HEIGHT if full_width else PANEL_HEIGHT,
        },
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
    if panel.kind != 'logs':
        defaults: dict[str, t.Any] = {'unit': panel.unit}
        if panel.stack:
            defaults['custom'] = {'stacking': {'mode': 'normal'}, 'fillOpacity': 30}
        definition['fieldConfig'] = {'defaults': defaults, 'overrides': []}
    return definition


def _layout(panels: list[Panel]) -> list[dict]:
    """Two panels per row; a logs panel takes the full width and starts a new row."""
    rendered = []
    position = 0
    for index, panel in enumerate(panels):
        if panel.kind == 'logs' and position % 2:
            position += 1
        rendered.append(_panel(panel, index, position))
        position += 2 if panel.kind == 'logs' else 1
    return rendered


def _query_variable(name: str, query: str, datasource: str = 'prometheus') -> dict:
    return {
        'name': name,
        'type': 'query',
        'datasource': _datasource(datasource),
        'query': query,
        'refresh': 2,
        'multi': True,
        'includeAll': True,
        'allValue': '.+',
        'current': {'selected': True, 'text': 'All', 'value': '$__all'},
    }


def _textbox_variable(name: str, label: str) -> dict:
    return {'name': name, 'label': label, 'type': 'textbox', 'query': '', 'current': {'value': ''}}


def _dashboard(
    uid: str,
    title: str,
    panels: list[Panel],
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

# Docker containers on hosts outside the cluster, from cAdvisor (job `ax51`; the Docker hosts of
# dockerhost join when its LAN targets move). Only cAdvisor series carry the `name` label, so the
# selector also keeps the node exporter and Docker engine targets of the same job out. The
# `container_label_*` labels are dropped in Alloy and are not available here.
_DOCKER = 'job="ax51", name=~"$name", name!=""'
DOCKER_VARIABLES = [
    _query_variable('name', 'label_values(container_last_seen{job="ax51", name!=""}, name)'),
]
DOCKER_PANELS = [
    Panel(
        'Running containers',
        'count(time() - container_last_seen{job="ax51", name!=""} < 120)',
        kind='stat',
    ),
    Panel(
        'Containers restarted (last hour)',
        f'count(changes(container_start_time_seconds{{{_DOCKER}}}[1h]) > 0) or vector(0)',
        kind='stat',
    ),
    Panel(
        'OOM kills (last hour)',
        f'sum(increase(container_oom_events_total{{{_DOCKER}}}[1h])) or vector(0)',
        kind='stat',
    ),
    Panel(
        'Shortest uptime (bottom 15)',
        f'bottomk(15, time() - container_start_time_seconds{{{_DOCKER}}})',
        's',
        legend='{{name}}',
    ),
    Panel(
        'CPU used (cores, top 15)',
        f'topk(15, sum by (name) (rate(container_cpu_usage_seconds_total{{{_DOCKER}}}[5m])))',
        legend='{{name}}',
    ),
    Panel(
        'CPU throttled (share of periods, top 10)',
        f'topk(10, sum by (name) (rate(container_cpu_cfs_throttled_periods_total{{{_DOCKER}}}[5m]))'
        f' / sum by (name) (rate(container_cpu_cfs_periods_total{{{_DOCKER}}}[5m])))',
        'percentunit',
        legend='{{name}}',
    ),
    Panel(
        'Memory working set (top 15)',
        f'topk(15, sum by (name) (container_memory_working_set_bytes{{{_DOCKER}}}))',
        'bytes',
        legend='{{name}}',
    ),
    Panel(
        'Memory used vs limit (containers with a limit, top 15)',
        f'topk(15, sum by (name) (container_memory_working_set_bytes{{{_DOCKER}}})'
        f' / (sum by (name) (container_spec_memory_limit_bytes{{{_DOCKER}}}) > 0))',
        'percentunit',
        legend='{{name}}',
    ),
    Panel(
        'Network received (top 15)',
        f'topk(15, sum by (name) (rate(container_network_receive_bytes_total{{{_DOCKER}}}[5m])))',
        'Bps',
        legend='{{name}}',
    ),
    Panel(
        'Network sent (top 15)',
        f'topk(15, sum by (name) (rate(container_network_transmit_bytes_total{{{_DOCKER}}}[5m])))',
        'Bps',
        legend='{{name}}',
    ),
    Panel(
        'Processes and threads (top 10)',
        f'topk(10, sum by (name) (container_threads{{{_DOCKER}}}))',
        legend='{{name}}',
    ),
    Panel(
        'Memory pressure, time stalled (top 10)',
        f'topk(10, sum by (name) (rate(container_pressure_memory_stalled_seconds_total{{{_DOCKER}}}[5m])))',
        's',
        legend='{{name}}',
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
        'docker-containers.json': _dashboard(
            'homelab-docker-containers', 'Docker containers', DOCKER_PANELS, DOCKER_VARIABLES
        ),
    }
    for name in (*COMMUNITY_DASHBOARDS, *LEGACY_DASHBOARDS):
        files[name] = _adapt_community((COMMUNITY_DIR / name).read_text())
    return files
