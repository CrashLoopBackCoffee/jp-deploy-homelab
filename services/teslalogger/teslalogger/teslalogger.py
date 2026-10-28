import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_random as random
import utils.cloudflare
import utils.mariadb

from teslalogger.config import ComponentConfig

# TeslaLogger, its PHP admin panel and its Grafana datasource hardcode these names and credentials,
# so the database, the Services and the root password cannot be chosen freely. The NetworkPolicy
# from `utils.mariadb` keeps the credentials inside the namespace.
DATABASE_RESOURCE_NAME = 'database'
DATABASE_NAME = 'teslalogger'
DATABASE_ROOT_PASSWORD = 'teslalogger'
TIME_ZONE = 'Europe/Berlin'

API_PORT = 5000
WEB_PORT = 80
GRAFANA_PORT = 3000
IMAGE_REPOSITORY = 'bassmaster187/teslalogger'

PREPARE_SCRIPT = """\
set -e
mkdir -p /state/tmp /state/data /state/backup /state/invoices /state/grafana
# PHP runs as www-data and keeps its sessions in the shared /tmp
chmod 1777 /state/tmp
# The upstream image detects Docker mode by these files in its own /tmp, which the volume hides
echo DOCKER > /state/tmp/teslalogger-DOCKER
echo DOCKER > /state/tmp/teslalogger-dockernet8
# Grafana runs as uid 472
chown 472:0 /state/grafana
# Grafana loads plugins only at startup; teslalogger would copy them too late
cp -a /etc/teslalogger/git/TeslaLogger/GrafanaPlugins/. /grafana-plugins/
"""


class TeslaLogger(p.ComponentResource):
    def __init__(
        self,
        component_config: ComponentConfig,
        namespace: p.Input[str],
        k8s_provider: k8s.Provider,
    ):
        super().__init__('teslalogger', 'teslalogger')
        config = component_config.teslalogger
        database_config = component_config.database
        hostname = f'{config.host}.{component_config.zone}'
        grafana_hostname = f'{config.grafana_host}.{component_config.zone}'

        namespaced_provider = k8s.Provider(
            'teslalogger-provider',
            kubeconfig=k8s_provider.kubeconfig,  # type: ignore
            namespace=namespace,
        )
        k8s_opts = p.ResourceOptions(parent=self, provider=namespaced_provider)

        database = utils.mariadb.create_mariadb_database(
            DATABASE_RESOURCE_NAME,
            database=DATABASE_NAME,
            character_set='utf8mb4',
            collate='utf8mb4_unicode_ci',  # as on the legacy instance
            root_password=DATABASE_ROOT_PASSWORD,
            image_version=database_config.image_version,
            storage_size=database_config.storage_size,
            # The legacy instance ran with TZ=Europe/Berlin and time_zone=SYSTEM
            time_zone=TIME_ZONE,
            backup_prefix='teslalogger-db',
            backup=utils.mariadb.BackupTarget(
                endpoint=database_config.backup.endpoint,
                bucket=database_config.backup.bucket,
                region=database_config.backup.region,
                access_key_id=database_config.backup.access_key_id.value,
                secret_access_key=database_config.backup.secret_access_key.value,
                schedule=database_config.backup.schedule,
                max_retention=database_config.backup.max_retention,
            ),
            k8s_opts=k8s_opts,
        )

        grafana_admin = k8s.core.v1.Secret(
            'grafana-admin',
            metadata={'name': 'grafana-admin'},
            string_data={
                'password': random.RandomPassword(
                    'grafana-admin-password', length=32, special=False
                ).result,
            },
            opts=k8s_opts,
        )

        state_claim = k8s.core.v1.PersistentVolumeClaim(
            'teslalogger',
            metadata={'name': 'teslalogger'},
            spec={
                'access_modes': ['ReadWriteOnce'],
                'resources': {'requests': {'storage': config.storage_size}},
            },
            opts=k8s_opts,
        )

        def image(suffix: str = '') -> str:
            return f'{IMAGE_REPOSITORY}{suffix}:{config.version}'

        time_zone_env: list[k8s.core.v1.EnvVarArgsDict] = [{'name': 'TZ', 'value': TIME_ZONE}]
        # teslalogger and the PHP webserver share /tmp (sessions, settings copies).
        tmp_mount: k8s.core.v1.VolumeMountArgsDict = {
            'name': 'state',
            'sub_path': 'tmp',
            'mount_path': '/tmp',
        }
        # teslalogger regenerates the dashboards and copies the plugins on every start; Grafana
        # reads both.
        grafana_content_mounts: list[k8s.core.v1.VolumeMountArgsDict] = [
            {'name': 'grafana-dashboards', 'mount_path': '/var/lib/grafana/dashboards'},
            {'name': 'grafana-plugins', 'mount_path': '/var/lib/grafana/plugins'},
        ]

        app_labels = {'app': 'teslalogger'}
        deployment = k8s.apps.v1.Deployment(
            'teslalogger',
            metadata={'name': 'teslalogger'},
            spec={
                'replicas': config.replicas,
                'selector': {'match_labels': app_labels},
                # The state volume is ReadWriteOnce.
                'strategy': {'type': 'Recreate'},
                'template': {
                    'metadata': {'labels': app_labels},
                    'spec': {
                        # Service links would inject variables such as TESLALOGGER_PORT.
                        'enable_service_links': False,
                        'init_containers': [
                            {
                                'name': 'prepare',
                                'image': image(),
                                'command': ['sh', '-c', PREPARE_SCRIPT],
                                'volume_mounts': [
                                    {'name': 'state', 'mount_path': '/state'},
                                    {'name': 'grafana-plugins', 'mount_path': '/grafana-plugins'},
                                ],
                            },
                        ],
                        'containers': [
                            {
                                'name': 'teslalogger',
                                'image': image(),
                                'env': time_zone_env,
                                'ports': [{'name': 'api', 'container_port': API_PORT}],
                                'volume_mounts': [
                                    tmp_mount,
                                    {
                                        'name': 'state',
                                        'sub_path': 'data',
                                        'mount_path': '/etc/teslalogger/data',
                                    },
                                    {
                                        'name': 'state',
                                        'sub_path': 'backup',
                                        'mount_path': '/etc/teslalogger/backup',
                                    },
                                    {
                                        'name': 'state',
                                        'sub_path': 'invoices',
                                        'mount_path': '/etc/teslalogger/Debug/net8.0/tesla_invoices',
                                    },
                                    *grafana_content_mounts,
                                ],
                                'readiness_probe': {'tcp_socket': {'port': API_PORT}},
                                'resources': {
                                    'requests': {'cpu': '50m', 'memory': '256Mi'},
                                    'limits': {'memory': '1Gi'},
                                },
                            },
                            {
                                'name': 'webserver',
                                'image': image('-webserver'),
                                'env': time_zone_env,
                                'ports': [{'name': 'http', 'container_port': WEB_PORT}],
                                'volume_mounts': [tmp_mount],
                                'readiness_probe': {'tcp_socket': {'port': WEB_PORT}},
                                'resources': {
                                    'requests': {'cpu': '10m', 'memory': '64Mi'},
                                    'limits': {'memory': '256Mi'},
                                },
                            },
                            {
                                'name': 'grafana',
                                'image': image('-grafana'),
                                'env': [
                                    *time_zone_env,
                                    {
                                        'name': 'GF_SECURITY_ADMIN_PASSWORD',
                                        'value_from': {
                                            'secret_key_ref': {
                                                'name': grafana_admin.metadata.name,
                                                'key': 'password',
                                            },
                                        },
                                    },
                                ],
                                'ports': [{'name': 'grafana', 'container_port': GRAFANA_PORT}],
                                'volume_mounts': [
                                    {
                                        'name': 'state',
                                        'sub_path': 'grafana',
                                        'mount_path': '/var/lib/grafana',
                                    },
                                    *grafana_content_mounts,
                                ],
                                'readiness_probe': {
                                    'http_get': {'path': '/api/health', 'port': GRAFANA_PORT},
                                },
                                'resources': {
                                    'requests': {'cpu': '20m', 'memory': '128Mi'},
                                    'limits': {'memory': '512Mi'},
                                },
                            },
                        ],
                        'volumes': [
                            {
                                'name': 'state',
                                'persistent_volume_claim': {
                                    'claim_name': state_claim.metadata.name,
                                },
                            },
                            {'name': 'grafana-dashboards', 'empty_dir': {}},
                            {'name': 'grafana-plugins', 'empty_dir': {}},
                        ],
                    },
                },
            },
            opts=p.ResourceOptions.merge(
                k8s_opts, p.ResourceOptions(depends_on=[database.mariadb, database.database])
            ),
        )

        # The names are fixed: the PHP admin panel calls http://teslalogger:5000 and
        # http://grafana:3000.
        services: dict[str, k8s.core.v1.Service] = {}
        for service_name, port in (
            ('teslalogger', API_PORT),
            ('grafana', GRAFANA_PORT),
            ('webserver', WEB_PORT),
        ):
            services[service_name] = k8s.core.v1.Service(
                service_name,
                metadata={'name': service_name},
                spec={
                    'ports': [{'port': port}],
                    'selector': deployment.spec.selector.match_labels,
                },
                opts=k8s_opts,
            )

        # The cluster wildcard only covers `*.4jp.de`, not the second-level Grafana name.
        grafana_certificate = k8s.apiextensions.CustomResource(
            'grafana-certificate',
            api_version='cert-manager.io/v1',
            kind='Certificate',
            metadata={
                'name': 'grafana-certificate',
                'annotations': {'pulumi.com/waitFor': 'condition=Ready'},
            },
            spec={
                'secretName': 'grafana-certificate',
                'dnsNames': [grafana_hostname],
                'issuerRef': {'name': 'lets-encrypt', 'kind': 'ClusterIssuer'},
            },
            opts=k8s_opts,
        )

        # Port 5000 is not routed: the admin panel proxies it inside the cluster.
        k8s.apiextensions.CustomResource(
            'webserver',
            api_version='traefik.io/v1alpha1',
            kind='IngressRoute',
            metadata={'name': 'webserver'},
            spec={
                'entryPoints': ['websecure'],
                'routes': [
                    {
                        'kind': 'Rule',
                        'match': f'Host(`{hostname}`)',
                        'services': [
                            {
                                'name': services['webserver'].metadata.name,
                                'namespace': services['webserver'].metadata.namespace,
                                'port': WEB_PORT,
                            },
                        ],
                    }
                ],
                # use default wildcard certificate:
                'tls': {},
            },
            opts=k8s_opts,
        )
        k8s.apiextensions.CustomResource(
            'grafana',
            api_version='traefik.io/v1alpha1',
            kind='IngressRoute',
            metadata={'name': 'grafana'},
            spec={
                'entryPoints': ['websecure'],
                'routes': [
                    {
                        'kind': 'Rule',
                        'match': f'Host(`{grafana_hostname}`)',
                        'services': [
                            {
                                'name': services['grafana'].metadata.name,
                                'namespace': services['grafana'].metadata.namespace,
                                'port': GRAFANA_PORT,
                            },
                        ],
                    }
                ],
                'tls': {'secretName': 'grafana-certificate'},
            },
            opts=p.ResourceOptions.merge(
                k8s_opts, p.ResourceOptions(depends_on=[grafana_certificate])
            ),
        )

        # The names live in the public zone and point at Traefik's private address (ADR-0029).
        traefik_service = k8s.core.v1.Service.get(
            'traefik-service', 'traefik/traefik', opts=k8s_opts
        )
        cloudflare_provider = utils.cloudflare.get_token_provider(
            component_config.cloudflare_api_token.value
        )
        for resource_name, host in (
            ('teslalogger-dns', config.host),
            ('teslalogger-grafana-dns', config.grafana_host),
        ):
            utils.cloudflare.create_a_record(
                resource_name,
                host=host,
                zone_name=component_config.zone,
                address=traefik_service.status.load_balancer.ingress[0].ip,
                cloudflare_provider=cloudflare_provider,
                opts=p.ResourceOptions(parent=self),
            )

        p.export('teslalogger_url', f'https://{hostname}/admin/')
        p.export('grafana_url', f'https://{grafana_hostname}')
        self.register_outputs({})
