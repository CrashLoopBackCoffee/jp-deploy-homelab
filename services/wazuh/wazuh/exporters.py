"""Prometheus exporters for Wazuh indexer health and vulnerability state."""

import json

import pulumi as p
import pulumi_kubernetes as k8s

from wazuh.config import ComponentConfig

_FINDINGS_CONFIG = {
    'modules': {
        'wazuh_vulnerabilities': {
            'headers': {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            'body': {
                'content': json.dumps(
                    {
                        'size': 0,
                        'aggs': {
                            'severity': {'terms': {'field': 'vulnerability.severity', 'size': 8}},
                            'agent': {
                                'composite': {
                                    'size': 592,
                                    'sources': [
                                        {'agent_id': {'terms': {'field': 'agent.id'}}},
                                        {'agent_name': {'terms': {'field': 'agent.name'}}},
                                    ],
                                }
                            },
                        },
                    },
                    separators=(',', ':'),
                )
            },
            'http_client_config': {
                'basic_auth': {
                    'username': 'metrics_reader',
                    'password_file': '/credentials/password',
                },
                'tls_config': {
                    'ca_file': '/ca/ca.crt',
                    'cert_file': '/certs/tls.crt',
                    'key_file': '/certs/tls.key',
                },
            },
            'metrics': [
                {
                    'name': 'wazuh_vulnerability_findings_by_severity',
                    'type': 'object',
                    'help': 'Current Wazuh vulnerability findings by severity.',
                    'path': '{.aggregations.severity.buckets[*]}',
                    'labels': {'severity': '{.key}'},
                    'values': {'count': '{.doc_count}'},
                },
                {
                    'name': 'wazuh_vulnerability_findings_by_agent',
                    'type': 'object',
                    'help': 'Current Wazuh vulnerability findings by agent.',
                    'path': '{.aggregations.agent.buckets[*]}',
                    'labels': {
                        'agent_id': '{.key.agent_id}',
                        'agent_name': '{.key.agent_name}',
                    },
                    'values': {'count': '{.doc_count}'},
                },
            ],
        }
    }
}


def _deployment(
    name: str,
    image: str,
    port: int,
    command: list[str],
    mounts: list[dict[str, object]],
    volumes: list[dict[str, object]],
    env: list[dict[str, object]],
    provider: k8s.Provider,
    namespace: p.Input[str],
) -> k8s.apps.v1.Deployment:
    labels = {'app.kubernetes.io/name': name}
    deployment = k8s.apps.v1.Deployment(
        name,
        metadata={'name': name, 'namespace': namespace},
        spec={  # type: ignore
            'replicas': 1,
            'selector': {'match_labels': labels},
            'template': {
                'metadata': {'labels': labels},
                'spec': {
                    'containers': [
                        {
                            'name': name,
                            'image': image,
                            'args': command,
                            'env': env,
                            'ports': [{'name': 'metrics', 'containerPort': port}],
                            'volumeMounts': mounts,
                            'resources': {
                                'requests': {'cpu': '10m', 'memory': '32Mi'},
                                'limits': {'memory': '64Mi'},
                            },
                            'readinessProbe': {
                                'httpGet': {'path': '/metrics', 'port': port},
                                'initialDelaySeconds': 3,
                                'periodSeconds': 10,
                            },
                        }
                    ],
                    'volumes': volumes,
                },
            },
        },
        opts=p.ResourceOptions(provider=provider),
    )
    k8s.core.v1.Service(
        f'{name}-service',
        metadata={'name': name, 'namespace': namespace},
        spec={  # type: ignore
            'type': 'ClusterIP',
            'selector': labels,
            'ports': [{'name': 'metrics', 'port': port, 'targetPort': port}],
        },
        opts=p.ResourceOptions(provider=provider, depends_on=[deployment]),
    )
    return deployment


def create_exporters(
    config: ComponentConfig,
    provider: k8s.Provider,
    namespace: p.Input[str],
    ca_secret: k8s.core.v1.Secret,
) -> None:
    """Deploy internal-only indexer health and vulnerability finding exporters."""
    opts = p.ResourceOptions(provider=provider)
    findings_config = k8s.core.v1.ConfigMap(
        'wazuh-findings-exporter-config',
        metadata={'name': 'wazuh-findings-exporter-config', 'namespace': namespace},
        data={'config.yml': json.dumps(_FINDINGS_CONFIG, separators=(',', ':'))},
        opts=opts,
    )
    tls_volumes: list[dict[str, object]] = [
        {'name': 'client-certificate', 'secret': {'secretName': 'wazuh-metrics-reader'}},
        {
            'name': 'ca-certificate',
            'secret': {
                'secretName': ca_secret.metadata.name,
                'items': [{'key': 'ca.crt', 'path': 'ca.crt'}],
            },
        },
        {
            'name': 'basic-auth',
            'secret': {
                'secretName': 'wazuh-credentials',
                'items': [{'key': 'metrics_reader', 'path': 'password'}],
            },
        },
    ]
    tls_mounts: list[dict[str, object]] = [
        {'name': 'client-certificate', 'mountPath': '/certs', 'readOnly': True},
        {
            'name': 'ca-certificate',
            'mountPath': '/ca',
            'readOnly': True,
        },
        {'name': 'basic-auth', 'mountPath': '/credentials', 'readOnly': True},
    ]
    _deployment(
        'wazuh-indexer-exporter',
        'quay.io/prometheuscommunity/elasticsearch-exporter:v1.11.0',
        9114,
        [
            f'--es.uri=https://wazuh-indexer.{config.namespace}.svc:9200',
            '--es.client-cert=/certs/tls.crt',
            '--es.client-private-key=/certs/tls.key',
            '--es.ca=/ca/ca.crt',
        ],
        tls_mounts,
        tls_volumes,
        [
            {'name': 'ES_USERNAME', 'value': 'metrics_reader'},
            {
                'name': 'ES_PASSWORD',
                'valueFrom': {
                    'secretKeyRef': {'name': 'wazuh-credentials', 'key': 'metrics_reader'}
                },
            },
        ],
        provider,
        namespace,
    )
    _deployment(
        'wazuh-findings-exporter',
        'quay.io/prometheuscommunity/json-exporter:v0.8.0',
        7979,
        ['--config.file=/config/config.yml'],
        [
            *tls_mounts,
            {'name': 'config', 'mountPath': '/config', 'readOnly': True},
        ],
        [
            *tls_volumes,
            {
                'name': 'config',
                'configMap': {'name': findings_config.metadata.name},
            },
        ],
        [],
        provider,
        namespace,
    )
