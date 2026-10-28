import pulumi as p
import pulumi_kubernetes as k8s
import utils.mariadb

from kubernetes.config import ComponentConfig

REPOSITORY = 'https://mariadb-operator.github.io/mariadb-operator'


def create_mariadb_operator(component_config: ComponentConfig, k8s_provider: k8s.Provider):
    """Install the cluster-wide mariadb-operator; databases are created with `utils.mariadb`."""
    namespace = k8s.core.v1.Namespace(
        'mariadb-operator',
        metadata={'name': utils.mariadb.OPERATOR_NAMESPACE},
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    namespaced_k8s_provider = k8s.Provider(
        'mariadb-operator-provider',
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        namespace=namespace.metadata['name'],
    )
    k8s_opts = p.ResourceOptions(provider=namespaced_k8s_provider)

    crds = k8s.helm.v4.Chart(
        'mariadb-operator-crds',
        chart='mariadb-operator-crds',
        version=component_config.mariadb_operator.version,
        namespace=namespace.metadata.name,
        repository_opts={'repo': REPOSITORY},
        opts=k8s_opts,
    )

    return k8s.helm.v4.Chart(
        'mariadb-operator',
        chart='mariadb-operator',
        version=component_config.mariadb_operator.version,
        namespace=namespace.metadata.name,
        repository_opts={'repo': REPOSITORY},
        opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[crds])),
    )
