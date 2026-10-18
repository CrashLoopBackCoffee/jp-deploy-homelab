"""Off-site backup of Tandoor: a database dump and the media files, encrypted by restic."""

import textwrap

import pulumi as p
import pulumi_kubernetes as k8s

from tandoor.config import ComponentConfig

RCLONE_CONFIG_DIR = '/rclone-config'
DUMP_DIR = '/dump'
MEDIA_DIR = '/media'
DUMP_FILE = f'{DUMP_DIR}/tandoor.dump'

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


def _secret_env(name: str, secret_name: p.Input[str], key: str) -> k8s.core.v1.EnvVarArgsDict:
    return {
        'name': name,
        'value_from': {'secret_key_ref': {'name': secret_name, 'key': key}},
    }


def create_backup_cronjob(
    component_config: ComponentConfig,
    *,
    database_host: str,
    database_name: str,
    database_user: str,
    database_secret_name: str,
    media_claim_name: p.Input[str],
    k8s_opts: p.ResourceOptions,
) -> k8s.batch.v1.CronJob:
    """Create the CronJob that dumps the database and backs it up with the media files.

    The Job runs on the node of the application Pod because the media volume is ReadWriteOnce.
    """
    backup_config = component_config.backup
    database_config = component_config.database
    restic_image = (
        f'ghcr.io/crashloopbackcoffee/restic-rclone:{backup_config.restic_rclone_version}'
    )

    backup_secret = k8s.core.v1.Secret(
        'tandoor-backup-secrets',
        string_data={
            'restic-password': backup_config.restic_password.value,
            'NEXTCLOUD_URL': backup_config.nextcloud.url.value,
            'NEXTCLOUD_USER': backup_config.nextcloud.username.value,
            'NEXTCLOUD_PASSWORD': backup_config.nextcloud.password.value,
        },
        opts=k8s_opts,
    )

    backup_script = textwrap.dedent(
        f"""\
        set -eu
        # The first run creates the repository.
        restic snapshots >/dev/null 2>&1 || restic init
        restic backup --tag tandoor {DUMP_DIR} {MEDIA_DIR}
        restic forget --tag tandoor --prune \\
            --keep-daily {backup_config.retention_daily} \\
            --keep-weekly {backup_config.retention_weekly} \\
            --keep-monthly {backup_config.retention_monthly}
        restic check
        """
    )

    return k8s.batch.v1.CronJob(
        'tandoor-backup',
        metadata={'name': 'tandoor-backup'},
        spec={
            'schedule': backup_config.schedule,
            'concurrency_policy': 'Forbid',
            'successful_jobs_history_limit': 3,
            'failed_jobs_history_limit': 3,
            'job_template': {
                'spec': {
                    'backoff_limit': 1,
                    'active_deadline_seconds': 3600,
                    'template': {
                        'spec': {
                            'restart_policy': 'Never',
                            'affinity': {
                                'pod_affinity': {
                                    'required_during_scheduling_ignored_during_execution': [
                                        {
                                            'topology_key': 'kubernetes.io/hostname',
                                            'label_selector': {'match_labels': {'app': 'tandoor'}},
                                        }
                                    ]
                                }
                            },
                            'init_containers': [
                                {
                                    'name': 'setup-rclone-config',
                                    'image': restic_image,
                                    'command': ['/bin/sh', '-c', RCLONE_CONFIG_SCRIPT],
                                    'env_from': [
                                        {'secret_ref': {'name': backup_secret.metadata.name}}
                                    ],
                                    'volume_mounts': [
                                        {'name': 'rclone-config', 'mount_path': RCLONE_CONFIG_DIR},
                                    ],
                                },
                                {
                                    'name': 'dump-database',
                                    'image': (
                                        f'ghcr.io/cloudnative-pg/postgresql:'
                                        f'{database_config.image_version}'
                                    ),
                                    'command': ['pg_dump', '--format=custom', '--file', DUMP_FILE],
                                    'env': [
                                        {'name': 'PGHOST', 'value': database_host},
                                        {'name': 'PGDATABASE', 'value': database_name},
                                        {'name': 'PGUSER', 'value': database_user},
                                        _secret_env('PGPASSWORD', database_secret_name, 'password'),
                                    ],
                                    'volume_mounts': [{'name': 'dump', 'mount_path': DUMP_DIR}],
                                },
                            ],
                            'containers': [
                                {
                                    'name': 'restic',
                                    'image': restic_image,
                                    'command': ['/bin/sh', '-c', backup_script],
                                    'env': [
                                        {
                                            'name': 'RESTIC_REPOSITORY',
                                            'value': f'rclone:nextcloud:{backup_config.repository_path}',
                                        },
                                        _secret_env(
                                            'RESTIC_PASSWORD',
                                            backup_secret.metadata.name,
                                            'restic-password',
                                        ),
                                        {
                                            'name': 'RCLONE_CONFIG',
                                            'value': f'{RCLONE_CONFIG_DIR}/rclone.conf',
                                        },
                                        {'name': 'RESTIC_PROGRESS_FPS', 'value': '0'},
                                    ],
                                    'volume_mounts': [
                                        {'name': 'dump', 'mount_path': DUMP_DIR, 'read_only': True},
                                        {
                                            'name': 'media',
                                            'mount_path': MEDIA_DIR,
                                            'read_only': True,
                                        },
                                        {
                                            'name': 'rclone-config',
                                            'mount_path': RCLONE_CONFIG_DIR,
                                            'read_only': True,
                                        },
                                    ],
                                }
                            ],
                            'volumes': [
                                {'name': 'rclone-config', 'empty_dir': {}},
                                {'name': 'dump', 'empty_dir': {}},
                                {
                                    'name': 'media',
                                    'persistent_volume_claim': {
                                        'claim_name': media_claim_name,
                                        'read_only': True,
                                    },
                                },
                            ],
                        },
                    },
                },
            },
        },
        opts=k8s_opts,
    )
