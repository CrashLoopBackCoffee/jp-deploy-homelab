import utils.model


class TeslaLoggerConfig(utils.model.LocalBaseModel):
    # One tag for all three upstream images (teslalogger, teslalogger-webserver, teslalogger-grafana)
    version: str
    # Hostnames below the zone
    host: str = 'tesla-logger'
    grafana_host: str = 'grafana.tesla-logger'
    # Holds /tmp, data, backup (TeslaLogger's own nightly dumps), invoices and Grafana's database
    storage_size: str = '5Gi'
    # 0 while importing data: TeslaLogger must not start on an empty database
    replicas: int = 1


class DatabaseBackupConfig(utils.model.LocalBaseModel):
    # host:port without scheme
    endpoint: str
    bucket: str
    region: str
    access_key_id: utils.model.OnePasswordRef
    secret_access_key: utils.model.OnePasswordRef
    # Five-field cron expression in UTC
    schedule: str = '0 21 * * *'
    max_retention: str = '336h'


class DatabaseConfig(utils.model.LocalBaseModel):
    image_version: str
    storage_size: str = '5Gi'
    backup: DatabaseBackupConfig


class ComponentConfig(utils.model.LocalBaseModel):
    kubeconfig: utils.model.OnePasswordRef
    # DNS zone for the ingress hostnames
    zone: str
    # Scoped account token (DNS Edit, Zone Read), the one cert-manager uses (ADR-0010).
    cloudflare_api_token: utils.model.OnePasswordRef
    teslalogger: TeslaLoggerConfig
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
