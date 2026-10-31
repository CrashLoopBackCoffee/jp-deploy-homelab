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
        spec={  # type: ignore[reportArgumentType]  # Nested Kubernetes input inference loses the generated spec type.
            'replicas': 1,
            'selector': {'match_labels': labels},
            'strategy': {'type': 'Recreate'},
            'template': {
                'metadata': {'labels': labels},
                'spec': {
                    'security_context': {'fs_group': 1000},
                    'init_containers': [
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
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': 'wazuh-credentials',
                                            'key': 'api',
                                        }
                                    },
                                },
                            ],
                            'volume_mounts': [
                                {'name': 'config', 'mount_path': '/source', 'read_only': True},
                                {'name': 'wazuh-config', 'mount_path': '/writable'},
                            ],
                            'security_context': {'allow_privilege_escalation': False},
                        }
                    ],
                    'containers': [
                        {
                            'name': 'wazuh-dashboard',
                            'image': f'wazuh/wazuh-dashboard:{config.version}',
                            'ports': [{'name': 'https', 'container_port': DASHBOARD_PORT}],
                            'env': [
                                {
                                    'name': 'INDEXER_URL',
                                    'value': f'https://wazuh-indexer.{config.namespace}.svc:9200',
                                },
                                {'name': 'INDEXER_USERNAME', 'value': 'kibanaserver'},
                                {
                                    'name': 'INDEXER_PASSWORD',
                                    'value_from': {
                                        'secret_key_ref': {
                                            'name': 'wazuh-credentials',
                                            'key': 'kibanaserver',
                                        }
                                    },
                                },
                                {'name': 'DASHBOARD_USERNAME', 'value': 'kibanaserver'},
                                {
                                    'name': 'DASHBOARD_PASSWORD',
                                    'value_from': {
                                        'secret_key_ref': {
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
                            'volume_mounts': [
                                {
                                    'name': 'config',
                                    'mount_path': '/usr/share/wazuh-dashboard/config/opensearch_dashboards.yml',
                                    'sub_path': 'opensearch_dashboards.yml',
                                    'read_only': True,
                                },
                                {
                                    'name': 'wazuh-config',
                                    'mount_path': '/usr/share/wazuh-dashboard/data/wazuh/config',
                                    'read_only': False,
                                },
                                {
                                    'name': 'dashboard-certs',
                                    'mount_path': '/usr/share/wazuh-dashboard/certs/cert.pem',
                                    'sub_path': 'tls.crt',
                                    'read_only': True,
                                },
                                {
                                    'name': 'dashboard-certs',
                                    'mount_path': '/usr/share/wazuh-dashboard/certs/key.pem',
                                    'sub_path': 'tls.key',
                                    'read_only': True,
                                },
                                {
                                    'name': 'ca',
                                    'mount_path': '/usr/share/wazuh-dashboard/certs/ca',
                                    'read_only': True,
                                },
                            ],
                            'readiness_probe': {
                                'http_get': {
                                    'path': '/',
                                    'port': DASHBOARD_PORT,
                                    'scheme': 'HTTPS',
                                },
                                'initial_delay_seconds': 30,
                                'period_seconds': 10,
                            },
                            'resources': {
                                'requests': {'cpu': '100m', 'memory': '512Mi'},
                                'limits': {'memory': '1Gi'},
                            },
                        },
                    ],
                    'volumes': [
                        {'name': 'config', 'config_map': {'name': config_map.metadata.name}},
                        {'name': 'wazuh-config', 'empty_dir': {}},
                        {'name': 'dashboard-certs', 'secret': {'secret_name': 'wazuh-dashboard'}},
                        {
                            'name': 'ca',
                            'secret': {
                                'secret_name': ca_secret.metadata.name,
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
        spec={
            'type': 'ClusterIP',
            'selector': labels,
            'ports': [{'name': 'https', 'port': DASHBOARD_PORT, 'target_port': DASHBOARD_PORT}],
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
