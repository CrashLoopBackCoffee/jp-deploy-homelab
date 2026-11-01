import utils.model


class InfluxDbConfig(utils.model.LocalBaseModel):
    version: str
    # Hostname below the zone; LAN writers (Home Assistant, mqtt2influxdb) and Grafana use it
    host: str = 'influx'
    # Holds the TSM files, WAL and meta; the two migrated databases take about 9 GB on disk
    storage_size: str = '20Gi'


class ComponentConfig(utils.model.LocalBaseModel):
    kubeconfig: utils.model.OnePasswordRef
    # DNS zone for the ingress hostname
    zone: str
    # Scoped account token (DNS Edit, Zone Read), the one cert-manager uses (ADR-0010).
    cloudflare_api_token: utils.model.OnePasswordRef
    influxdb: InfluxDbConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
