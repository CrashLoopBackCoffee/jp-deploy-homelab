import pulumi as p
import pulumi_kubernetes as k8s

from observability.config import ComponentConfig

MIMIR_RELEASE = 'mimir'
MIMIR_S3_SECRET = 'mimir-s3-credentials'
# Release name equals the chart name, so the chart names its gateway Service `mimir-gateway`.
MIMIR_GATEWAY_URL = 'http://mimir-gateway.observability.svc.cluster.local'


def _persistent_volume(size_gb: int) -> dict:
    return {
        'enabled': True,
        'size': f'{size_gb}Gi',
        'enableRetentionPolicy': True,
        'whenDeleted': 'Retain',
        'whenScaled': 'Retain',
    }


def create_mimir(
    component_config: ComponentConfig,
    k8s_opts: p.ResourceOptions,
) -> k8s.helm.v3.Release:
    """Metrics storage on one node, with blocks in a QuObjects bucket instead of bundled MinIO."""
    mimir_config = component_config.mimir
    s3_secret = k8s.core.v1.Secret(
        MIMIR_S3_SECRET,
        metadata={'name': MIMIR_S3_SECRET},
        string_data={
            'MIMIR_S3_ACCESS_KEY_ID': mimir_config.access_key_id.value,
            'MIMIR_S3_SECRET_ACCESS_KEY': mimir_config.secret_access_key.value,
        },
        opts=k8s_opts,
    )

    return k8s.helm.v3.Release(
        'mimir',
        name=MIMIR_RELEASE,
        chart='mimir-distributed',
        version=mimir_config.version,
        repository_opts={'repo': 'https://grafana.github.io/helm-charts'},
        values={
            'global': {
                'extraEnvFrom': [{'secretRef': {'name': s3_secret.metadata.name}}],
            },
            'mimir': {
                'structuredConfig': {
                    'multitenancy_enabled': False,
                    'common': {
                        'storage': {
                            'backend': 's3',
                            's3': {
                                'endpoint': mimir_config.endpoint,
                                'bucket_name': mimir_config.bucket,
                                'access_key_id': '${MIMIR_S3_ACCESS_KEY_ID}',
                                'secret_access_key': '${MIMIR_S3_SECRET_ACCESS_KEY}',
                                'insecure': False,
                            },
                        },
                    },
                    'blocks_storage': {'storage_prefix': 'blocks'},
                    'ingest_storage': {'enabled': False},
                    'ingester': {
                        'push_grpc_method_enabled': True,
                        'ring': {'replication_factor': 1},
                    },
                    'store_gateway': {'sharding_ring': {'replication_factor': 1}},
                    'limits': {
                        'compactor_blocks_retention_period': f'{mimir_config.retention_days}d',
                    },
                    'compactor': {'data_dir': '/data'},
                },
            },
            'minio': {'enabled': False},
            'kafka': {'enabled': False},
            'rollout_operator': {'enabled': False},
            # Grafana-managed alerting replaces the ruler and Alertmanager.
            'ruler': {'enabled': False},
            'alertmanager': {'enabled': False},
            'overrides_exporter': {'enabled': False},
            'distributor': {'replicas': 1},
            'querier': {'replicas': 1},
            'query_scheduler': {'replicas': 1},
            'ingester': {
                'replicas': 1,
                'zoneAwareReplication': {'enabled': False},
                'persistentVolume': _persistent_volume(mimir_config.ingester_storage_size_gb),
            },
            'store_gateway': {
                'replicas': 1,
                'zoneAwareReplication': {'enabled': False},
                'persistentVolume': _persistent_volume(mimir_config.store_gateway_storage_size_gb),
            },
            'compactor': {
                'persistentVolume': _persistent_volume(mimir_config.compactor_storage_size_gb),
            },
        },
        opts=k8s_opts,
    )
