import pulumi as p
import pulumi_kubernetes as k8s

from kubernetes.config import ComponentConfig


def create_longhorn(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    """Install Longhorn on the dedicated data disk prepared with Ansible (services/k0s/ansible).

    The chart does not install a CSI snapshot controller; the OpenEBS add-on already provides one.
    """
    namespace = k8s.core.v1.Namespace(
        'longhorn-system',
        metadata={'name': 'longhorn-system'},
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    namespaced_k8s_provider = k8s.Provider(
        'longhorn-provider',
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        namespace=namespace.metadata['name'],
    )
    k8s_opts = p.ResourceOptions(provider=namespaced_k8s_provider)
    backup_credentials = k8s.core.v1.Secret(
        'longhorn-backup-credentials',
        metadata={'name': 'longhorn-backup-credentials', 'namespace': namespace.metadata.name},
        string_data={
            'AWS_ACCESS_KEY_ID': component_config.longhorn.backup.access_key_id.value,
            'AWS_SECRET_ACCESS_KEY': component_config.longhorn.backup.secret_access_key.value,
            'AWS_ENDPOINTS': component_config.longhorn.backup.endpoint,
            'VIRTUAL_HOSTED_STYLE': 'false',
        },
        opts=k8s_opts,
    )

    # Release instead of Chart because the chart relies on pre-upgrade, post-upgrade and
    # pre-delete hook jobs, which Chart does not execute.
    release = k8s.helm.v3.Release(
        'longhorn',
        chart='longhorn',
        version=component_config.longhorn.version,
        namespace=namespace.metadata.name,
        repository_opts={'repo': 'https://charts.longhorn.io'},
        values={
            'csi': {'kubeletRootDir': '/var/lib/k0s/kubelet'},
            'defaultSettings': {
                'defaultDataPath': component_config.longhorn.data_path,
                'defaultReplicaCount': component_config.longhorn.replica_count,
                'allowRecurringJobWhileVolumeDetached': True,
            },
            'defaultBackupStore': {
                'backupTarget': (
                    f's3://{component_config.longhorn.backup.bucket}'
                    f'@{component_config.longhorn.backup.region}/'
                ),
                'backupTargetCredentialSecret': backup_credentials.metadata.name,
            },
            'persistence': {'defaultClassReplicaCount': component_config.longhorn.replica_count},
            'metrics': {'serviceMonitor': {'enabled': False}},
        },
        opts=p.ResourceOptions(provider=namespaced_k8s_provider, depends_on=[backup_credentials]),
    )

    k8s.apiextensions.CustomResource(
        'longhorn-daily-backup',
        api_version='longhorn.io/v1beta2',
        kind='RecurringJob',
        metadata={'name': 'longhorn-daily-backup', 'namespace': namespace.metadata.name},
        spec={
            'cron': '0 2 * * *',
            'task': 'backup',
            'groups': ['default'],
            'retentionPolicy': 'count-based',
            'retain': 14,
            'concurrency': 1,
        },
        opts=p.ResourceOptions(provider=namespaced_k8s_provider, depends_on=[release]),
    )

    return release
