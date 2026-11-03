import utils.model


class ObjectStoreConfig(utils.model.LocalBaseModel):
    # S3 endpoint as host:port without scheme; TLS is always on.
    endpoint: str
    bucket: str
    access_key_id: utils.model.OnePasswordRef
    secret_access_key: utils.model.OnePasswordRef


class ThanosConfig(utils.model.LocalBaseModel):
    # Helm chart version (Thanos itself is the chart's appVersion)
    version: str
    objstore: ObjectStoreConfig
    # Receive keeps 48 h locally and ships 2 h blocks to the bucket; the WAL lives here.
    receive_storage_size_gb: int
    # Scratch space of the compactor; it can be rebuilt from the bucket.
    compactor_storage_size_gb: int
    store_gateway_storage_size_gb: int


class ComponentConfig(utils.model.LocalBaseModel):
    kubeconfig: utils.model.OnePasswordRef
    thanos: ThanosConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
