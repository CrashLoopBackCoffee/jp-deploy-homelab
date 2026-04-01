import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_kubernetes as k8s

from kubernetes.certmanager import create_certmanager
from kubernetes.cloudnativepg import create_cloudnative_pg
from kubernetes.config import ComponentConfig
from kubernetes.csi_nfs import create_csi_nfs
from kubernetes.metallb import create_metallb
from kubernetes.traefik import create_traefik

component_config = ComponentConfig.model_validate(p.Config().get_object('config'))

cloudflare_provider = cloudflare.Provider(
    'cloudflare',
    api_key=component_config.cloudflare.api_key.value,
    email=component_config.cloudflare.email,
)

# kubeconfig is stored as a Pulumi secret set via:
#   k0sctl kubeconfig -c services/k0s/k0sctl/cluster.yaml \
#     | (cd services/kubernetes && pulumi config set --secret kubernetes:config.k0s.kubeconfig -)
k8s_provider = k8s.Provider('k0s', kubeconfig=component_config.k0s.kubeconfig)

create_metallb(component_config, k8s_provider)

issuer = create_certmanager(component_config, cloudflare_provider, k8s_provider)

create_traefik(component_config, issuer, k8s_provider)

create_csi_nfs(component_config, k8s_provider)

create_cloudnative_pg(component_config, k8s_provider)
