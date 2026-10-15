"""Paperless backup orchestration using CronJob."""

import textwrap

import pulumi as p
import pulumi_kubernetes as k8s

from .config import ComponentConfig

BACKUP_SCRIPT = textwrap.dedent(
    """\
    #!/bin/sh
    set -eu

    # Log with timestamp
    log() {{
        echo "$(date '+%Y-%m-%d %H:%M:%S') $1"
    }}

    log "Starting Paperless backup process..."

    KUBECTL="/usr/local/bin/kubectl"

    log "Using kubectl version: $($KUBECTL version --client --short 2>/dev/null || $KUBECTL version --client)"

    # Step 1: Export documents from Paperless
    log "Step 1: Exporting documents from Paperless..."
    $KUBECTL exec paperless-0 -c paperless -- document_exporter \\
        /usr/src/paperless/export \\
        --split-manifest \\
        --no-progress-bar \\
        --use-folder-prefix \\
        --no-archive \\
        --no-thumbnail \\
        --delete

    log "Document export completed."

    RESTIC="$KUBECTL exec paperless-0 -c restic -- restic"

    # Initialize only a missing repository; reject other access errors and clean stale locks.
    log "Step 2: Ensuring the Nextcloud repository is initialized..."
    rc=0
    $RESTIC cat config --no-lock >/dev/null || rc=$?
    if [ "$rc" -eq 10 ]; then
        log "Repository not initialized; initializing..."
        $RESTIC init
        log "Repository initialized."
    elif [ "$rc" -ne 0 ]; then
        log "Failed to access the repository (restic exit code $rc)"
        exit 1
    fi
    log "Removing stale locks..."
    $RESTIC unlock

    # Step 3: Back up the export to the off-site Nextcloud repository
    log "Step 3: Running restic backup..."
    $RESTIC backup /usr/src/paperless/export \\
        --tag paperless \\
        --tag "$(date +%Y-%m-%d)"
    log "Restic backup completed."

    # Step 4: Retention
    log "Step 4: Running restic maintenance..."
    $RESTIC forget \\
        --keep-daily {retention_daily} \\
        --keep-weekly {retention_weekly} \\
        --keep-monthly {retention_monthly} \\
        --prune
    log "Maintenance completed."

    # Step 5: Verify repository structure so a damaged off-site copy fails the job
    log "Step 5: Checking repository..."
    $RESTIC check

    log "Backup process completed successfully."
    """
)


def create_backup_cronjob(
    component_config: ComponentConfig, k8s_opts: p.ResourceOptions
) -> k8s.batch.v1.CronJob:
    """Create a CronJob that orchestrates the Paperless backup process."""

    # ServiceAccount for kubectl operations
    backup_service_account = k8s.core.v1.ServiceAccount(
        'paperless-backup',
        metadata={'name': 'paperless-backup'},
        opts=k8s_opts,
    )

    # Role for kubectl exec permissions
    backup_role = k8s.rbac.v1.Role(
        'paperless-backup',
        metadata={'name': 'paperless-backup'},
        rules=[
            {
                'api_groups': [''],
                'resources': ['pods'],
                'verbs': ['get', 'list'],
            },
            {
                'api_groups': [''],
                'resources': ['pods/exec'],
                'verbs': ['create'],
            },
        ],
        opts=k8s_opts,
    )

    # RoleBinding
    k8s.rbac.v1.RoleBinding(
        'paperless-backup',
        metadata={'name': 'paperless-backup'},
        role_ref={
            'api_group': 'rbac.authorization.k8s.io',
            'kind': 'Role',
            'name': backup_role.metadata.name,
        },
        subjects=[
            {
                'kind': 'ServiceAccount',
                'name': backup_service_account.metadata.name,
                'namespace': backup_service_account.metadata.namespace,
            }
        ],
        opts=k8s_opts,
    )

    # ConfigMap with backup script
    backup_script = k8s.core.v1.ConfigMap(
        'paperless-backup-script',
        metadata={'name': 'paperless-backup-script'},
        data={
            'backup.sh': BACKUP_SCRIPT.format(
                retention_daily=component_config.backup.retention_daily,
                retention_weekly=component_config.backup.retention_weekly,
                retention_monthly=component_config.backup.retention_monthly,
            )
        },
        opts=k8s_opts,
    )

    # CronJob for backup orchestration
    return k8s.batch.v1.CronJob(
        'paperless-backup',
        metadata={'name': 'paperless-backup'},
        spec={
            'schedule': component_config.backup.schedule,
            'job_template': {
                'spec': {
                    'template': {
                        'spec': {
                            'service_account_name': backup_service_account.metadata.name,
                            'restart_policy': 'OnFailure',
                            'containers': [
                                {
                                    'name': 'backup-orchestrator',
                                    'image': f'registry.k8s.io/conformance:v{component_config.backup.kubectl_version}',
                                    'command': ['/bin/sh'],
                                    'args': ['/scripts/backup.sh'],
                                    'volume_mounts': [
                                        {
                                            'name': 'backup-script',
                                            'mount_path': '/scripts',
                                            'read_only': True,
                                        },
                                    ],
                                }
                            ],
                            'volumes': [
                                {
                                    'name': 'backup-script',
                                    'config_map': {
                                        'name': backup_script.metadata.name,
                                        'default_mode': 0o755,
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
