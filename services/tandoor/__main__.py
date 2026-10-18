import pulumi as p
import pulumi_kubernetes as k8s

from tandoor.config import ComponentConfig
from tandoor.tandoor import Tandoor

config = p.Config()
component_config = ComponentConfig.model_validate(config.get_object('config'))

k8s_provider = k8s.Provider('k8s', kubeconfig=component_config.kubeconfig.value)

namespace = k8s.core.v1.Namespace(
    'tandoor-namespace',
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name='tandoor',
    ),
    opts=p.ResourceOptions(
        provider=k8s_provider,
    ),
)

Tandoor(
    component_config,
    namespace.metadata.name,
    k8s_provider,
)
