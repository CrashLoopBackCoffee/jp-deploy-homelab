import pulumi as p
import pulumi_kubernetes as k8s
import utils.cloudflare

from influxdb.config import ComponentConfig

NAMESPACE = 'influxdb'
HTTP_PORT = 8086
# influxd runs as this user and group in the official image
INFLUXDB_ID = 999
DATA_DIR = '/var/lib/influxdb'


class InfluxDb(p.ComponentResource):
    def __init__(
        self,
        component_config: ComponentConfig,
        namespace: p.Input[str],
        k8s_provider: k8s.Provider,
    ):
        super().__init__('influxdb', 'influxdb')
        config = component_config.influxdb
        hostname = f'{config.host}.{component_config.zone}'

        namespaced_provider = k8s.Provider(
            'influxdb-provider',
            kubeconfig=k8s_provider.kubeconfig,  # type: ignore
            namespace=namespace,
        )
        k8s_opts = p.ResourceOptions(parent=self, provider=namespaced_provider)

        data_claim = k8s.core.v1.PersistentVolumeClaim(
            'influxdb',
            metadata={'name': 'influxdb'},
            spec={
                'access_modes': ['ReadWriteOnce'],
                'resources': {'requests': {'storage': config.storage_size}},
            },
            opts=k8s_opts,
        )

        labels = {'app': 'influxdb'}
        deployment = k8s.apps.v1.Deployment(
            'influxdb',
            metadata={'name': 'influxdb'},
            spec={
                'replicas': 1,
                'selector': {'match_labels': labels},
                # The data volume is ReadWriteOnce.
                'strategy': {'type': 'Recreate'},
                'template': {
                    'metadata': {'labels': labels},
                    'spec': {
                        'enable_service_links': False,
                        'security_context': {
                            'run_as_user': INFLUXDB_ID,
                            'run_as_group': INFLUXDB_ID,
                            'fs_group': INFLUXDB_ID,
                        },
                        'containers': [
                            {
                                'name': 'influxdb',
                                'image': f'influxdb:{config.version}',
                                'env': [
                                    {'name': 'INFLUXDB_REPORTING_DISABLED', 'value': 'true'},
                                    # One line per write would flood the log; errors still appear.
                                    {'name': 'INFLUXDB_HTTP_LOG_ENABLED', 'value': 'false'},
                                ],
                                'ports': [{'name': 'http', 'container_port': HTTP_PORT}],
                                'volume_mounts': [{'name': 'data', 'mount_path': DATA_DIR}],
                                'readiness_probe': {
                                    'http_get': {'path': '/ping', 'port': HTTP_PORT},
                                },
                                'liveness_probe': {
                                    'http_get': {'path': '/ping', 'port': HTTP_PORT},
                                    'initial_delay_seconds': 60,
                                    'failure_threshold': 6,
                                },
                                'resources': {
                                    'requests': {'cpu': '50m', 'memory': '512Mi'},
                                    'limits': {'memory': '2Gi'},
                                },
                            },
                        ],
                        'volumes': [
                            {
                                'name': 'data',
                                'persistent_volume_claim': {
                                    'claim_name': data_claim.metadata.name,
                                },
                            },
                        ],
                    },
                },
            },
            opts=k8s_opts,
        )

        service = k8s.core.v1.Service(
            'influxdb',
            metadata={'name': 'influxdb'},
            spec={
                'ports': [{'port': HTTP_PORT}],
                'selector': deployment.spec.selector.match_labels,
            },
            opts=k8s_opts,
        )

        # The writers on the LAN use the name; the cluster wildcard certificate covers it.
        k8s.apiextensions.CustomResource(
            'influxdb',
            api_version='traefik.io/v1alpha1',
            kind='IngressRoute',
            metadata={'name': 'influxdb'},
            spec={
                'entryPoints': ['websecure'],
                'routes': [
                    {
                        'kind': 'Rule',
                        'match': f'Host(`{hostname}`)',
                        'services': [
                            {
                                'name': service.metadata.name,
                                'namespace': service.metadata.namespace,
                                'port': HTTP_PORT,
                            },
                        ],
                    }
                ],
                # use default wildcard certificate:
                'tls': {},
            },
            opts=k8s_opts,
        )

        # The name lives in the public zone and points at Traefik's private address (ADR-0029).
        traefik_service = k8s.core.v1.Service.get(
            'traefik-service', 'traefik/traefik', opts=k8s_opts
        )
        cloudflare_provider = utils.cloudflare.get_token_provider(
            component_config.cloudflare_api_token.value
        )
        utils.cloudflare.create_a_record(
            'influxdb-dns',
            host=config.host,
            zone_name=component_config.zone,
            address=traefik_service.status.load_balancer.ingress[0].ip,
            cloudflare_provider=cloudflare_provider,
            opts=p.ResourceOptions(parent=self),
        )

        p.export('influxdb_url', f'https://{hostname}')
        p.export('influxdb_cluster_url', f'http://influxdb.{NAMESPACE}.svc:{HTTP_PORT}')
        self.register_outputs({})
