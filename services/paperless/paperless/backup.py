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

    SECONDARY_FAILED=0

    # Initialize only missing repositories; reject other access errors and clean stale locks.
    ensure_repo() {{
        container="$1"
        rc=0
        $KUBECTL exec paperless-0 -c "$container" -- restic cat config --no-lock >/dev/null || rc=$?
        if [ "$rc" -eq 10 ]; then
            log "Repository of $container not initialized; initializing..."
            $KUBECTL exec paperless-0 -c "$container" -- restic init || return $?
            log "Repository of $container initialized."
        elif [ "$rc" -ne 0 ]; then
            log "Failed to access repository of $container (restic exit code $rc)"
            return "$rc"
        fi
        log "Removing stale locks in repository of $container..."
        $KUBECTL exec paperless-0 -c "$container" -- restic unlock
    }}

    log "Step 1.5: Ensuring repositories are initialized..."
    ensure_repo restic || {{ log "Primary repository not usable"; exit 1; }}

    if $KUBECTL get pod paperless-0 -o jsonpath='{{.spec.containers[*].name}}' | grep -q 'restic-idrive'; then
        if ! ensure_repo restic-idrive; then
            log "Secondary IDrive repository not usable; continuing with primary backup"
            SECONDARY_FAILED=1
        fi
    fi

    # Step 2: Run restic backup (primary Google Drive)
    log "Step 2: Running primary restic backup (gdrive)..."
    $KUBECTL exec paperless-0 -c restic -- restic backup /usr/src/paperless/export \\
        --tag paperless \\
        --tag "$(date +%Y-%m-%d)"
    log "Primary restic backup completed."

    # Optional secondary backup to IDrive E2 if sidecar exists
    if $KUBECTL get pod paperless-0 -o jsonpath='{{.spec.containers[*].name}}' | grep -q 'restic-idrive'; then
        log "Secondary restic sidecar detected; running IDrive E2 backup..."
        if $KUBECTL exec paperless-0 -c restic-idrive -- restic backup /usr/src/paperless/export \\
            --tag paperless \\
            --tag "$(date +%Y-%m-%d)"; then
            log "Secondary restic backup (IDrive) completed."
        else
            log "IDrive backup failed"
            SECONDARY_FAILED=1
        fi
    else
        log "Secondary restic sidecar not present; skipping IDrive backup."
    fi

    # Step 3: Restic maintenance primary
    log "Step 3: Running restic maintenance (primary)..."
    $KUBECTL exec paperless-0 -c restic -- restic forget \\
        --keep-daily {retention_daily} \\
        --keep-weekly {retention_weekly} \\
        --keep-monthly {retention_monthly} \\
        --prune
    log "Primary maintenance completed."

    # Step 4: Restic maintenance secondary (if present)
    if $KUBECTL get pod paperless-0 -o jsonpath='{{.spec.containers[*].name}}' | grep -q 'restic-idrive'; then
        log "Running restic maintenance (IDrive)..."
        if $KUBECTL exec paperless-0 -c restic-idrive -- restic forget \\
            --keep-daily {retention_daily} \\
            --keep-weekly {retention_weekly} \\
            --keep-monthly {retention_monthly} \\
            --prune; then
            log "Secondary maintenance completed."
        else
            log "IDrive maintenance failed"
            SECONDARY_FAILED=1
        fi
    fi

    if [ "$SECONDARY_FAILED" -ne 0 ]; then
        log "Backup process completed with secondary backup errors."
        exit 1
    fi

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
