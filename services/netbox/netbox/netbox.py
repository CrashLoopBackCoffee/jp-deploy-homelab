import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_random as random
import utils.cloudflare
import utils.cnpg

from netbox.config import ComponentConfig

# Service port of the official chart
NETBOX_PORT = 80
VALKEY_PORT = 6379
DATABASE_NAME = 'netbox'
DATABASE_USER = 'netbox'
CHART = 'oci://ghcr.io/netbox-community/netbox-chart/netbox'


class Netbox(p.ComponentResource):
    def __init__(
        self,
        component_config: ComponentConfig,
        namespace: p.Input[str],
        k8s_provider: k8s.Provider,
    ):
        super().__init__('netbox', 'netbox')
        netbox_config = component_config.netbox
        hostname = f'{netbox_config.host}.{component_config.zone}'

        namespaced_provider = k8s.Provider(
            'netbox-provider',
            kubeconfig=k8s_provider.kubeconfig,  # type: ignore
            namespace=namespace,
        )
        k8s_opts = p.ResourceOptions(parent=self, provider=namespaced_provider)

        database_config = component_config.database
        database = utils.cnpg.create_cnpg_database(
            database_config.name,
            database=DATABASE_NAME,
            owner=DATABASE_USER,
            image_version=database_config.image_version,
            storage_size=database_config.storage_size,
            storage_class=database_config.storage_class,
            backup=utils.cnpg.BackupTarget(
                endpoint=database_config.backup.endpoint,
                bucket=database_config.backup.bucket,
                access_key_id=database_config.backup.access_key_id.value,
                secret_access_key=database_config.backup.secret_access_key.value,
                retention_policy=database_config.backup.retention_policy,
                schedule=database_config.backup.schedule,
            ),
            k8s_opts=k8s_opts,
        )

        # The peppers are explicit: the chart would generate them with Helm `lookup`, which does
        # not work under `helm.v4.Chart`, so they would change on every render.
        api_token_pepper = random.RandomPassword(
            'netbox-api-token-pepper', length=64, special=False
        )
        config_secret = k8s.core.v1.Secret(
            'netbox-config',
            metadata={'name': 'netbox-config'},
            string_data={
                'secret_key': random.RandomPassword(
                    'netbox-secret-key', length=64, special=False
                ).result,
                'api_token_peppers': p.Output.json_dumps({'1': api_token_pepper.result}),
                'email_password': '',
            },
            opts=k8s_opts,
        )

        # Only satisfies the chart: the superuser creation is skipped (`SKIP_SUPERUSER`) because
        # the imported account is the only one.
        superuser_secret = k8s.core.v1.Secret(
            'netbox-superuser',
            metadata={'name': 'netbox-superuser'},
            type='kubernetes.io/basic-auth',
            string_data={
                'username': 'admin',
                'password': random.RandomPassword(
                    'netbox-superuser-password', length=32, special=False
                ).result,
                'email': 'admin@4jp.de',
                'api_token': random.RandomId('netbox-superuser-api-token', byte_length=20).hex,
            },
            opts=k8s_opts,
        )

        valkey_service = self._create_valkey(component_config, k8s_opts)

        # The media volume is ReadWriteOnce: the worker has to run next to the web pod.
        affinity = {
            'podAffinity': {
                'requiredDuringSchedulingIgnoredDuringExecution': [
                    {
                        'labelSelector': {'matchLabels': {'app.kubernetes.io/name': 'netbox'}},
                        'topologyKey': 'kubernetes.io/hostname',
                    }
                ]
            }
        }
        values = {
            'replicaCount': 1,
            'allowedHosts': [hostname, p.Output.format('netbox.{}.svc', namespace)],
            # The chart default would allow anonymous reads; the legacy instance required login.
            'loginRequired': True,
            'timeZone': 'UTC',
            'existingSecret': config_secret.metadata.name,
            'superuser': {'existingSecret': superuser_secret.metadata.name},
            'extraEnvs': [{'name': 'SKIP_SUPERUSER', 'value': 'true'}],
            'metrics': {'enabled': True, 'granian': {'enabled': False}},
            'persistence': {'enabled': True, 'size': netbox_config.media_size},
            'reportsPersistence': {'enabled': False},
            'scriptsPersistence': {'enabled': False},
            'ingress': {'enabled': False},
            'httpRoute': {'enabled': False},
            'affinity': affinity,
            'resources': {
                'requests': {'cpu': '100m', 'memory': '512Mi'},
                'limits': {'memory': '1536Mi'},
            },
            # The chart presets set a CPU limit on the init containers; keep them small and
            # without one.
            'init': {
                'resources': {
                    'requests': {'cpu': '10m', 'memory': '16Mi'},
                    'limits': {'memory': '64Mi'},
                },
            },
            'worker': {
                'replicaCount': 1,
                'affinity': affinity,
                'waitForBackend': {
                    'resources': {
                        'requests': {'cpu': '10m', 'memory': '32Mi'},
                        'limits': {'memory': '128Mi'},
                    },
                },
                'resources': {
                    'requests': {'cpu': '25m', 'memory': '256Mi'},
                    'limits': {'memory': '512Mi'},
                },
            },
            'postgresql': {'enabled': False},
            'externalDatabase': {
                'host': database.host,
                'port': database.port,
                'database': DATABASE_NAME,
                'username': DATABASE_USER,
                'existingSecretName': database.app_secret_name,
                'existingSecretKey': 'password',
            },
            'valkey': {'enabled': False},
            'tasksDatabase': {
                'host': valkey_service.metadata.name,
                'port': VALKEY_PORT,
                'database': 0,
            },
            'cachingDatabase': {
                'host': valkey_service.metadata.name,
                'port': VALKEY_PORT,
                'database': 1,
            },
        }

        chart = k8s.helm.v4.Chart(
            'netbox',
            chart=CHART,
            version=netbox_config.chart_version,
            namespace=namespace,
            values=values,
            opts=p.ResourceOptions.merge(
                k8s_opts, p.ResourceOptions(depends_on=[database.cluster])
            ),
        )

        k8s.apiextensions.CustomResource(
            'ingress',
            api_version='traefik.io/v1alpha1',
            kind='IngressRoute',
            metadata={'name': 'ingress'},
            spec={
                'entryPoints': ['websecure'],
                'routes': [
                    {
                        'kind': 'Rule',
                        # `/metrics` is unauthenticated: only Alloy inside the cluster may read
                        # it, so the ingress does not route it.
                        'match': f'Host(`{hostname}`) && !PathPrefix(`/metrics`)',
                        'services': [
                            {
                                'name': 'netbox',
                                'namespace': namespace,
                                'port': NETBOX_PORT,
                            },
                        ],
                    }
                ],
                # use default wildcard certificate:
                'tls': {},
            },
            opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[chart])),
        )

        # The name lives in the public zone and points at Traefik's private address (ADR-0029).
        traefik_service = k8s.core.v1.Service.get(
            'traefik-service', 'traefik/traefik', opts=k8s_opts
        )
        utils.cloudflare.create_a_record(
            'netbox-dns',
            host=netbox_config.host,
            zone_name=component_config.zone,
            address=traefik_service.status.load_balancer.ingress[0].ip,
            cloudflare_provider=utils.cloudflare.get_token_provider(
                component_config.cloudflare_api_token.value
            ),
            opts=p.ResourceOptions(parent=self),
        )

        p.export('netbox_url', f'https://{hostname}')
        self.register_outputs({})

    @staticmethod
    def _create_valkey(
        component_config: ComponentConfig, k8s_opts: p.ResourceOptions
    ) -> k8s.core.v1.Service:
        """Task queue (DB 0) and cache (DB 1). Nothing is persisted: both are rebuilt by NetBox."""
        app_labels = {'app': 'netbox-valkey'}
        k8s.apps.v1.Deployment(
            'netbox-valkey',
            metadata={'name': 'netbox-valkey'},
            spec={
                'replicas': 1,
                'selector': {'match_labels': app_labels},
                'template': {
                    'metadata': {'labels': app_labels},
                    'spec': {
                        'containers': [
                            {
                                'name': 'valkey',
                                'image': f'docker.io/valkey/valkey:{component_config.valkey.version}-alpine',
                                'args': ['valkey-server', '--save', '', '--appendonly', 'no'],
                                'ports': [{'container_port': VALKEY_PORT}],
                                'readiness_probe': {'tcp_socket': {'port': VALKEY_PORT}},
                                'resources': {
                                    'requests': {'cpu': '10m', 'memory': '32Mi'},
                                    'limits': {'memory': '128Mi'},
                                },
                            }
                        ],
                    },
                },
            },
            opts=k8s_opts,
        )
        return k8s.core.v1.Service(
            'netbox-valkey',
            metadata={'name': 'netbox-valkey'},
            spec={
                'ports': [{'port': VALKEY_PORT}],
                'selector': app_labels,
            },
            opts=k8s_opts,
        )
