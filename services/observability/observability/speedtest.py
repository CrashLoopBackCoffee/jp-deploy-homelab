import pulumi as p
import pulumi_kubernetes as k8s

from observability.config import ComponentConfig

SPEEDTEST_PORT = 9469
SPEEDTEST_LABELS = {'app.kubernetes.io/name': 'speedtest-exporter'}


def create_speedtest_exporter(component_config: ComponentConfig, k8s_opts: p.ResourceOptions):
    """Internet speed test, run by the exporter at every scrape of Alloy (every 30 minutes).

    It measures the uplink of the cluster, not of the old dockerhost. The port is not named
    `metrics`, so the generic pod scrape in Alloy leaves it alone: a scrape starts a real test.
    """
    deployment = k8s.apps.v1.Deployment(
        'speedtest-exporter',
        metadata={'name': 'speedtest-exporter'},
        spec={
            'replicas': 1,
            'selector': {'match_labels': SPEEDTEST_LABELS},
            'template': {
                'metadata': {'labels': SPEEDTEST_LABELS},
                'spec': {
                    'containers': [
                        {
                            'name': 'speedtest-exporter',
                            'image': (
                                'billimek/prometheus-speedtest-exporter:'
                                f'{component_config.speedtest_exporter.version}'
                            ),
                            'ports': [{'name': 'probe', 'container_port': SPEEDTEST_PORT}],
                            # No CPU limit: it would throttle the measurement.
                            'resources': {
                                'requests': {'cpu': '50m', 'memory': '64Mi'},
                                'limits': {'memory': '256Mi'},
                            },
                        },
                    ],
                },
            },
        },
        opts=k8s_opts,
    )

    return k8s.core.v1.Service(
        'speedtest-exporter',
        metadata={'name': 'speedtest-exporter'},
        spec={
            'selector': SPEEDTEST_LABELS,
            'ports': [{'name': 'probe', 'port': SPEEDTEST_PORT, 'target_port': 'probe'}],
        },
        opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[deployment])),
    )
