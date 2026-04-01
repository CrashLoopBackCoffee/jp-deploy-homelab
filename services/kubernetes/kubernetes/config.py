import ipaddress

import utils.model


class MetallbConfig(utils.model.LocalBaseModel):
    version: str
    start: ipaddress.IPv4Address
    end: ipaddress.IPv4Address


class NfsCsiDriverConfig(utils.model.LocalBaseModel):
    version: str


class TraefikConfig(utils.model.LocalBaseModel):
    version: str


class K0sConfig(utils.model.LocalBaseModel):
    kubeconfig: utils.model.PulumiSecret
    metallb: MetallbConfig


class CertManagerConfig(utils.model.LocalBaseModel):
    version: str
    use_staging: bool = False

    @property
    def issuer_server(self):
        return (
            'https://acme-staging-v02.api.letsencrypt.org/directory'
            if self.use_staging
            else 'https://acme-v02.api.letsencrypt.org/directory'
        )


class CloudNativePgConfig(utils.model.LocalBaseModel):
    version: str


class ComponentConfig(utils.model.LocalBaseModel):
    cert_manager: CertManagerConfig
    cloudflare: utils.model.CloudflareConfig
    cloudnative_pg: CloudNativePgConfig
    k0s: K0sConfig
    csi_nfs_driver: NfsCsiDriverConfig
    traefik: TraefikConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
