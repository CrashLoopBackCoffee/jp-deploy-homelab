import utils.model


class ComponentConfig(utils.model.LocalBaseModel):
    kubeconfig: utils.model.OnePasswordRef
    cloudflare_api_token: utils.model.OnePasswordRef
    zone: str
    version: str
    namespace: str = 'wazuh'
    dashboard_hostname: str
    manager_hostname: str
    agent_address: str
    agent_source_ranges: list[str]
    indexer_storage: str = '50Gi'
    manager_storage: str = '20Gi'
    indexer_heap: str = '2g'
    indexer_memory_request: str = '3Gi'
    indexer_memory_limit: str = '4Gi'
    indexer_cpu_request: str = '500m'
    busybox_version: str
    kubectl_version: str


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
