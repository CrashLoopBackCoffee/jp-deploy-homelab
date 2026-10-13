import pulumi as p
import pulumi_kubernetes as k8s

from observability.config import ComponentConfig

LOKI_RELEASE = 'loki'
# Release name equals the chart name, so the chart names its gateway Service `loki-gateway`.
LOKI_GATEWAY_URL = 'http://loki-gateway.observability.svc.cluster.local'


def create_loki(component_config: ComponentConfig, k8s_opts: p.ResourceOptions):
    """Single-binary Loki with filesystem storage on a Longhorn volume."""
    loki_config = component_config.loki
    return k8s.helm.v3.Release(
        'loki',
        name=LOKI_RELEASE,
        chart='loki',
        version=loki_config.version,
        repository_opts={'repo': 'https://grafana-community.github.io/helm-charts'},
        values={
            'deploymentMode': 'SingleBinary',
            'loki': {
                'auth_enabled': False,
                'commonConfig': {'replication_factor': 1},
                'compactor': {
                    'delete_request_store': 'filesystem',
                    'retention_enabled': True,
                },
                'limits_config': {'retention_period': f'{loki_config.retention_days}d'},
                # Pinned: the chart's test schema may change between versions and orphan data.
                'schemaConfig': {
                    'configs': [
                        {
                            'from': '2024-04-01',
                            'store': 'tsdb',
                            'object_store': 'filesystem',
                            'schema': 'v13',
                            'index': {'prefix': 'index_', 'period': '24h'},
                        },
                    ],
                },
                'storage': {'type': 'filesystem'},
            },
            'singleBinary': {
                'replicas': 1,
                'persistence': {
                    'enabled': True,
                    'size': f'{loki_config.storage_size_gb}Gi',
                    'whenDeleted': 'Retain',
                    'whenScaled': 'Retain',
                },
            },
            'gateway': {
                'deploymentStrategy': {'type': 'Recreate'},
                'metrics': {'enabled': False},
            },
            'chunksCache': {'allocatedMemory': 512},
            'resultsCache': {'allocatedMemory': 128},
            'backend': {'replicas': 0},
            'read': {'replicas': 0},
            'write': {'replicas': 0},
            'sidecar': {'rules': {'enabled': False}},
            'lokiCanary': {'enabled': False},
            'test': {'enabled': False},
            'minio': {'enabled': False},
        },
        opts=k8s_opts,
    )
