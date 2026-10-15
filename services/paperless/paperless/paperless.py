import json
import textwrap

import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_random as random
import utils.cnpg
import utils.opnsense.dnsmasq.host

from paperless.backup import create_backup_cronjob
from paperless.config import ComponentConfig

REDIS_PORT = 6379
PAPERLESS_PORT = 8000
TIKA_PORT = 9998
GOTENBERG_PORT = 3000
DATABASE_NAME = 'paperless'
DATABASE_USER = 'paperless'
RCLONE_CONFIG_DIR = '/rclone-config'
RESTORE_PATH = '/restore'

# rclone only accepts an obscured WebDAV password, so the config is written at pod start using the
# rclone binary of the restic image. The Nextcloud values come from the backup Secret.
RCLONE_CONFIG_SCRIPT = textwrap.dedent(
    f"""\
    set -eu
    mkdir -p {RCLONE_CONFIG_DIR}
    umask 077
    cat > {RCLONE_CONFIG_DIR}/rclone.conf <<EOF
    [nextcloud]
    type = webdav
    url = ${{NEXTCLOUD_URL%/}}/remote.php/dav/files/${{NEXTCLOUD_USER}}/
    vendor = nextcloud
    user = ${{NEXTCLOUD_USER}}
    pass = $(rclone obscure "$NEXTCLOUD_PASSWORD")
    EOF
    """
)


class Paperless(p.ComponentResource):
    def __init__(
        self,
        component_config: ComponentConfig,
        namespace: p.Input[str],
        k8s_provider: k8s.Provider,
    ):
        super().__init__('paperless', 'paperless')
        paperless_config = component_config.paperless
        backup_config = component_config.backup
        hostname = f'{paperless_config.host}.{component_config.zone}'

        admin_username = 'admin'
        admin_password = random.RandomPassword('admin-password', length=32, special=False).result
        p.export('admin_username', admin_username)
        p.export('admin_password', p.Output.secret(admin_password))
        namespaced_provider = k8s.Provider(
            'paperless-provider',
            kubeconfig=k8s_provider.kubeconfig,  # type: ignore
            namespace=namespace,
        )
        k8s_opts = p.ResourceOptions(
            parent=self,
            provider=namespaced_provider,
        )

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
        redis_service = create_redis(component_config, k8s_opts)
        tika_service = create_tika(component_config, k8s_opts)
        gotenberg_service = create_gotenberg(component_config, k8s_opts)

        env_vars = {
            'PAPERLESS_REDIS': p.Output.format(
                'redis://{}:{}',
                redis_service.metadata.name,
                REDIS_PORT,
            ),
            'PAPERLESS_CONSUMER_POLLING': '30',
            'PAPERLESS_TASK_WORKERS': '4',
            'PAPERLESS_THREADS_PER_WORKER': '4',
            # Extend the polling delay to account for printers updating their PDFs after scanning
            # each page.
            'PAPERLESS_CONSUMER_POLLING_DELAY': '30',
            # Wait up to 10min for the scan to finish
            'PAPERLESS_CONSUMER_POLLING_RETRY_COUNT': '20',
            'PAPERLESS_URL': f'https://{hostname}',
            # https://docs.paperless-ngx.com/troubleshooting/#gunicorn-fails-to-start-with-is-not-a-valid-port-number
            'PAPERLESS_PORT': str(PAPERLESS_PORT),
            'PAPERLESS_ADMIN_USER': admin_username,
            'PAPERLESS_OCR_LANGUAGE': paperless_config.ocr_language,
            'PAPERLESS_TIME_ZONE': 'Europe/Berlin',
            'PAPERLESS_DBENGINE': 'postgresql',
            'PAPERLESS_DBHOST': database.host,
            'PAPERLESS_DBPORT': str(database.port),
            'PAPERLESS_DBNAME': DATABASE_NAME,
            'PAPERLESS_DBUSER': DATABASE_USER,
            'PAPERLESS_CONSUMER_ENABLE_BARCODES': 'true',
            'PAPERLESS_CONSUMER_ENABLE_ASN_BARCODE': 'true',
            'PAPERLESS_CONSUMER_BARCODE_SCANNER': 'ZXING',
            'PAPERLESS_CONSUMER_RECURSIVE': 'true',
            'PAPERLESS_CONSUMER_IGNORE_PATTERNS': json.dumps(
                [
                    '._*',
                    '.DS_Store',
                    '.DS_STORE',
                    '.localized/*',
                    '.stfolder/*',
                    '.stversions/*',
                    '@eaDir/*',
                    '#recycle/*',
                    # QNAP keeps deleted and snapshot files in these folders of the share
                    '@Recycle/*',
                    '@Recently-Snapshot/*',
                    '.@__thumb/*',
                    'desktop.ini',
                    'Thumbs.db',
                ]
            ),
            'PAPERLESS_TIKA_ENABLED': 'true',
            'PAPERLESS_TIKA_ENDPOINT': p.Output.format(
                'http://{}:{}', tika_service.metadata.name, TIKA_PORT
            ),
            'PAPERLESS_TIKA_GOTENBERG_ENDPOINT': p.Output.format(
                'http://{}:{}', gotenberg_service.metadata.name, GOTENBERG_PORT
            ),
            'PAPERLESS_WEBSERVER_WORKERS': '4',
        }

        config_secret = k8s.core.v1.Secret(
            'paperless-config',
            string_data={
                'PAPERLESS_SECRET_KEY': random.RandomPassword(
                    'paperless-secret-key', length=64, special=False
                ).result,
                'PAPERLESS_ADMIN_PASSWORD': admin_password,
            },
            opts=k8s_opts,
        )

        backup_secret = k8s.core.v1.Secret(
            'paperless-backup-secrets',
            string_data={
                'restic-password': backup_config.restic_password.value,
                'NEXTCLOUD_URL': backup_config.nextcloud.url.value,
                'NEXTCLOUD_USER': backup_config.nextcloud.username.value,
                'NEXTCLOUD_PASSWORD': backup_config.nextcloud.password.value,
            },
            opts=k8s_opts,
        )

        restic_image = (
            f'ghcr.io/crashloopbackcoffee/restic-rclone:{backup_config.restic_rclone_version}'
        )
        app_labels = {'app': 'paperless'}
        sts = k8s.apps.v1.StatefulSet(
            'paperless',
            metadata={'name': 'paperless'},
            spec={
                'replicas': 1,
                'selector': {'match_labels': app_labels},
                'service_name': 'paperless-headless',
                'template': {
                    'metadata': {'labels': app_labels},
                    'spec': {
                        'init_containers': [
                            {
                                'name': 'setup-rclone-config',
                                'image': restic_image,
                                'command': ['/bin/sh', '-c', RCLONE_CONFIG_SCRIPT],
                                'env_from': [{'secret_ref': {'name': backup_secret.metadata.name}}],
                                'volume_mounts': [
                                    {'name': 'rclone-config', 'mount_path': RCLONE_CONFIG_DIR},
                                ],
                            },
                        ],
                        'containers': [
                            {
                                'name': 'paperless',
                                'image': f'ghcr.io/paperless-ngx/paperless-ngx:{paperless_config.version}',
                                'env': [
                                    *[{'name': k, 'value': v} for k, v in env_vars.items()],
                                    {
                                        'name': 'PAPERLESS_DBPASS',
                                        'value_from': {
                                            'secret_key_ref': {
                                                'name': database.app_secret_name,
                                                'key': 'password',
                                            },
                                        },
                                    },
                                ],
                                'env_from': [
                                    {
                                        'secret_ref': {
                                            'name': config_secret.metadata.name,
                                        },
                                    },
                                ],
                                'ports': [{'container_port': PAPERLESS_PORT}],
                                'volume_mounts': [
                                    {
                                        'name': 'data',
                                        'mount_path': '/usr/src/paperless/data',
                                    },
                                    {
                                        'name': 'media',
                                        'mount_path': '/usr/src/paperless/media',
                                    },
                                    {
                                        'name': 'consume',
                                        'mount_path': '/usr/src/paperless/consume',
                                    },
                                    {
                                        'name': 'export',
                                        'mount_path': '/usr/src/paperless/export',
                                    },
                                    {'name': 'restore', 'mount_path': RESTORE_PATH},
                                ],
                            },
                            {
                                'name': 'restic',
                                'image': restic_image,
                                'command': ['/bin/sh'],
                                'args': ['-c', 'sleep infinity'],
                                'env': [
                                    {
                                        'name': 'RESTIC_REPOSITORY',
                                        'value': f'rclone:nextcloud:{backup_config.repository_path}',
                                    },
                                    {
                                        'name': 'RESTIC_PASSWORD',
                                        'value_from': {
                                            'secret_key_ref': {
                                                'name': backup_secret.metadata.name,
                                                'key': 'restic-password',
                                            }
                                        },
                                    },
                                    {
                                        'name': 'RCLONE_CONFIG',
                                        'value': f'{RCLONE_CONFIG_DIR}/rclone.conf',
                                    },
                                    {'name': 'RESTIC_PROGRESS_FPS', 'value': '0'},
                                ],
                                'volume_mounts': [
                                    {
                                        'name': 'export',
                                        'mount_path': '/usr/src/paperless/export',
                                        'read_only': True,
                                    },
                                    {
                                        'name': 'rclone-config',
                                        'mount_path': RCLONE_CONFIG_DIR,
                                        'read_only': True,
                                    },
                                    {'name': 'restore', 'mount_path': RESTORE_PATH},
                                ],
                            },
                        ],
                        'volumes': [
                            {
                                'name': 'consume',
                                'csi': {
                                    'driver': 'nfs.csi.k8s.io',
                                    'volume_attributes': {
                                        'server': paperless_config.consume.server,
                                        'share': paperless_config.consume.share,
                                        'mount_options': paperless_config.consume.mount_options,
                                    },
                                },
                            },
                            {'name': 'rclone-config', 'empty_dir': {}},
                            # Scratch space shared by the restic and paperless containers for restores
                            {
                                'name': 'restore',
                                'empty_dir': {'size_limit': paperless_config.storage.export_size},
                            },
                        ],
                        'security_context': {
                            'fs_group': 1000,
                        },
                    },
                },
                'volume_claim_templates': [
                    {
                        'metadata': {'name': name},
                        'spec': {
                            'access_modes': ['ReadWriteOnce'],
                            'resources': {'requests': {'storage': size}},
                        },
                    }
                    for name, size in (
                        ('data', paperless_config.storage.data_size),
                        ('media', paperless_config.storage.media_size),
                        ('export', paperless_config.storage.export_size),
                    )
                ],
            },
            opts=p.ResourceOptions.merge(
                k8s_opts, p.ResourceOptions(depends_on=[database.cluster])
            ),
        )

        service_paperless = k8s.core.v1.Service(
            'paperless',
            metadata={'name': 'paperless'},
            spec={
                'ports': [{'port': PAPERLESS_PORT}],
                'selector': sts.spec.selector.match_labels,
            },
            opts=k8s_opts,
        )

        # Create local DNS record
        traefik_service = k8s.core.v1.Service.get(
            'traefik-service', 'traefik/traefik', opts=k8s_opts
        )
        utils.opnsense.dnsmasq.host.Host(
            'paperless',
            host=paperless_config.host,
            domain=component_config.zone,
            ipaddress=traefik_service.status.load_balancer.ingress[0].ip,
        )

        k8s.apiextensions.CustomResource(
            'ingress',
            api_version='traefik.io/v1alpha1',
            kind='IngressRoute',
            metadata={
                'name': 'ingress',
            },
            spec={
                'entryPoints': ['websecure'],
                'routes': [
                    {
                        'kind': 'Rule',
                        'match': f'Host(`{hostname}`)',
                        'services': [
                            {
                                'name': service_paperless.metadata.name,
                                'namespace': service_paperless.metadata.namespace,
                                'port': PAPERLESS_PORT,
                            },
                        ],
                    }
                ],
                # use default wildcard certificate:
                'tls': {},
            },
            opts=k8s_opts,
        )

        p.export('paperless_url', f'https://{hostname}')

        # Create backup CronJob
        create_backup_cronjob(component_config, k8s_opts)

        self.register_outputs({})


def create_redis(component_config: ComponentConfig, opts: p.ResourceOptions) -> k8s.core.v1.Service:
    app_labels_redis = {'app': 'redis'}
    redis_sts = k8s.apps.v1.StatefulSet(
        'redis',
        metadata={'name': 'redis'},
        spec={
            'replicas': 1,
            'selector': {'match_labels': app_labels_redis},
            'service_name': 'redis-headless',
            'template': {
                'metadata': {'labels': app_labels_redis},
                'spec': {
                    'containers': [
                        {
                            'name': 'redis',
                            'image': f'docker.io/library/redis:{component_config.redis.version}',
                            'ports': [{'container_port': REDIS_PORT}],
                        },
                    ],
                },
            },
        },
        opts=opts,
    )
    return k8s.core.v1.Service(
        'redis',
        metadata={'name': 'redis'},
        spec={
            'ports': [{'port': REDIS_PORT}],
            'selector': redis_sts.spec.selector.match_labels,
        },
        opts=opts,
    )


def create_tika(component_config: ComponentConfig, opts: p.ResourceOptions) -> k8s.core.v1.Service:
    app_labels_tika = {'app': 'tika'}
    tika_sts = k8s.apps.v1.Deployment(
        'tika',
        metadata={'name': 'tika'},
        spec={
            'replicas': 1,
            'selector': {'match_labels': app_labels_tika},
            'template': {
                'metadata': {'labels': app_labels_tika},
                'spec': {
                    'containers': [
                        {
                            'name': 'tika',
                            'image': f'docker.io/apache/tika:{component_config.tika.version}',
                            'ports': [{'container_port': TIKA_PORT}],
                        },
                    ],
                },
            },
        },
        opts=opts,
    )
    return k8s.core.v1.Service(
        'tika',
        metadata={'name': 'tika'},
        spec={
            'ports': [{'port': TIKA_PORT}],
            'selector': tika_sts.spec.selector.match_labels,
        },
        opts=opts,
    )


def create_gotenberg(
    component_config: ComponentConfig, opts: p.ResourceOptions
) -> k8s.core.v1.Service:
    app_labels_gotenberg = {'app': 'gotenberg'}
    gotenberg_sts = k8s.apps.v1.Deployment(
        'gotenberg',
        metadata={'name': 'gotenberg'},
        spec={
            'replicas': 1,
            'selector': {'match_labels': app_labels_gotenberg},
            'template': {
                'metadata': {'labels': app_labels_gotenberg},
                'spec': {
                    'containers': [
                        {
                            'name': 'gotenberg',
                            'image': f'docker.io/gotenberg/gotenberg:{component_config.gotenberg.version}',
                            # The gotenberg chromium route is used to convert .eml files. We do not
                            # want to allow external content like tracking pixels or even javascript.
                            'command': [
                                'gotenberg',
                                '--chromium-disable-javascript=true',
                                '--chromium-allow-list=file:///tmp/.*',
                            ],
                            'ports': [{'container_port': GOTENBERG_PORT}],
                        },
                    ],
                },
            },
        },
        opts=opts,
    )
    return k8s.core.v1.Service(
        'gotenberg',
        metadata={'name': 'gotenberg'},
        spec={
            'ports': [{'port': GOTENBERG_PORT}],
            'selector': gotenberg_sts.spec.selector.match_labels,
        },
        opts=opts,
    )
