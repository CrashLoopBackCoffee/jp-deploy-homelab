import pulumi as p
import pulumi_kubernetes as k8s

from wazuh.config import ComponentConfig
from wazuh.pki import create_pki

config = ComponentConfig.model_validate(p.Config().require_object('config'))
provider = k8s.Provider('k8s', kubeconfig=config.kubeconfig.value)
namespace = k8s.core.v1.Namespace(
    'wazuh-namespace',
    metadata={'name': config.namespace},
    opts=p.ResourceOptions(provider=provider),
)
create_pki(config, provider, namespace.metadata.name)
