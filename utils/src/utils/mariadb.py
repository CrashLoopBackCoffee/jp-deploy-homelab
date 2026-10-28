import dataclasses

import pulumi as p
import pulumi_kubernetes as k8s

OPERATOR_NAMESPACE = 'mariadb-operator'
MARIADB_PORT = 3306


@dataclasses.dataclass(frozen=True)
class BackupTarget:
    """S3-compatible bucket receiving daily logical dumps; each database gets its own prefix."""

    # host:port without scheme
    endpoint: str
    bucket: str
    region: str
    access_key_id: p.Input[str]
    secret_access_key: p.Input[str]
    # Five-field cron expression in UTC.
    schedule: str = '0 21 * * *'
    max_retention: str = '336h'


@dataclasses.dataclass(frozen=True)
class MariaDbDatabase:
    mariadb: k8s.apiextensions.CustomResource
    database: k8s.apiextensions.CustomResource
    # Service name, equal to the MariaDB resource name.
    host: str
    port: int = MARIADB_PORT


def create_mariadb_database(
    name: str,
    *,
    database: str,
    character_set: str,
    collate: str,
    root_password: p.Input[str],
    image_version: str,
    storage_size: str,
    time_zone: str,
    backup_prefix: str,
    backup: BackupTarget,
    k8s_opts: p.ResourceOptions,
) -> MariaDbDatabase:
    """Create a single-instance MariaDB with a database, daily logical dumps and an access policy.

    Requires the mariadb-operator from the kubernetes stack, and `k8s_opts` must carry a provider
    scoped to the target namespace. The instance lives on the default StorageClass, so its volume
    also joins the nightly Longhorn backup. Only pods of the same namespace and the operator may
    connect.
    """
    root_secret = k8s.core.v1.Secret(
        f'{name}-root',
        metadata={'name': f'{name}-root'},
        string_data={'password': root_password},
        opts=k8s_opts,
    )
    backup_credentials = k8s.core.v1.Secret(
        f'{name}-backup-credentials',
        metadata={'name': f'{name}-backup-credentials'},
        string_data={
            'access-key-id': backup.access_key_id,
            'secret-access-key': backup.secret_access_key,
        },
        opts=k8s_opts,
    )

    mariadb = k8s.apiextensions.CustomResource(
        name,
        api_version='k8s.mariadb.com/v1alpha1',
        kind='MariaDB',
        # Applications depending on the database should not start before it is serving.
        metadata={'name': name, 'annotations': {'pulumi.com/waitFor': 'condition=Ready'}},
        spec={
            'image': f'mariadb:{image_version}',
            'rootPasswordSecretKeyRef': {
                'name': root_secret.metadata.name,
                'key': 'password',
                'generate': False,
            },
            'storage': {'size': storage_size},
            'timeZone': time_zone,
            'myCnf': '[mariadb]\nbind-address=*\ndefault_storage_engine=InnoDB\nmax_allowed_packet=256M\n',
            # Clients share the namespace and are admitted by the NetworkPolicy below; TLS would only
            # add negotiation differences between client libraries.
            'tls': {'enabled': False},
            'resources': {
                'requests': {'cpu': '50m', 'memory': '512Mi'},
                'limits': {'memory': '1Gi'},
            },
        },
        opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[root_secret])),
    )

    database_resource = k8s.apiextensions.CustomResource(
        f'{name}-database',
        api_version='k8s.mariadb.com/v1alpha1',
        kind='Database',
        metadata={'name': database, 'annotations': {'pulumi.com/waitFor': 'condition=Ready'}},
        spec={
            'mariaDbRef': {'name': name},
            'characterSet': character_set,
            'collate': collate,
            # Never drop data when the resource goes.
            'cleanupPolicy': 'Skip',
        },
        opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[mariadb])),
    )

    # Logical dumps restore across MariaDB major versions and the databases are small.
    k8s.apiextensions.CustomResource(
        f'{name}-mariadb-backup',
        api_version='k8s.mariadb.com/v1alpha1',
        kind='Backup',
        metadata={'name': f'{name}-mariadb-backup'},
        spec={
            'mariaDbRef': {'name': name},
            # Without a list the operator dumps every database, including the `mysql` system schema.
            'databases': [database],
            'schedule': {'cron': backup.schedule},
            'timeZone': 'UTC',
            'maxRetention': backup.max_retention,
            'compression': 'gzip',
            'storage': {
                's3': {
                    'bucket': backup.bucket,
                    'endpoint': backup.endpoint,
                    'region': backup.region,
                    'prefix': backup_prefix,
                    'accessKeyIdSecretKeyRef': {
                        'name': backup_credentials.metadata.name,
                        'key': 'access-key-id',
                    },
                    'secretAccessKeySecretKeyRef': {
                        'name': backup_credentials.metadata.name,
                        'key': 'secret-access-key',
                    },
                    'tls': {'enabled': True},
                },
            },
        },
        opts=p.ResourceOptions.merge(
            k8s_opts, p.ResourceOptions(depends_on=[mariadb, backup_credentials])
        ),
    )

    k8s.networking.v1.NetworkPolicy(
        f'{name}-access',
        metadata={'name': f'{name}-access'},
        spec={
            'pod_selector': {
                'match_labels': {
                    'app.kubernetes.io/name': 'mariadb',
                    'app.kubernetes.io/instance': name,
                },
            },
            'policy_types': ['Ingress'],
            'ingress': [
                {
                    'from_': [
                        {'pod_selector': {}},
                        # The operator runs SQL against the instance.
                        {
                            'namespace_selector': {
                                'match_labels': {'kubernetes.io/metadata.name': OPERATOR_NAMESPACE},
                            },
                        },
                    ],
                    'ports': [{'port': MARIADB_PORT, 'protocol': 'TCP'}],
                },
            ],
        },
        opts=k8s_opts,
    )

    return MariaDbDatabase(mariadb=mariadb, database=database_resource, host=name)
