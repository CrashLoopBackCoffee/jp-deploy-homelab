import utils.model


class ChartConfig(utils.model.LocalBaseModel):
    version: str


class LokiConfig(ChartConfig):
    retention_days: int
    storage_size_gb: int


class MimirConfig(ChartConfig):
    retention_days: int
    # S3 endpoint as host:port without scheme; TLS is always on.
    endpoint: str
    bucket: str
    access_key_id: utils.model.OnePasswordRef
    secret_access_key: utils.model.OnePasswordRef
    ingester_storage_size_gb: int
    store_gateway_storage_size_gb: int
    compactor_storage_size_gb: int
    # Mimir's default of 150,000 was reached by pod churn plus the Wazuh and Trivy series (ADR-0041)
    max_global_series_per_user: int


class PushoverConfig(utils.model.LocalBaseModel):
    api_token: utils.model.OnePasswordRef
    user_key: utils.model.OnePasswordRef


class GrafanaConfig(ChartConfig):
    # Hostname below the zone, e.g. `g` for g.4jp.de
    host: str
    storage_size_gb: int
    opensearch_plugin_version: str
    pushover: PushoverConfig


class SyslogConfig(utils.model.LocalBaseModel):
    """Receiver for syslog from the QNAP and OPNsense on a fixed MetalLB address."""

    # Hostname below the zone, e.g. `syslog` for syslog.4jp.de
    host: str
    # Fixed address from the MetalLB pool
    address: str
    # CIDRs allowed to send; enforced by kube-proxy for the LoadBalancer address
    allowed_sources: list[str]


class ScrapeCredentials(utils.model.LocalBaseModel):
    """Basic-auth login of a metrics endpoint that Alloy scrapes over HTTPS."""

    username: utils.model.OnePasswordRef
    password: utils.model.OnePasswordRef


class OpnsenseConfig(ChartConfig):
    """OPNsense metrics: the os-node_exporter plugin and the API exporter (ADR-0038).

    `version` is the image tag of ghcr.io/athennamind/opnsense-exporter.
    """

    # Host of the OPNsense API; must match the web GUI certificate
    api_host: str
    # host:port of the os-node_exporter plugin, bound to the CoRE interface
    node_exporter_target: str
    # Key and secret of the read-only API user `metrics-exporter`
    api_key: utils.model.OnePasswordRef
    api_secret: utils.model.OnePasswordRef


class AlloyConfig(ChartConfig):
    syslog: SyslogConfig
    # Secure Note listing the probe and scrape targets, one `<group> <target>` per line
    targets: utils.model.OnePasswordRef
    ax51: ScrapeCredentials
    pretix: ScrapeCredentials
    # Django `sessionid` of the space-less Tandoor user `tandoor-metrics` (ADR-0035)
    tandoor_session: utils.model.OnePasswordRef


class ComponentConfig(utils.model.LocalBaseModel):
    kubeconfig: utils.model.OnePasswordRef
    # DNS zone for the local records and the ingress hostname
    zone: str
    loki: LokiConfig
    mimir: MimirConfig
    alloy: AlloyConfig
    grafana: GrafanaConfig
    kube_state_metrics: ChartConfig
    node_exporter: ChartConfig
    speedtest_exporter: ChartConfig
    opnsense: OpnsenseConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
