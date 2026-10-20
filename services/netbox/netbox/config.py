import utils.model


class NetboxConfig(utils.model.LocalBaseModel):
    chart_version: str
    # Hostname below the zone, e.g. `netbox` for netbox.4jp.de
    host: str = 'netbox'
    media_size: str = '1Gi'


class ValkeyConfig(utils.model.LocalBaseModel):
    version: str


class DatabaseBackupConfig(utils.model.LocalBaseModel):
    endpoint: str
    bucket: str
    access_key_id: utils.model.OnePasswordRef
    secret_access_key: utils.model.OnePasswordRef
    # Six-field CloudNativePG cron expression (seconds first)
    schedule: str = '0 0 21 * * *'
    retention_policy: str = '14d'


class DatabaseConfig(utils.model.LocalBaseModel):
    """Dedicated CloudNativePG cluster; its backups go to their own prefix in the bucket."""

    name: str = 'netbox-db'
    image_version: str
    storage_size: str = '2Gi'
    storage_class: str = 'openebs-lvm-postgres'
    backup: DatabaseBackupConfig


class ComponentConfig(utils.model.LocalBaseModel):
    kubeconfig: utils.model.OnePasswordRef
    # DNS zone for the ingress hostname
    zone: str
    # Scoped account token (DNS Edit, Zone Read), the one cert-manager uses (ADR-0010).
    cloudflare_api_token: utils.model.OnePasswordRef
    netbox: NetboxConfig
    valkey: ValkeyConfig
    database: DatabaseConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
