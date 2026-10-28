import utils.model


class ComponentConfig(utils.model.LocalBaseModel):
    kubeconfig: utils.model.OnePasswordRef
    version: str = '4.14.9'
    namespace: str = 'wazuh'
    dashboard_hostname: str = 'wazuh.4jp.de'
    manager_hostname: str = 'wazuh-manager.4jp.de'
    agent_address: str = '10.10.88.3'
    indexer_storage: str = '50Gi'
    manager_storage: str = '20Gi'
    indexer_heap: str = '2g'
    indexer_memory_request: str = '3Gi'
    indexer_memory_limit: str = '4Gi'
    indexer_cpu_request: str = '500m'


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
