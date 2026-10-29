import pulumi as p
import pulumi_kubernetes as k8s
import utils.cloudflare

from wazuh.config import ComponentConfig
from wazuh.dashboard import create_dashboard
from wazuh.exporters import create_exporters
from wazuh.indexer import create_indexer
from wazuh.manager import create_manager
from wazuh.pki import create_pki

config = ComponentConfig.model_validate(p.Config().require_object('config'))
provider = k8s.Provider('k8s', kubeconfig=config.kubeconfig.value)
namespace = k8s.core.v1.Namespace(
    'wazuh-namespace',
    metadata={'name': config.namespace},
    opts=p.ResourceOptions(provider=provider),
)
cloudflare_provider = utils.cloudflare.get_token_provider(config.cloudflare_api_token.value)
ca_secret, credentials = create_pki(config, provider, namespace.metadata.name)
create_indexer(config, provider, namespace.metadata.name, ca_secret, credentials)
create_exporters(config, provider, namespace.metadata.name, ca_secret)
create_manager(config, provider, namespace.metadata.name, credentials, cloudflare_provider)
create_dashboard(
    config, provider, namespace.metadata.name, ca_secret, credentials, cloudflare_provider
)
