import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_random as random
import utils.cnpg

from tandoor.config import ComponentConfig

# The Tandoor 2 image runs nginx (static and media files) in front of gunicorn.
TANDOOR_PORT = 80
DATABASE_NAME = 'tandoor'
DATABASE_USER = 'tandoor'
STATIC_PATH = '/opt/recipes/staticfiles'
MEDIA_PATH = '/opt/recipes/mediafiles'
IMAGE = 'vabene1111/recipes'

MIGRATE_SCRIPT = """\
set -e
. venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
"""


class Tandoor(p.ComponentResource):
    def __init__(
        self,
        component_config: ComponentConfig,
        namespace: p.Input[str],
        k8s_provider: k8s.Provider,
    ):
        super().__init__('tandoor', 'tandoor')
        tandoor_config = component_config.tandoor
        hostname = f'{tandoor_config.host}.{component_config.zone}'

        namespaced_provider = k8s.Provider(
            'tandoor-provider',
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

        config_secret = k8s.core.v1.Secret(
            'tandoor-config',
            string_data={
                'SECRET_KEY': random.RandomPassword(
                    'tandoor-secret-key', length=64, special=False
                ).result,
            },
            opts=k8s_opts,
        )

        media_claim = k8s.core.v1.PersistentVolumeClaim(
            'mediafiles',
            metadata={'name': 'mediafiles'},
            spec={
                'access_modes': ['ReadWriteOnce'],
                'resources': {'requests': {'storage': tandoor_config.media_size}},
            },
            opts=k8s_opts,
        )

        # Application wiring wins over the free-form preferences from the stack config.
        plain_env = {
            **tandoor_config.settings,
            'DB_ENGINE': 'django.db.backends.postgresql',
            'POSTGRES_HOST': database.host,
            'POSTGRES_PORT': str(database.port),
            'POSTGRES_DB': DATABASE_NAME,
            'POSTGRES_USER': DATABASE_USER,
            'ALLOWED_HOSTS': hostname,
            'TIMEZONE': 'Europe/Berlin',
            'TANDOOR_PORT': str(TANDOOR_PORT),
            # nginx in the image serves the media files
            'GUNICORN_MEDIA': '0',
        }
        env: list[k8s.core.v1.EnvVarArgsDict] = [
            *[{'name': k, 'value': v} for k, v in plain_env.items()],
            {
                'name': 'POSTGRES_PASSWORD',
                'value_from': {
                    'secret_key_ref': {'name': database.app_secret_name, 'key': 'password'}
                },
            },
        ]
        env_from: list[k8s.core.v1.EnvFromSourceArgsDict] = [
            {'secret_ref': {'name': config_secret.metadata.name}}
        ]
        volume_mounts: list[k8s.core.v1.VolumeMountArgsDict] = [
            {'name': 'staticfiles', 'mount_path': STATIC_PATH},
            {'name': 'mediafiles', 'mount_path': MEDIA_PATH},
        ]
        image = f'{IMAGE}:{tandoor_config.version}'

        app_labels = {'app': 'tandoor'}
        deployment = k8s.apps.v1.Deployment(
            'tandoor',
            metadata={'name': 'tandoor'},
            spec={
                'replicas': 1,
                'selector': {'match_labels': app_labels},
                # The media volume is ReadWriteOnce.
                'strategy': {'type': 'Recreate'},
                'template': {
                    'metadata': {'labels': app_labels},
                    'spec': {
                        # `TANDOOR_PORT` would otherwise be injected by the Service named `tandoor`
                        'enable_service_links': False,
                        'security_context': {'fs_group': 65534},
                        'init_containers': [
                            {
                                'name': 'migrate',
                                'image': image,
                                'command': ['sh', '-c', MIGRATE_SCRIPT],
                                'env': env,
                                'env_from': env_from,
                                'volume_mounts': volume_mounts,
                            },
                        ],
                        'containers': [
                            {
                                'name': 'tandoor',
                                'image': image,
                                'ports': [{'name': 'http', 'container_port': TANDOOR_PORT}],
                                'env': env,
                                'env_from': env_from,
                                'volume_mounts': volume_mounts,
                                'readiness_probe': {'tcp_socket': {'port': TANDOOR_PORT}},
                                'resources': {
                                    'requests': {'cpu': '50m', 'memory': '256Mi'},
                                    'limits': {'memory': '1Gi'},
                                },
                            },
                        ],
                        'volumes': [
                            # Rebuilt by `collectstatic` on every start
                            {'name': 'staticfiles', 'empty_dir': {}},
                            {
                                'name': 'mediafiles',
                                'persistent_volume_claim': {
                                    'claim_name': media_claim.metadata.name
                                },
                            },
                        ],
                    },
                },
            },
            opts=p.ResourceOptions.merge(
                k8s_opts, p.ResourceOptions(depends_on=[database.cluster])
            ),
        )

        service = k8s.core.v1.Service(
            'tandoor',
            metadata={'name': 'tandoor'},
            spec={
                'ports': [{'port': TANDOOR_PORT}],
                'selector': deployment.spec.selector.match_labels,
            },
            opts=k8s_opts,
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
                        'match': f'Host(`{hostname}`)',
                        'services': [
                            {
                                'name': service.metadata.name,
                                'namespace': service.metadata.namespace,
                                'port': TANDOOR_PORT,
                            },
                        ],
                    }
                ],
                # use default wildcard certificate:
                'tls': {},
            },
            opts=k8s_opts,
        )

        p.export('tandoor_url', f'https://{hostname}')
        self.register_outputs({})
