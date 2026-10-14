import pulumi as p
import pulumi_kubernetes as k8s

from observability.config import ComponentConfig

PROMETHEUS_COMMUNITY_REPO = 'https://prometheus-community.github.io/helm-charts'

# The Barman Cloud plugin does not feed CloudNativePG's own backup metrics (they stay 0), so
# backup freshness is derived from the Backup custom resources instead.
CNPG_BACKUP_STATE_METRICS = {
    'kind': 'CustomResourceStateMetrics',
    'spec': {
        'resources': [
            {
                'groupVersionKind': {
                    'group': 'postgresql.cnpg.io',
                    'version': 'v1',
                    'kind': 'Backup',
                },
                'metricNamePrefix': 'cnpg_backup',
                'labelsFromPath': {
                    'name': ['metadata', 'name'],
                    'namespace': ['metadata', 'namespace'],
                    'cluster': ['spec', 'cluster', 'name'],
                    'phase': ['status', 'phase'],
                },
                'metrics': [
                    {
                        'name': 'stopped_at_seconds',
                        'help': 'Unix time at which the backup stopped.',
                        'each': {
                            'type': 'Gauge',
                            'gauge': {'path': ['status', 'stoppedAt'], 'nilIsZero': True},
                        },
                    },
                ],
            },
        ],
    },
}


def create_kube_state_metrics(component_config: ComponentConfig, k8s_opts: p.ResourceOptions):
    return k8s.helm.v3.Release(
        'kube-state-metrics',
        name='kube-state-metrics',
        chart='kube-state-metrics',
        version=component_config.kube_state_metrics.version,
        repository_opts={'repo': PROMETHEUS_COMMUNITY_REPO},
        values={
            'prometheusScrape': False,
            'customResourceState': {'enabled': True, 'config': CNPG_BACKUP_STATE_METRICS},
            'rbac': {
                'extraRules': [
                    {
                        'apiGroups': ['postgresql.cnpg.io'],
                        'resources': ['backups'],
                        'verbs': ['list', 'watch'],
                    },
                ],
            },
        },
        opts=k8s_opts,
    )


def create_node_exporter(component_config: ComponentConfig, k8s_opts: p.ResourceOptions):
    return k8s.helm.v3.Release(
        'node-exporter',
        name='node-exporter',
        chart='prometheus-node-exporter',
        version=component_config.node_exporter.version,
        repository_opts={'repo': PROMETHEUS_COMMUNITY_REPO},
        values={'prometheus': {'monitor': {'enabled': False}}},
        opts=k8s_opts,
    )
