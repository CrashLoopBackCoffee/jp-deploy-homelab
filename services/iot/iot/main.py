import pulumi as p
import pulumi_kubernetes as k8s

from iot.config import ComponentConfig
from iot.mosquitto import Mosquitto
from iot.mqtt2prometheus import Mqtt2Prometheus


def main():
    config = p.Config()
    component_config = ComponentConfig.model_validate(config.get_object('config'))

    k8s_provider = k8s.Provider('k8s', kubeconfig=component_config.kubeconfig.value)

    Mosquitto('mosquitto', component_config, k8s_provider)

    Mqtt2Prometheus('mqtt2prometheus', component_config, k8s_provider)
