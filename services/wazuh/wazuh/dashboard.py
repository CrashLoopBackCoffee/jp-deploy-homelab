"""Provision the Wazuh dashboard and LAN ingress."""

import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_kubernetes as k8s
import utils.cloudflare

from wazuh.config import ComponentConfig

DASHBOARD_PORT = 5601


def create_dashboard(
    config: ComponentConfig,
    provider: k8s.Provider,
    namespace: p.Input[str],
    ca_secret: k8s.core.v1.Secret,
    credentials: k8s.core.v1.Secret,
    cloudflare_provider: cloudflare.Provider,
) -> None:
    opts = p.ResourceOptions(provider=provider)
    labels = {'app.kubernetes.io/name': 'wazuh-dashboard'}
    config_map = k8s.core.v1.ConfigMap(
        'wazuh-dashboard-config',
        metadata={'name': 'wazuh-dashboard-config', 'namespace': namespace},
        data={
            'opensearch_dashboards.yml': f"""server.host: 0.0.0.0
server.port: {DASHBOARD_PORT}
server.ssl.enabled: true
server.ssl.certificate: /usr/share/wazuh-dashboard/certs/cert.pem
server.ssl.key: /usr/share/wazuh-dashboard/certs/key.pem
opensearch.hosts: ["${{INDEXER_URL}}"]
opensearch.ssl.certificateAuthorities: [/usr/share/wazuh-dashboard/certs/ca/ca.crt]
opensearch.ssl.verificationMode: full
opensearch.username: ${{DASHBOARD_USERNAME}}
opensearch.password: ${{DASHBOARD_PASSWORD}}
""",
            'wazuh.yml': f"""hosts:
  - 1513629884013:
      url: https://wazuh-manager.{config.namespace}.svc
      port: 55000
      username: wazuh-wui
      password: __API_PASSWORD__
      run_as: true
      ssl:
        verificationMode: full
        certificateAuthorities:
          - /usr/share/wazuh-dashboard/certs/ca/ca.crt
""",
        },
        opts=opts,
    )
    deployment = k8s.apps.v1.Deployment(
        'wazuh-dashboard',
        metadata={'name': 'wazuh-dashboard', 'namespace': namespace},
        spec={  # type: ignore
            'replicas': 1,
            'selector': {'matchLabels': labels},
            'strategy': {'type': 'Recreate'},
            'template': {
                'metadata': {'labels': labels},
                'spec': {
                    'securityContext': {'fsGroup': 1000},
                    'initContainers': [
                        {
                            'name': 'prepare-api-config',
                            'image': f'wazuh/wazuh-dashboard:{config.version}',
                            'command': [
                                '/bin/sh',
                                '-c',
                                'set -eu; '
                                'cp /source/wazuh.yml /writable/wazuh.yml; '
                                'sed -i "s|__API_PASSWORD__|${API_PASSWORD}|" /writable/wazuh.yml; '
                                'chmod 0640 /writable/wazuh.yml',
                            ],
                            'env': [
                                {
                                    'name': 'API_PASSWORD',
                                    'valueFrom': {
                                        'secretKeyRef': {'name': 'wazuh-credentials', 'key': 'api'}
                                    },
                                },
                            ],
                            'volumeMounts': [
                                {'name': 'config', 'mountPath': '/source', 'readOnly': True},
                                {'name': 'wazuh-config', 'mountPath': '/writable'},
                            ],
                            'securityContext': {'allowPrivilegeEscalation': False},
                        }
                    ],
                    'containers': [
                        {
                            'name': 'wazuh-dashboard',
                            'image': f'wazuh/wazuh-dashboard:{config.version}',
                            'ports': [{'name': 'https', 'containerPort': DASHBOARD_PORT}],
                            'env': [
                                {
                                    'name': 'INDEXER_URL',
                                    'value': f'https://wazuh-indexer.{config.namespace}.svc:9200',
                                },
                                {'name': 'INDEXER_USERNAME', 'value': 'kibanaserver'},
                                {
                                    'name': 'INDEXER_PASSWORD',
                                    'valueFrom': {
                                        'secretKeyRef': {
                                            'name': 'wazuh-credentials',
                                            'key': 'kibanaserver',
                                        }
                                    },
                                },
                                {'name': 'DASHBOARD_USERNAME', 'value': 'kibanaserver'},
                                {
                                    'name': 'DASHBOARD_PASSWORD',
                                    'valueFrom': {
                                        'secretKeyRef': {
                                            'name': 'wazuh-credentials',
                                            'key': 'kibanaserver',
                                        }
                                    },
                                },
                                {
                                    'name': 'API_PASSWORD',
                                    'valueFrom': {
                                        'secretKeyRef': {'name': 'wazuh-credentials', 'key': 'api'}
                                    },
                                },
                            ],
                            'volumeMounts': [
                                {
                                    'name': 'config',
                                    'mountPath': '/usr/share/wazuh-dashboard/config/opensearch_dashboards.yml',
                                    'subPath': 'opensearch_dashboards.yml',
                                    'readOnly': True,
                                },
                                {
                                    'name': 'wazuh-config',
                                    'mountPath': '/usr/share/wazuh-dashboard/data/wazuh/config',
                                    'readOnly': False,
                                },
                                {
                                    'name': 'dashboard-certs',
                                    'mountPath': '/usr/share/wazuh-dashboard/certs/cert.pem',
                                    'subPath': 'tls.crt',
                                    'readOnly': True,
                                },
                                {
                                    'name': 'dashboard-certs',
                                    'mountPath': '/usr/share/wazuh-dashboard/certs/key.pem',
                                    'subPath': 'tls.key',
                                    'readOnly': True,
                                },
                                {
                                    'name': 'ca',
                                    'mountPath': '/usr/share/wazuh-dashboard/certs/ca',
                                    'readOnly': True,
                                },
                            ],
                            'readinessProbe': {
                                'httpGet': {'path': '/', 'port': DASHBOARD_PORT, 'scheme': 'HTTPS'},
                                'initialDelaySeconds': 30,
                                'periodSeconds': 10,
                            },
                            'resources': {
                                'requests': {'cpu': '100m', 'memory': '512Mi'},
                                'limits': {'memory': '1Gi'},
                            },
                        },
                    ],
                    'volumes': [
                        {'name': 'config', 'configMap': {'name': config_map.metadata.name}},
                        {'name': 'wazuh-config', 'emptyDir': {}},
                        {'name': 'dashboard-certs', 'secret': {'secretName': 'wazuh-dashboard'}},
                        {
                            'name': 'ca',
                            'secret': {
                                'secretName': ca_secret.metadata.name,
                                'items': [{'key': 'ca.crt', 'path': 'ca.crt'}],
                            },
                        },
                    ],
                },
            },
        },
        opts=p.ResourceOptions.merge(
            opts, p.ResourceOptions(depends_on=[config_map, ca_secret, credentials])
        ),
    )
    service = k8s.core.v1.Service(
        'wazuh-dashboard',
        metadata={'name': 'wazuh-dashboard', 'namespace': namespace},
        spec={  # type: ignore
            'type': 'ClusterIP',
            'selector': labels,
            'ports': [{'name': 'https', 'port': DASHBOARD_PORT, 'targetPort': DASHBOARD_PORT}],
        },
        opts=p.ResourceOptions.merge(opts, p.ResourceOptions(depends_on=[deployment])),
    )
    transport = k8s.apiextensions.CustomResource(
        'wazuh-dashboard-transport',
        api_version='traefik.io/v1alpha1',
        kind='ServersTransport',
        metadata={'name': 'wazuh-dashboard-transport', 'namespace': namespace},
        spec={
            'serverName': f'wazuh-dashboard.{config.namespace}.svc.cluster.local',
            'rootCAsSecrets': [ca_secret.metadata.name],
        },
        opts=p.ResourceOptions.merge(opts, p.ResourceOptions(depends_on=[ca_secret])),
    )
    _route = k8s.apiextensions.CustomResource(
        'wazuh-dashboard-ingress',
        api_version='traefik.io/v1alpha1',
        kind='IngressRoute',
        metadata={'name': 'wazuh-dashboard', 'namespace': namespace},
        spec={
            'entryPoints': ['websecure'],
            'routes': [
                {
                    'match': f'Host(`{config.dashboard_hostname}`)',
                    'kind': 'Rule',
                    'services': [
                        {
                            'name': 'wazuh-dashboard',
                            'port': DASHBOARD_PORT,
                            'scheme': 'https',
                            'serversTransport': 'wazuh-dashboard-transport',
                        }
                    ],
                }
            ],
            'tls': {},
        },
        opts=p.ResourceOptions.merge(opts, p.ResourceOptions(depends_on=[service, transport])),
    )
    traefik = k8s.core.v1.Service.get('wazuh-dashboard-traefik', 'traefik/traefik', opts=opts)
    utils.cloudflare.create_a_record(
        'wazuh-dashboard-dns',
        host=config.dashboard_hostname.removesuffix(f'.{config.zone}'),
        zone_name=config.zone,
        address=traefik.status.load_balancer.ingress[0].ip,
        cloudflare_provider=cloudflare_provider,
        opts=p.ResourceOptions(parent=deployment),
    )
