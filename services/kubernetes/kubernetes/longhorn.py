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

    # Release instead of Chart because the chart relies on pre-upgrade, post-upgrade and
    # pre-delete hook jobs, which Chart does not execute.
    return k8s.helm.v3.Release(
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
            },
            'persistence': {'defaultClassReplicaCount': component_config.longhorn.replica_count},
            'metrics': {'serviceMonitor': {'enabled': False}},
        },
        opts=k8s_opts,
    )
