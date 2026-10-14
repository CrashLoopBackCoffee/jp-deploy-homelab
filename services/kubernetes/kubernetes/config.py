import ipaddress

import utils.model


class MetallbConfig(utils.model.LocalBaseModel):
    version: str
    start: ipaddress.IPv4Address
    end: ipaddress.IPv4Address


class NfsCsiDriverConfig(utils.model.LocalBaseModel):
    version: str


class LonghornBackupConfig(utils.model.LocalBaseModel):
    endpoint: str
    bucket: str
    region: str
    access_key_id: utils.model.OnePasswordRef
    secret_access_key: utils.model.OnePasswordRef


class LonghornConfig(utils.model.LocalBaseModel):
    version: str
    data_path: str
    replica_count: int
    backup: LonghornBackupConfig


class OpenEbsLvmConfig(utils.model.LocalBaseModel):
    version: str
    volume_group: str


class TraefikConfig(utils.model.LocalBaseModel):
    version: str


class CertManagerConfig(utils.model.LocalBaseModel):
    version: str
    use_staging: bool = False
    acme_email: str

    @property
    def issuer_server(self):
        return (
            'https://acme-staging-v02.api.letsencrypt.org/directory'
            if self.use_staging
            else 'https://acme-v02.api.letsencrypt.org/directory'
        )


class CloudNativePgClusterConfig(utils.model.LocalBaseModel):
    name: str
    image_version: str
    storage_size: str


class CloudNativePgBackupConfig(utils.model.LocalBaseModel):
    endpoint: str
    bucket: str
    access_key_id: utils.model.OnePasswordRef
    secret_access_key: utils.model.OnePasswordRef
    schedule: str
    retention_policy: str


class CloudNativePgConfig(utils.model.LocalBaseModel):
    version: str
    plugin_version: str
    cluster: CloudNativePgClusterConfig
    backup: CloudNativePgBackupConfig


class CloudflareConfig(utils.model.LocalBaseModel):
    api_token: utils.model.OnePasswordRef
    zone: str


class ComponentConfig(utils.model.LocalBaseModel):
    cert_manager: CertManagerConfig
    cloudflare: CloudflareConfig
    cloudnative_pg: CloudNativePgConfig
    csi_nfs_driver: NfsCsiDriverConfig
    kubeconfig: utils.model.OnePasswordRef
    longhorn: LonghornConfig
    metallb: MetallbConfig
    openebs_lvm: OpenEbsLvmConfig
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
