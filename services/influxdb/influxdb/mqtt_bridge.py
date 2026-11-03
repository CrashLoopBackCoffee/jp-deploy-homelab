import pulumi as p
import pulumi_kubernetes as k8s

from influxdb.config import ComponentConfig
from influxdb.influxdb import HTTP_PORT, NAMESPACE

CONFIG_DIR = '/etc/telegraf'

# Replaces mqtt2influxdb: same measurements, one field `value`, no tags (ADR-0045).
TELEGRAF_CONFIG = """\
[agent]
  interval = "10s"
  flush_interval = "10s"
  omit_hostname = true

[[outputs.influxdb]]
  urls = ["http://influxdb.__NAMESPACE__.svc:__HTTP_PORT__"]
  database = "vzlogger"
  skip_database_creation = true

# mqtt2influxdb wrote second-precision timestamps; service inputs ignore agent.precision.
[[processors.starlark]]
  source = '''
def apply(metric):
    metric.time = metric.time - metric.time % 1000000000
    return metric
'''

[[inputs.mqtt_consumer]]
  servers = ["__BROKER__"]
  client_id = "telegraf-vzlogger-meter"
  username = "${MQTT_USERNAME}"
  password = "${MQTT_PASSWORD}"
  topics = ["tele/tasmota_629634/SENSOR"]
  topic_tag = ""
  data_format = "json_v2"
  [[inputs.mqtt_consumer.json_v2]]
    measurement_name = "current_power"
    [[inputs.mqtt_consumer.json_v2.field]]
      path = "MT691.Power_curr"
      rename = "value"
      type = "int"
  [[inputs.mqtt_consumer.json_v2]]
    measurement_name = "meter1"
    [[inputs.mqtt_consumer.json_v2.field]]
      path = "MT691.Total_in"
      rename = "value"
      type = "float"
  [[inputs.mqtt_consumer.json_v2]]
    measurement_name = "meter2"
    [[inputs.mqtt_consumer.json_v2.field]]
      path = "MT691.Total_out"
      rename = "value"
      type = "float"

[[inputs.mqtt_consumer]]
  servers = ["__BROKER__"]
  client_id = "telegraf-vzlogger-bkw"
  username = "${MQTT_USERNAME}"
  password = "${MQTT_PASSWORD}"
  # switch:0 is the only bkw/status/* topic that carries apower
  topics = ["bkw/status/switch:0"]
  topic_tag = ""
  data_format = "json_v2"
  [[inputs.mqtt_consumer.json_v2]]
    measurement_name = "bkw_current_power"
    [[inputs.mqtt_consumer.json_v2.field]]
      path = "apower"
      rename = "value"
      type = "float"

[[inputs.mqtt_consumer]]
  servers = ["__BROKER__"]
  client_id = "telegraf-vzlogger-rolladen"
  username = "${MQTT_USERNAME}"
  password = "${MQTT_PASSWORD}"
  topics = ["shellies/rolladen-dach/roller/0/pos"]
  topic_tag = ""
  name_override = "rolladen_position"
  data_format = "value"
  data_type = "integer"
"""


class MqttBridge(p.ComponentResource):
    def __init__(
        self,
        component_config: ComponentConfig,
        namespace: p.Input[str],
        k8s_provider: k8s.Provider,
    ):
        super().__init__('mqtt-bridge', 'mqtt-bridge')
        config = component_config.mqtt_bridge

        namespaced_provider = k8s.Provider(
            'mqtt-bridge-provider',
            kubeconfig=k8s_provider.kubeconfig,  # type: ignore
            namespace=namespace,
        )
        k8s_opts = p.ResourceOptions(parent=self, provider=namespaced_provider)

        credentials = k8s.core.v1.Secret(
            'mqtt-bridge-credentials',
            string_data={
                'MQTT_USERNAME': config.username.value,
                'MQTT_PASSWORD': config.password.value,
            },
            opts=k8s_opts,
        )

        # Auto-named: a changed config renames the ConfigMap and so rolls the Deployment.
        telegraf_config = (
            TELEGRAF_CONFIG.replace('__BROKER__', config.broker)
            .replace('__NAMESPACE__', NAMESPACE)
            .replace('__HTTP_PORT__', str(HTTP_PORT))
        )
        config_map = k8s.core.v1.ConfigMap(
            'mqtt-bridge-config',
            data={'telegraf.conf': telegraf_config},
            opts=k8s_opts,
        )

        labels = {'app': 'mqtt-bridge'}
        k8s.apps.v1.Deployment(
            'mqtt-bridge',
            metadata={'name': 'mqtt-bridge'},
            spec={
                'replicas': 1,
                'selector': {'match_labels': labels},
                'template': {
                    'metadata': {'labels': labels},
                    'spec': {
                        'enable_service_links': False,
                        'containers': [
                            {
                                'name': 'telegraf',
                                'image': f'telegraf:{config.version}',
                                'env_from': [{'secret_ref': {'name': credentials.metadata.name}}],
                                'volume_mounts': [
                                    {
                                        'name': 'config',
                                        'mount_path': CONFIG_DIR,
                                        'read_only': True,
                                    }
                                ],
                                # Telegraf reconnects to the broker itself, so no probes.
                                'resources': {
                                    'requests': {'cpu': '10m', 'memory': '32Mi'},
                                    'limits': {'memory': '128Mi'},
                                },
                            },
                        ],
                        'volumes': [
                            {
                                'name': 'config',
                                'config_map': {'name': config_map.metadata.name},
                            },
                        ],
                    },
                },
            },
            opts=k8s_opts,
        )

        self.register_outputs({})
