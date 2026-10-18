import utils.model


class TandoorConfig(utils.model.LocalBaseModel):
    version: str
    # Hostname below the zone, e.g. `tandoor` for tandoor.4jp.de
    host: str = 'tandoor'
    media_size: str = '10Gi'
    # Non-secret Tandoor preferences passed as environment variables, for example
    # `FRACTION_PREF_DEFAULT` or `ENABLE_PDF_EXPORT`. The keys of the application's own wiring
    # (database, secret key, hosts, port, time zone) are not overridable.
    settings: dict[str, str] = {}


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

    name: str = 'tandoor-db'
    image_version: str
    storage_size: str = '2Gi'
    storage_class: str = 'openebs-lvm-postgres'
    backup: DatabaseBackupConfig


class NextcloudConfig(utils.model.LocalBaseModel):
    """Off-site WebDAV target; use an app password, not the account password."""

    # Base URL of the Nextcloud server, e.g. https://cloud.example.org; the WebDAV path is derived.
    url: utils.model.OnePasswordRef
    username: utils.model.OnePasswordRef
    password: utils.model.OnePasswordRef


class BackupConfig(utils.model.LocalBaseModel):
    restic_rclone_version: str
    restic_password: utils.model.OnePasswordRef
    repository_path: str = 'tandoor'
    # Standard five-field cron expression, evaluated in UTC by the cluster
    schedule: str = '30 1 * * *'
    retention_daily: int = 7
    retention_weekly: int = 4
    retention_monthly: int = 6
    nextcloud: NextcloudConfig


class ComponentConfig(utils.model.LocalBaseModel):
    kubeconfig: utils.model.OnePasswordRef
    # DNS zone for the ingress hostname
    zone: str
    tandoor: TandoorConfig
    database: DatabaseConfig
    backup: BackupConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
