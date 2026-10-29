import base64
import hashlib
import json

import pulumi as p
import pulumi_kubernetes as k8s

from wazuh.config import ComponentConfig

_INDEXER_CONFIG = """cluster.name: wazuh
node.name: wazuh-indexer
network.host: 0.0.0.0
path.data: /var/lib/wazuh-indexer
discovery.type: single-node
compatibility.override_main_response_version: true
bootstrap.memory_lock: true
plugins.security.ssl.transport.pemcert_filepath: certs/tls.crt
plugins.security.ssl.transport.pemkey_filepath: certs/tls.key
plugins.security.ssl.transport.pemtrustedcas_filepath: ca/ca.crt
plugins.security.ssl.transport.enforce_hostname_verification: false
plugins.security.ssl.http.enabled: true
plugins.security.ssl.http.pemcert_filepath: certs/tls.crt
plugins.security.ssl.http.pemkey_filepath: certs/tls.key
plugins.security.ssl.http.pemtrustedcas_filepath: ca/ca.crt
plugins.security.allow_default_init_securityindex: false
plugins.security.nodes_dn:
- "CN=wazuh-indexer"
plugins.security.authcz.admin_dn:
- "CN=wazuh-admin"
plugins.security.audit.type: internal_opensearch
"""

_ISM_POLICY = {
    'alerts': {
        'policy': {
            'description': 'Delete Wazuh alert indices after 60 days.',
            'default_state': 'active',
            'states': [
                {
                    'name': 'active',
                    'actions': [],
                    'transitions': [
                        {'state_name': 'delete', 'conditions': {'min_index_age': '60d'}}
                    ],
                },
                {'name': 'delete', 'actions': [{'delete': {}}], 'transitions': []},
            ],
            'ism_template': [{'index_patterns': ['wazuh-alerts-*'], 'priority': 100}],
        }
    },
    'monitoring': {
        'policy': {
            'description': 'Delete Wazuh monitoring and statistics indices after 30 days.',
            'default_state': 'active',
            'states': [
                {
                    'name': 'active',
                    'actions': [],
                    'transitions': [
                        {'state_name': 'delete', 'conditions': {'min_index_age': '30d'}}
                    ],
                },
                {'name': 'delete', 'actions': [{'delete': {}}], 'transitions': []},
            ],
            'ism_template': [
                {
                    'index_patterns': [
                        'wazuh-monitoring-*',
                        'wazuh-statistics-*',
                    ],
                    'priority': 90,
                }
            ],
        }
    },
    'security-auditlog': {
        'policy': {
            'description': 'Delete security audit log indices after 30 days.',
            'default_state': 'active',
            'states': [
                {
                    'name': 'active',
                    'actions': [],
                    'transitions': [
                        {'state_name': 'delete', 'conditions': {'min_index_age': '30d'}}
                    ],
                },
                {'name': 'delete', 'actions': [{'delete': {}}], 'transitions': []},
            ],
            'ism_template': [{'index_patterns': ['security-auditlog-*'], 'priority': 100}],
        }
    },
}

_NODES_DN = """---
_meta:
  type: "nodesdn"
  config_version: 2
wazuh:
  nodes_dn:
    - "CN=wazuh-indexer"
"""
_SECURITY_ROLE_PAYLOADS = {
    'wazuh_grafana_reader': {
        'cluster_permissions': [
            'cluster_composite_ops_ro',
            'cluster_monitor',
        ],
        'index_permissions': [
            {
                'index_patterns': ['wazuh-alerts-*', 'wazuh-states-*', 'wazuh-monitoring-*'],
                'allowed_actions': [
                    'read',
                    'indices:admin/mappings/fields/get',
                    'indices:admin/mappings/get',
                    'indices:monitor/settings/get',
                ],
            }
        ],
    },
    'wazuh_metrics_reader': {
        'cluster_permissions': ['cluster_monitor'],
        'index_permissions': [
            {
                'index_patterns': ['wazuh-*'],
                'allowed_actions': ['read'],
            },
            {
                'index_patterns': ['*'],
                'allowed_actions': ['indices:monitor/stats'],
            },
        ],
    },
}


def create_indexer(
    config: ComponentConfig,
    provider: k8s.Provider,
    namespace: p.Input[str],
    ca: k8s.core.v1.Secret,
    credentials: k8s.core.v1.Secret,
) -> None:
    """Create persistent single-node indexer and apply security/retention configuration."""
    opts = p.ResourceOptions(provider=provider)

    config_map = k8s.core.v1.ConfigMap(
        'wazuh-indexer-config',
        metadata={'name': 'wazuh-indexer-config', 'namespace': namespace},
        data={'opensearch.yml': _INDEXER_CONFIG},
        opts=opts,
    )
    settings = k8s.core.v1.ConfigMap(
        'wazuh-indexer-security-settings',
        metadata={'name': 'wazuh-indexer-security-settings', 'namespace': namespace},
        data={
            'internal_users.yml': credentials.data.apply(
                lambda data: base64.b64decode(data['internal_users.yml']).decode()
            ),
            'nodes_dn.yml': _NODES_DN,
            'ism-alerts.json': json.dumps(_ISM_POLICY['alerts']),
            'ism-monitoring.json': json.dumps(_ISM_POLICY['monitoring']),
        },
        opts=opts,
    )

    labels = {'app.kubernetes.io/name': 'wazuh-indexer'}
    stateful_set = k8s.apps.v1.StatefulSet(
        'wazuh-indexer',
        metadata={'name': 'wazuh-indexer', 'namespace': namespace},
        spec={
            'service_name': 'wazuh-indexer',
            'replicas': 1,
            'selector': {'match_labels': labels},
            'template': {
                'metadata': {
                    'labels': labels,
                    'annotations': {
                        'checksum/indexer-config': hashlib.sha256(
                            _INDEXER_CONFIG.encode()
                        ).hexdigest()
                    },
                },
                'spec': {
                    'security_context': {
                        'run_as_non_root': True,
                        'run_as_user': 1000,
                        'run_as_group': 1000,
                        'fs_group': 1000,
                        'fs_group_change_policy': 'OnRootMismatch',
                    },
                    'containers': [
                        {
                            'name': 'indexer',
                            'image': f'wazuh/wazuh-indexer:{config.version}',
                            'ports': [
                                {'name': 'https', 'container_port': 9200},
                                {'name': 'transport', 'container_port': 9300},
                            ],
                            'env': [
                                {
                                    'name': 'OPENSEARCH_JAVA_OPTS',
                                    'value': f'-Xms{config.indexer_heap} -Xmx{config.indexer_heap}',
                                }
                            ],
                            'resources': {
                                'requests': {
                                    'cpu': config.indexer_cpu_request,
                                    'memory': config.indexer_memory_request,
                                },
                                'limits': {'memory': config.indexer_memory_limit},
                            },
                            'volume_mounts': [
                                {'name': 'data', 'mount_path': '/var/lib/wazuh-indexer'},
                                {
                                    'name': 'config',
                                    'mount_path': '/usr/share/wazuh-indexer/config/opensearch.yml',
                                    'sub_path': 'opensearch.yml',
                                    'read_only': True,
                                },
                                {
                                    'name': 'indexer-cert',
                                    'mount_path': '/usr/share/wazuh-indexer/config/certs',
                                    'read_only': True,
                                },
                                {
                                    'name': 'ca-cert',
                                    'mount_path': '/usr/share/wazuh-indexer/config/ca',
                                    'read_only': True,
                                },
                            ],
                            'readiness_probe': {
                                'tcp_socket': {'port': 9200},
                                'initial_delay_seconds': 30,
                                'period_seconds': 10,
                            },
                        }
                    ],
                    'volumes': [
                        {'name': 'config', 'config_map': {'name': config_map.metadata.name}},
                        {
                            'name': 'indexer-cert',
                            'secret': {'secret_name': 'wazuh-indexer'},
                        },
                        {'name': 'ca-cert', 'secret': {'secret_name': 'wazuh-ca'}},
                    ],
                },
            },
            'volume_claim_templates': [
                {
                    'metadata': {
                        'name': 'data',
                        'labels': {
                            'recurring-job-group.longhorn.io/default': 'enabled',
                        },
                    },
                    'spec': {
                        'access_modes': ['ReadWriteOnce'],
                        'resources': {'requests': {'storage': config.indexer_storage}},
                    },
                }
            ],
        },
        opts=p.ResourceOptions.merge(
            opts, p.ResourceOptions(depends_on=[config_map, settings, ca, credentials])
        ),
    )
    k8s.core.v1.Service(
        'wazuh-indexer',
        metadata={'name': 'wazuh-indexer', 'namespace': namespace},
        spec={
            'type': 'ClusterIP',
            'selector': labels,
            'ports': [
                {'name': 'https', 'port': 9200, 'target_port': 9200},
            ],
        },
        opts=p.ResourceOptions.merge(opts, p.ResourceOptions(depends_on=[stateful_set])),
    )

    role_payloads = {
        name: json.dumps(payload, separators=(',', ':'))
        for name, payload in _SECURITY_ROLE_PAYLOADS.items()
    }
    apply_script = f"""set -eu
export OPENSEARCH_JAVA_HOME=/usr/share/wazuh-indexer/jdk
BASE=/usr/share/wazuh-indexer
TOOLS=$BASE/plugins/opensearch-security/tools/securityadmin.sh
curl_tls() {{
  curl --cacert /ca/ca.crt --cert /certs/tls.crt --key /certs/tls.key "$@"
}}
until curl_tls --silent --output /dev/null https://wazuh-indexer:9200/; do sleep 5; done
mkdir -p /tmp/security-config
cp -a "$BASE/config/opensearch-security/." /tmp/security-config/
cp /custom/internal_users.yml /tmp/security-config/internal_users.yml
cp /custom/nodes_dn.yml /tmp/security-config/nodes_dn.yml
"$TOOLS" -h wazuh-indexer -p 9200 -cacert /ca/ca.crt -cert /certs/tls.crt -key /certs/tls.key -nhnv -cd /tmp/security-config -icl
"$TOOLS" -h wazuh-indexer -p 9200 -cacert /ca/ca.crt -cert /certs/tls.crt -key /certs/tls.key -nhnv -icl -us 0
curl --fail --silent --show-error --cacert /ca/ca.crt --cert /certs/tls.crt --key /certs/tls.key \\
  -H 'Content-Type: application/json' -X PUT -d '{role_payloads['wazuh_grafana_reader']}' \\
  'https://wazuh-indexer:9200/_plugins/_security/api/roles/wazuh_grafana_reader'
curl --fail --silent --show-error --cacert /ca/ca.crt --cert /certs/tls.crt --key /certs/tls.key \\
  -H 'Content-Type: application/json' -X PUT -d '{role_payloads['wazuh_metrics_reader']}' \\
  'https://wazuh-indexer:9200/_plugins/_security/api/roles/wazuh_metrics_reader'
curl --fail --silent --show-error --cacert /ca/ca.crt --cert /certs/tls.crt --key /certs/tls.key \\
  -H 'Content-Type: application/json' -X PUT -d '{{"backend_roles":["admin"]}}' \\
  'https://wazuh-indexer:9200/_plugins/_security/api/rolesmapping/security_rest_api_access'
curl --fail --silent --show-error --cacert /ca/ca.crt --cert /certs/tls.crt --key /certs/tls.key \\
  -H 'Content-Type: application/json' -X PUT -d '{{"backend_roles":["wazuh_grafana_reader"]}}' \\
  'https://wazuh-indexer:9200/_plugins/_security/api/rolesmapping/wazuh_grafana_reader'
curl --fail --silent --show-error --cacert /ca/ca.crt --cert /certs/tls.crt --key /certs/tls.key \\
  -H 'Content-Type: application/json' -X PUT -d '{{"backend_roles":["wazuh_metrics_reader"]}}' \\
  'https://wazuh-indexer:9200/_plugins/_security/api/rolesmapping/wazuh_metrics_reader'
for name in alerts monitoring; do
  url="https://wazuh-indexer:9200/_plugins/_ism/policies/wazuh-$name-retention"
  status=$(curl --silent --show-error --cacert /ca/ca.crt --cert /certs/tls.crt --key /certs/tls.key \\
    -o /tmp/ism-policy.json -w '%{{http_code}}' "$url" || true)
  if [ "$status" = 200 ]; then
    sequence=$(sed -n 's/.*"_seq_no":\\([0-9][0-9]*\\).*/\\1/p' /tmp/ism-policy.json)
    term=$(sed -n 's/.*"_primary_term":\\([0-9][0-9]*\\).*/\\1/p' /tmp/ism-policy.json)
    url="$url?if_seq_no=$sequence&if_primary_term=$term"
  fi
  curl --fail --silent --show-error --cacert /ca/ca.crt --cert /certs/tls.crt --key /certs/tls.key \\
    -H 'Content-Type: application/json' -X PUT -d "@/custom/ism-$name.json" "$url"
done
curl --fail --silent --show-error --cacert /ca/ca.crt --cert /certs/tls.crt --key /certs/tls.key \\
  -H 'Content-Type: application/json' -X PUT -d '{{"persistent":{{"plugins.index_state_management.history.number_of_replicas":0}}}}' \\
  'https://wazuh-indexer:9200/_cluster/settings'
for index in '.opendistro-ism-managed-index-history-*' '.opendistro-job-scheduler-lock'; do
  curl --fail --silent --show-error --cacert /ca/ca.crt --cert /certs/tls.crt --key /certs/tls.key \\
    -H 'Content-Type: application/json' -X PUT -d '{{"index.number_of_replicas":0}}' \\
    "https://wazuh-indexer:9200/$index/_settings"
done
curl --fail --silent --show-error --cacert /ca/ca.crt --cert /certs/tls.crt --key /certs/tls.key \\
  -H 'Content-Type: application/json' -X PUT -d '{{"index_patterns":["wazuh-*"],"priority":1,"template":{{"settings":{{"index.number_of_replicas":0}}}}}}' \\
  'https://wazuh-indexer:9200/_index_template/wazuh-single-node'
curl --fail --silent --show-error --cacert /ca/ca.crt --cert /certs/tls.crt --key /certs/tls.key \\
  -H 'Content-Type: application/json' -X PUT -d '{{"index_patterns":["wazuh-*"],"order":1000,"settings":{{"index.number_of_replicas":0}}}}' \\
  'https://wazuh-indexer:9200/_template/wazuh-single-node'
curl --fail --silent --show-error --cacert /ca/ca.crt --cert /certs/tls.crt --key /certs/tls.key \\
  -H 'Content-Type: application/json' -X PUT -d '{{"index_patterns":["security-auditlog-*"],"order":1000,"settings":{{"index.number_of_replicas":0}}}}' \\
  'https://wazuh-indexer:9200/_template/wazuh-security-auditlog-single-node'
curl --fail --silent --show-error --cacert /ca/ca.crt --cert /certs/tls.crt --key /certs/tls.key \\
  -H 'Content-Type: application/json' -X PUT -d '{{"index.number_of_replicas":0}}' \\
  'https://wazuh-indexer:9200/.opendistro-ism-config/_settings'
curl --fail --silent --show-error --cacert /ca/ca.crt --cert /certs/tls.crt --key /certs/tls.key \\
  -H 'Content-Type: application/json' -X PUT -d '{{"index.number_of_replicas":0}}' \\
  'https://wazuh-indexer:9200/security-auditlog-*/_settings'
"""
    config_hash = p.Output.all(
        _INDEXER_CONFIG,
        settings.data,
        credentials.data.apply(lambda data: data['admin']),
        _SECURITY_ROLE_PAYLOADS,
        _ISM_POLICY,
        apply_script,
    ).apply(
        lambda values: hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()[:12]
    )
    job = k8s.batch.v1.Job(
        'wazuh-indexer-security',
        metadata={
            'name': config_hash.apply(lambda digest: f'wazuh-indexer-security-{digest}'),
            'namespace': namespace,
        },
        spec={
            'backoff_limit': 4,
            'template': {
                'metadata': {'labels': {'app.kubernetes.io/name': 'wazuh-indexer-security'}},
                'spec': {
                    'restart_policy': 'OnFailure',
                    'containers': [
                        {
                            'name': 'securityadmin',
                            'image': f'wazuh/wazuh-indexer:{config.version}',
                            'command': ['sh', '-c', apply_script],
                            'volume_mounts': [
                                {'name': 'security', 'mount_path': '/custom', 'read_only': True},
                                {'name': 'admin-cert', 'mount_path': '/certs', 'read_only': True},
                                {'name': 'ca-cert', 'mount_path': '/ca', 'read_only': True},
                            ],
                        }
                    ],
                    'volumes': [
                        {
                            'name': 'security',
                            'config_map': {
                                'name': settings.metadata.name,
                                'items': [
                                    {'key': 'internal_users.yml', 'path': 'internal_users.yml'},
                                    {'key': 'nodes_dn.yml', 'path': 'nodes_dn.yml'},
                                    {'key': 'ism-alerts.json', 'path': 'ism-alerts.json'},
                                    {'key': 'ism-monitoring.json', 'path': 'ism-monitoring.json'},
                                ],
                            },
                        },
                        {'name': 'admin-cert', 'secret': {'secret_name': 'wazuh-admin'}},
                        {'name': 'ca-cert', 'secret': {'secret_name': 'wazuh-ca'}},
                    ],
                },
            },
        },
        opts=p.ResourceOptions.merge(
            opts, p.ResourceOptions(depends_on=[stateful_set, settings, ca, credentials])
        ),
    )
    p.export('wazuh_indexer_service', 'wazuh-indexer.wazuh.svc:9200')
    p.export('wazuh_indexer_security_job', job.metadata.name)
