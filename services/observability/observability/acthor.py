import json

import pulumi as p
import pulumi_kubernetes as k8s

from observability.config import ComponentConfig

ACTHOR_EXPORTER_PORT = 7979
ACTHOR_EXPORTER_LABELS = {'app.kubernetes.io/name': 'acthor-exporter'}

# `data.jsn` of the my-PV AC•THOR. The exporter cannot scale, so the temperature stays in the
# device's unit of 0.1 °C. Only fields that are always numeric are listed: a null value fails the
# whole probe.
_ACTHOR_CONFIG = {
    'modules': {
        'acthor': {
            'metrics': [
                {
                    'name': 'acthor_power_act_watts',
                    'type': 'value',
                    'help': 'Power the AC•THOR currently puts into the heater.',
                    'path': '{.power_act}',
                },
                {
                    'name': 'acthor_load_nom_watts',
                    'type': 'value',
                    'help': 'Nominal power of the connected heater.',
                    'path': '{.load_nom}',
                },
                {
                    'name': 'acthor_temp1_decicelsius',
                    'type': 'value',
                    'help': 'Hot water temperature (sensor 1) in units of 0.1 degrees Celsius.',
                    'path': '{.temp1}',
                },
                {
                    'name': 'acthor_boost_active',
                    'type': 'value',
                    'help': '1 while the boost backup (heating from the grid on purpose) is active.',
                    'path': '{.boostactive}',
                },
                {
                    'name': 'acthor_error_state',
                    'type': 'value',
                    'help': 'Error code of the device, 0 when healthy.',
                    'path': '{.error_state}',
                },
            ],
        },
    },
}


def create_acthor_exporter(component_config: ComponentConfig, k8s_opts: p.ResourceOptions):
    """JSON exporter for the AC•THOR on HoME, so that the heating is watched without Home Assistant."""
    config_map = k8s.core.v1.ConfigMap(
        'acthor-exporter',
        metadata={'name': 'acthor-exporter'},
        data={'config.yml': json.dumps(_ACTHOR_CONFIG, separators=(',', ':'))},
        opts=k8s_opts,
    )
    deployment = k8s.apps.v1.Deployment(
        'acthor-exporter',
        metadata={'name': 'acthor-exporter'},
        spec={
            'replicas': 1,
            'selector': {'match_labels': ACTHOR_EXPORTER_LABELS},
            'template': {
                'metadata': {'labels': ACTHOR_EXPORTER_LABELS},
                'spec': {
                    'containers': [
                        {
                            'name': 'json-exporter',
                            'image': (
                                'quay.io/prometheuscommunity/json-exporter:'
                                f'{component_config.acthor.version}'
                            ),
                            'args': [
                                '--config.file=/config/config.yml',
                                f'--web.listen-address=:{ACTHOR_EXPORTER_PORT}',
                            ],
                            # Not named `metrics`, so the generic pod scrape in Alloy ignores it
                            # and the explicit `acthor` job owns it.
                            'ports': [{'name': 'http', 'container_port': ACTHOR_EXPORTER_PORT}],
                            'volume_mounts': [
                                {'name': 'config', 'mount_path': '/config', 'read_only': True}
                            ],
                            'resources': {
                                'requests': {'cpu': '10m', 'memory': '16Mi'},
                                'limits': {'memory': '64Mi'},
                            },
                        },
                    ],
                    'volumes': [{'name': 'config', 'config_map': {'name': 'acthor-exporter'}}],
                },
            },
        },
        opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[config_map])),
    )

    return k8s.core.v1.Service(
        'acthor-exporter',
        metadata={'name': 'acthor-exporter'},
        spec={
            'selector': ACTHOR_EXPORTER_LABELS,
            'ports': [{'name': 'http', 'port': ACTHOR_EXPORTER_PORT, 'target_port': 'http'}],
        },
        opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[deployment])),
    )
