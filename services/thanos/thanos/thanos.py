import json

import pulumi as p
import pulumi_kubernetes as k8s

from thanos.config import ComponentConfig

NAMESPACE = 'thanos'
# Release name equals the chart name, so the chart prefixes its resources with `thanos-`. Alloy and
# Grafana in the observability stack use these addresses (observability/thanos_archive.py).
RECEIVE_REMOTE_WRITE_URL = (
    f'http://thanos-receive-router.{NAMESPACE}.svc.cluster.local:19291/api/v1/receive'
)
QUERY_URL = f'http://thanos-query.{NAMESPACE}.svc.cluster.local:10902'
STORAGE_CLASS = 'longhorn'


def _persistence(size_gb: int) -> dict:
    return {'enabled': True, 'storageClass': STORAGE_CLASS, 'size': f'{size_gb}Gi'}


def _resources(request_memory: str, limit_memory: str) -> dict:
    return {
        'requests': {'cpu': '25m', 'memory': request_memory},
        'limits': {'memory': limit_memory},
    }


class Thanos(p.ComponentResource):
    def __init__(
        self,
        component_config: ComponentConfig,
        namespace: p.Input[str],
        k8s_provider: k8s.Provider,
    ):
        super().__init__('thanos', 'thanos')
        config = component_config.thanos

        namespaced_provider = k8s.Provider(
            'thanos-provider',
            kubeconfig=k8s_provider.kubeconfig,  # type: ignore
            namespace=namespace,
        )
        k8s_opts = p.ResourceOptions(parent=self, provider=namespaced_provider)

        objstore_config = p.Output.all(
            config.objstore.access_key_id.value, config.objstore.secret_access_key.value
        ).apply(
            lambda keys: json.dumps(
                {
                    'type': 'S3',
                    'config': {
                        'endpoint': config.objstore.endpoint,
                        'bucket': config.objstore.bucket,
                        'access_key': keys[0],
                        'secret_key': keys[1],
                        'insecure': False,
                    },
                }
            )
        )
        objstore_secret = k8s.core.v1.Secret(
            'thanos-objstore',
            metadata={'name': 'thanos-objstore'},
            string_data={'config': p.Output.secret(objstore_config)},
            opts=k8s_opts,
        )

        k8s.helm.v4.Chart(
            'thanos',
            # The classic repository (steve.hipwell.xyz/helm-charts) fails to load in Pulumi ("Chart.yaml
            # file is missing"), the OCI artifact of the same chart works.
            chart='oci://ghcr.io/stevehipwell/helm-charts/thanos',
            version=config.version,
            namespace=namespace,
            values={
                'objstoreConfig': {
                    'create': False,
                    'name': objstore_secret.metadata.name,
                    'key': 'config',
                },
                # Home Assistant is scraped by Alloy and written to the router (ADR-0047).
                'receive': {
                    'enabled': True,
                    'retention': '48h',
                    'ingestor': {
                        'persistence': _persistence(config.receive_storage_size_gb),
                        'resources': _resources('256Mi', '1Gi'),
                    },
                    'router': {'resources': _resources('64Mi', '256Mi')},
                },
                # Raw data is kept forever and downsampling is off: about 0.9 GB a year.
                'compact': {
                    'enabled': True,
                    'persistence': _persistence(config.compactor_storage_size_gb),
                    'resources': _resources('128Mi', '1Gi'),
                    'extraArgs': [
                        '--retention.resolution-raw=0d',
                        '--retention.resolution-5m=0d',
                        '--retention.resolution-1h=0d',
                        '--downsampling.disable',
                    ],
                },
                'storeGateway': {
                    'persistence': _persistence(config.store_gateway_storage_size_gb),
                    'resources': _resources('128Mi', '512Mi'),
                },
                'query': {'resources': _resources('128Mi', '512Mi')},
            },
            opts=k8s_opts,
        )

        p.export('thanos_receive_remote_write_url', RECEIVE_REMOTE_WRITE_URL)
        p.export('thanos_query_url', QUERY_URL)
        self.register_outputs({})
