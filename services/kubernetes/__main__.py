"""Install Kubernetes add-ons on the externally managed k0s cluster."""

import pulumi as p
import pulumi_kubernetes as k8s

from kubernetes.certmanager import create_certmanager
from kubernetes.cloudnativepg import create_cloudnative_pg
from kubernetes.config import ComponentConfig
from kubernetes.csi_nfs import create_csi_nfs
from kubernetes.metallb import create_metallb
from kubernetes.openebs_lvm import create_openebs_lvm
from kubernetes.traefik import create_traefik

component_config = ComponentConfig.model_validate(p.Config().require_object('config'))

k8s_provider = k8s.Provider('k8s', kubeconfig=component_config.kubeconfig.value)

create_metallb(component_config, k8s_provider)
create_csi_nfs(component_config, k8s_provider)
create_openebs_lvm(component_config, k8s_provider)

issuer = create_certmanager(component_config, k8s_provider)
create_traefik(component_config, issuer, k8s_provider)
create_cloudnative_pg(component_config, k8s_provider)

p.export('kubeconfig', component_config.kubeconfig.value)
