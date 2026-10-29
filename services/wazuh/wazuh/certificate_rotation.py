"""Restart Wazuh certificate consumers when cert-manager rotates leaf Secrets."""

import pulumi as p
import pulumi_kubernetes as k8s

from wazuh.config import ComponentConfig

_CERT_CONSUMERS = (
    ('wazuh-indexer', 'statefulset', 'wazuh-indexer'),
    ('wazuh-admin', 'statefulset', 'wazuh-indexer'),
    ('wazuh-manager', 'statefulset', 'wazuh-manager'),
    ('wazuh-filebeat', 'statefulset', 'wazuh-manager'),
    ('wazuh-dashboard', 'deployment', 'wazuh-dashboard'),
    ('wazuh-grafana-reader', 'deployment', 'wazuh-indexer-exporter'),
    ('wazuh-metrics-reader', 'deployment', 'wazuh-indexer-exporter'),
)


def create_certificate_rotation(
    config: ComponentConfig, provider: k8s.Provider, namespace: p.Input[str]
) -> None:
    """Install least-privilege daily certificate-hash reconciliation."""
    opts = p.ResourceOptions(provider=provider)
    account = k8s.core.v1.ServiceAccount(
        'wazuh-certificate-rotation',
        metadata={'name': 'wazuh-certificate-rotation', 'namespace': namespace},
        opts=opts,
    )
    role = k8s.rbac.v1.Role(
        'wazuh-certificate-rotation',
        metadata={'name': 'wazuh-certificate-rotation', 'namespace': namespace},
        rules=[
            {
                'api_groups': [''],
                'resources': ['secrets', 'pods'],
                'verbs': ['get'],
            },
            {
                'api_groups': ['apps'],
                'resources': ['statefulsets', 'deployments'],
                'verbs': ['get', 'patch'],
            },
        ],
        opts=opts,
    )
    k8s.rbac.v1.RoleBinding(
        'wazuh-certificate-rotation',
        metadata={'name': 'wazuh-certificate-rotation', 'namespace': namespace},
        role_ref={
            'api_group': 'rbac.authorization.k8s.io',
            'kind': 'Role',
            'name': role.metadata.name,
        },
        subjects=[
            {'kind': 'ServiceAccount', 'name': account.metadata.name, 'namespace': namespace}
        ],
        opts=p.ResourceOptions.merge(opts, p.ResourceOptions(depends_on=[account, role])),
    )
    script = r"""set -eu
annotation='cert-reconciler.wazuh.io/leaf-sha256'
reconcile() {
  kind=$1
  workload=$2
  shift 2
  combined=''
  for secret in "$@"; do
    leaf=$(kubectl -n "$NAMESPACE" get secret "$secret" -o jsonpath='{.data.tls\.crt}' | base64 -d | sha256sum | cut -d' ' -f1)
    combined="${combined}${secret}:${leaf}\n"
  done
  hash=$(printf '%b' "$combined" | sha256sum | cut -d' ' -f1)
  template_hash=$(kubectl -n "$NAMESPACE" get "$kind" "$workload" -o 'go-template={{with index .spec.template.metadata.annotations "cert-reconciler.wazuh.io/leaf-sha256"}}{{.}}{{end}}')
  baseline_hash=$(kubectl -n "$NAMESPACE" get "$kind" "$workload" -o 'go-template={{with index .metadata.annotations "cert-reconciler.wazuh.io/leaf-sha256"}}{{.}}{{end}}')
  current=${template_hash:-$baseline_hash}
  if [ -z "$current" ]; then
    # Metadata-only baseline avoids an initial pod-template change/restart.
    kubectl -n "$NAMESPACE" annotate "$kind" "$workload" "$annotation=$hash" --overwrite
  elif [ "$current" != "$hash" ]; then
    kubectl -n "$NAMESPACE" patch "$kind" "$workload" --type=merge -p "{\"metadata\":{\"annotations\":{\"$annotation\":\"$hash\"}},\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"$annotation\":\"$hash\"}}}}}"
    desired=$(kubectl -n "$NAMESPACE" get "$kind" "$workload" -o 'go-template={{.spec.replicas}}')
    attempt=0
    while [ "$attempt" -lt 120 ]; do
      live=$(kubectl -n "$NAMESPACE" get "$kind" "$workload" -o 'go-template={{.status.replicas}}')
      updated=$(kubectl -n "$NAMESPACE" get "$kind" "$workload" -o 'go-template={{.status.updatedReplicas}}')
      ready=$(kubectl -n "$NAMESPACE" get "$kind" "$workload" -o 'go-template={{.status.readyReplicas}}')
      if [ "$live" = "$desired" ] && [ "$updated" = "$desired" ] && [ "$ready" = "$desired" ]; then break; fi
      sleep 5
      attempt=$((attempt + 1))
    done
    [ "$live" = "$desired" ] && [ "$updated" = "$desired" ] && [ "$ready" = "$desired" ]
  fi
}
# Reconcile each owner once, preserving restart order and combining all its certs.
reconcile statefulset wazuh-indexer wazuh-indexer wazuh-admin
reconcile statefulset wazuh-manager wazuh-manager wazuh-filebeat
reconcile deployment wazuh-dashboard wazuh-dashboard
reconcile deployment wazuh-indexer-exporter wazuh-metrics-reader wazuh-grafana-reader
reconcile deployment wazuh-findings-exporter wazuh-metrics-reader
"""
    job = k8s.batch.v1.CronJob(
        'wazuh-certificate-rotation',
        metadata={'name': 'wazuh-certificate-rotation', 'namespace': namespace},
        spec={
            'schedule': '17 3 * * *',
            'concurrency_policy': 'Forbid',
            'successful_jobs_history_limit': 1,
            'failed_jobs_history_limit': 3,
            'job_template': {
                'spec': {
                    'backoff_limit': 2,
                    'template': {
                        'metadata': {
                            'labels': {'app.kubernetes.io/name': 'wazuh-certificate-rotation'}
                        },
                        'spec': {
                            'service_account_name': account.metadata.name,
                            'automount_service_account_token': True,
                            'restart_policy': 'OnFailure',
                            'security_context': {
                                'run_as_non_root': True,
                                'run_as_user': 1001,
                                'run_as_group': 1001,
                                'seccomp_profile': {'type': 'RuntimeDefault'},
                            },
                            'containers': [
                                {
                                    'name': 'rotate',
                                    'image': f'bitnamilegacy/kubectl:{config.kubectl_version}',
                                    'command': ['/bin/bash', '-c', script],
                                    'env': [{'name': 'NAMESPACE', 'value': namespace}],
                                    'resources': {
                                        'requests': {'cpu': '10m', 'memory': '32Mi'},
                                        'limits': {'memory': '128Mi'},
                                    },
                                    'security_context': {
                                        'allow_privilege_escalation': False,
                                        'read_only_root_filesystem': True,
                                        'capabilities': {'drop': ['ALL']},
                                    },
                                }
                            ],
                        },
                    },
                },
            },
        },
        opts=p.ResourceOptions.merge(opts, p.ResourceOptions(depends_on=[account, role])),
    )
    p.export('wazuh_certificate_rotation_cronjob', job.metadata.name)
