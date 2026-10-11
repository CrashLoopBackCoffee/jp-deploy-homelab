import pulumi as p
import pulumi_kubernetes as k8s

from kubernetes.config import ComponentConfig


def create_openebs_lvm(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    """Install OpenEBS LVM LocalPV and a StorageClass for node-local PostgreSQL volumes.

    The volume group itself is prepared on each node with Ansible (services/k0s/ansible).
    """
    namespace = k8s.core.v1.Namespace(
        'openebs',
        metadata={'name': 'openebs'},
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    namespaced_k8s_provider = k8s.Provider(
        'openebs-provider',
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        namespace=namespace.metadata['name'],
    )
    k8s_opts = p.ResourceOptions(provider=namespaced_k8s_provider)

    chart = k8s.helm.v4.Chart(
        'openebs-lvm-localpv',
        chart='lvm-localpv',
        version=component_config.openebs_lvm.version,
        namespace=namespace.metadata.name,
        repository_opts={'repo': 'https://openebs.github.io/lvm-localpv'},
        values={
            'lvmNode': {'kubeletDir': '/var/lib/k0s/kubelet/'},
            'analytics': {'enabled': False},
        },
        opts=k8s_opts,
    )

    # WaitForFirstConsumer plus the chart's storage capacity tracking lets the scheduler
    # place a pod only on a node whose volume group has enough free space.
    return k8s.storage.v1.StorageClass(
        'openebs-lvm-postgres',
        metadata={'name': 'openebs-lvm-postgres'},
        provisioner='local.csi.openebs.io',
        parameters={
            'volgroup': component_config.openebs_lvm.volume_group,
            'fsType': 'ext4',
        },
        volume_binding_mode='WaitForFirstConsumer',
        allow_volume_expansion=True,
        opts=p.ResourceOptions(provider=k8s_provider, depends_on=[chart]),
    )
