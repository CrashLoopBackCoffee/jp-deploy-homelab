import typing as t

import utils.model


class MosquittoConfig(utils.model.LocalBaseModel):
    version: str
    hostname: str
    passwords: list[str] = []


class MqttPrometheusInstanceConfig(utils.model.LocalBaseModel):
    name: str
    topic_path: str
    device_id_regex: str | None = None
    metrics: list[dict[str, t.Any]] = []


class MqttPrometheusConfig(utils.model.LocalBaseModel):
    version: str
    username: utils.model.OnePasswordRef
    password: utils.model.OnePasswordRef
    instances: list[MqttPrometheusInstanceConfig] = []


class ComponentConfig(utils.model.LocalBaseModel):
    kubeconfig: utils.model.OnePasswordRef

    cloudflare: utils.model.CloudflareConfig | None = None
    mosquitto: MosquittoConfig
    mqtt2prometheus: MqttPrometheusConfig


class StackConfig(utils.model.LocalBaseModel):
    model_config = {
        'alias_generator': lambda field_name: (
            f'{utils.model.get_pulumi_project(__file__)}:{field_name}'
        )
    }
    config: ComponentConfig


class PulumiConfigRoot(utils.model.LocalBaseModel):
    config: StackConfig
