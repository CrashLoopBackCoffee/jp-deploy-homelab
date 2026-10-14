import pulumi as p
import pulumi_kubernetes as k8s

from kubernetes.config import ComponentConfig


def create_cloudnative_pg(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    """Install the operator and its Barman Cloud plugin."""
    namespace = k8s.core.v1.Namespace(
        'cnpg-system',
        metadata={'name': 'cnpg-system'},
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    namespaced_k8s_provider = k8s.Provider(
        'cnpg-provider',
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        namespace=namespace.metadata['name'],
    )
    k8s_opts = p.ResourceOptions(provider=namespaced_k8s_provider)

    # Install CloudNativePG operator using Helm chart
    operator = k8s.helm.v4.Chart(
        'cloudnative-pg',
        chart='cloudnative-pg',
        version=component_config.cloudnative_pg.version,
        namespace=namespace.metadata.name,
        repository_opts={'repo': 'https://cloudnative-pg.github.io/charts'},
        values={
            'config': {
                'create': True,
                'secret': False,
            },
        },
        opts=k8s_opts,
    )

    return k8s.helm.v4.Chart(
        'plugin-barman-cloud',
        chart='plugin-barman-cloud',
        version=component_config.cloudnative_pg.plugin_version,
        namespace=namespace.metadata.name,
        repository_opts={'repo': 'https://cloudnative-pg.github.io/charts'},
        opts=p.ResourceOptions(provider=namespaced_k8s_provider, depends_on=[operator]),
    )


def create_postgres_cluster(
    component_config: ComponentConfig,
    k8s_provider: k8s.Provider,
    plugin: k8s.helm.v4.Chart,
    storage_class: k8s.storage.v1.StorageClass,
) -> k8s.apiextensions.CustomResource:
    """Create the single-node PostgreSQL pilot with physical backups and WAL archiving."""
    cluster_config = component_config.cloudnative_pg.cluster
    backup_config = component_config.cloudnative_pg.backup
    store_name = f'{cluster_config.name}-store'
    namespace = k8s.core.v1.Namespace(
        cluster_config.name,
        metadata={'name': cluster_config.name},
        opts=p.ResourceOptions(provider=k8s_provider),
    )
    namespaced_provider = k8s.Provider(
        f'{cluster_config.name}-provider',
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        namespace=namespace.metadata.name,
    )
    k8s_opts = p.ResourceOptions(provider=namespaced_provider)
    credentials = k8s.core.v1.Secret(
        'cnpg-backup-credentials',
        metadata={'name': 'cnpg-backup-credentials', 'namespace': namespace.metadata.name},
        string_data={
            'ACCESS_KEY_ID': backup_config.access_key_id.value,
            'ACCESS_SECRET_KEY': backup_config.secret_access_key.value,
        },
        opts=k8s_opts,
    )
    store = k8s.apiextensions.CustomResource(
        store_name,
        api_version='barmancloud.cnpg.io/v1',
        kind='ObjectStore',
        metadata={'name': store_name, 'namespace': namespace.metadata.name},
        spec={
            'configuration': {
                'destinationPath': f's3://{backup_config.bucket}/{cluster_config.name}/',
                'endpointURL': backup_config.endpoint,
                's3Credentials': {
                    'accessKeyId': {'name': credentials.metadata.name, 'key': 'ACCESS_KEY_ID'},
                    'secretAccessKey': {
                        'name': credentials.metadata.name,
                        'key': 'ACCESS_SECRET_KEY',
                    },
                },
                'wal': {'compression': 'gzip'},
            },
            # QuObjects rejects boto3's optional checksum headers with InvalidDigest.
            'instanceSidecarConfiguration': {
                'env': [
                    {'name': 'AWS_REQUEST_CHECKSUM_CALCULATION', 'value': 'when_required'},
                    {'name': 'AWS_RESPONSE_CHECKSUM_VALIDATION', 'value': 'when_required'},
                ],
            },
            'retentionPolicy': backup_config.retention_policy,
        },
        opts=p.ResourceOptions(provider=namespaced_provider, depends_on=[plugin, credentials]),
    )
    cluster = k8s.apiextensions.CustomResource(
        cluster_config.name,
        api_version='postgresql.cnpg.io/v1',
        kind='Cluster',
        metadata={'name': cluster_config.name, 'namespace': namespace.metadata.name},
        spec={
            'instances': 1,
            'imageName': f'ghcr.io/cloudnative-pg/postgresql:{cluster_config.image_version}',
            'storage': {
                'size': cluster_config.storage_size,
                'storageClass': storage_class.metadata.name,
            },
            'plugins': [
                {
                    'name': 'barman-cloud.cloudnative-pg.io',
                    'isWALArchiver': True,
                    'parameters': {'barmanObjectName': store_name},
                }
            ],
        },
        opts=p.ResourceOptions(provider=namespaced_provider, depends_on=[store, storage_class]),
    )
    k8s.apiextensions.CustomResource(
        f'{cluster_config.name}-backup',
        api_version='postgresql.cnpg.io/v1',
        kind='ScheduledBackup',
        metadata={'name': f'{cluster_config.name}-backup', 'namespace': namespace.metadata.name},
        spec={
            'schedule': backup_config.schedule,
            'immediate': True,
            'backupOwnerReference': 'self',
            'cluster': {'name': cluster_config.name},
            'method': 'plugin',
            'pluginConfiguration': {'name': 'barman-cloud.cloudnative-pg.io'},
        },
        opts=p.ResourceOptions(provider=namespaced_provider, depends_on=[cluster]),
    )
    return cluster
