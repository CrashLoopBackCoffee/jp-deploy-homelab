import pulumi as p
import pulumi_kubernetes as k8s

from observability.alloy import create_alloy, create_node_proxy_access
from observability.config import ComponentConfig
from observability.exporters import create_kube_state_metrics, create_node_exporter
from observability.grafana import create_grafana
from observability.loki import create_loki
from observability.mimir import create_mimir


def main():
    component_config = ComponentConfig.model_validate(p.Config().require_object('config'))

    k8s_provider = k8s.Provider('k8s', kubeconfig=component_config.kubeconfig.value)
    namespace = k8s.core.v1.Namespace(
        'observability',
        metadata={'name': 'observability'},
        opts=p.ResourceOptions(provider=k8s_provider),
    )
    namespaced_provider = k8s.Provider(
        'observability-provider',
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        namespace=namespace.metadata.name,
    )
    k8s_opts = p.ResourceOptions(provider=namespaced_provider)

    loki = create_loki(component_config, k8s_opts)
    mimir = create_mimir(component_config, k8s_opts)
    create_kube_state_metrics(component_config, k8s_opts)
    create_node_exporter(component_config, k8s_opts)
    alloy = create_alloy(component_config, k8s_opts, depends_on=[loki, mimir])
    create_node_proxy_access(k8s_opts, alloy)
    create_grafana(component_config, k8s_opts, depends_on=[loki, mimir])
