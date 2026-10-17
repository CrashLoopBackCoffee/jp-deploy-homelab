import utils.model


class RedisConfig(utils.model.LocalBaseModel):
    version: str


class TikaConfig(utils.model.LocalBaseModel):
    version: str


class GotenbergConfig(utils.model.LocalBaseModel):
    version: str


class DatabaseBackupConfig(utils.model.LocalBaseModel):
    endpoint: str
    bucket: str
    access_key_id: utils.model.OnePasswordRef
    secret_access_key: utils.model.OnePasswordRef
    # Six-field CloudNativePG cron expression (seconds first)
    schedule: str = '0 0 3 * * *'
    retention_policy: str = '14d'


class DatabaseConfig(utils.model.LocalBaseModel):
    """Dedicated CloudNativePG cluster; its backups go to their own prefix in the bucket."""

    name: str = 'paperless-db'
    image_version: str
    storage_size: str = '5Gi'
    storage_class: str = 'openebs-lvm-postgres'
    backup: DatabaseBackupConfig


class ConsumeConfig(utils.model.LocalBaseModel):
    """NFS share the scanners drop files into."""

    server: str
    share: str
    mount_options: str = 'nfsvers=4.1,sec=sys'


class StorageConfig(utils.model.LocalBaseModel):
    data_size: str = '5Gi'
    media_size: str = '30Gi'
    # The exporter writes a full copy of the original documents, so it needs about the media size.
    export_size: str = '30Gi'


class OidcConfig(utils.model.LocalBaseModel):
    """Authentik provider for single sign-on.

    The group names are the contract with the Authentik blueprint in the AX41 repository.
    """

    # Item `Paperless OIDC`: the client id in `username`, the client secret in `password`.
    client_id: utils.model.OnePasswordRef
    client_secret: utils.model.OnePasswordRef
    # Issuer URL of the Authentik application, `https://<authentik>/application/o/<slug>/`
    issuer_url: str
    # Part of the redirect URI `/accounts/oidc/<provider_id>/login/callback/`
    provider_id: str = 'authentik'
    admins_group: str = 'paperless-admins'


class PaperlessConfig(utils.model.LocalBaseModel):
    version: str
    # Hostname below the zone, e.g. `paperless` for paperless.4jp.de
    host: str = 'paperless'
    ocr_language: str = 'deu+eng'
    consume: ConsumeConfig
    oidc: OidcConfig
    storage: StorageConfig = StorageConfig()


class NextcloudConfig(utils.model.LocalBaseModel):
    """Off-site WebDAV target; use an app password, not the account password."""

    # Base URL of the Nextcloud server, e.g. https://cloud.example.org; the WebDAV path is derived.
    url: utils.model.OnePasswordRef
    username: utils.model.OnePasswordRef
    password: utils.model.OnePasswordRef


class BackupConfig(utils.model.LocalBaseModel):
    restic_rclone_version: str
    kubectl_version: str
    restic_password: utils.model.OnePasswordRef
    repository_path: str = 'paperless'
    schedule: str = '0 2 * * *'
    retention_daily: int = 7
    retention_weekly: int = 4
    retention_monthly: int = 6
    nextcloud: NextcloudConfig


class ComponentConfig(utils.model.LocalBaseModel):
    kubeconfig: utils.model.OnePasswordRef
    # DNS zone for the local record and the ingress hostname
    zone: str
    paperless: PaperlessConfig
    database: DatabaseConfig
    backup: BackupConfig
    redis: RedisConfig
    tika: TikaConfig
    gotenberg: GotenbergConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
