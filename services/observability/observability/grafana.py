import hashlib
import json

import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_random as random
import utils.opnsense.dnsmasq.host

from observability import alert_rules, dashboards
from observability.config import ComponentConfig
from observability.loki import LOKI_GATEWAY_URL
from observability.mimir import MIMIR_GATEWAY_URL

GRAFANA_PORT = 80
SECRETS_NAME = 'grafana-secrets'
ALERTING_MOUNT_PATH = '/etc/grafana/provisioning/alerting'
DASHBOARD_PROVIDER = 'homelab'
DASHBOARD_PATH = f'/var/lib/grafana/dashboards/{DASHBOARD_PROVIDER}'

# Grafana expands $VAR in provisioning files, so the Pushover secrets stay out of the ConfigMap.
CONTACT_POINTS = {
    'apiVersion': 1,
    'contactPoints': [
        {
            'orgId': 1,
            'name': 'pushover',
            'receivers': [
                {
                    'uid': 'pushover',
                    'type': 'pushover',
                    'settings': {
                        'userKey': '$PUSHOVER_USER_KEY',
                        'apiToken': '$PUSHOVER_API_TOKEN',
                        'priority': '0',
                    },
                },
            ],
        },
    ],
}
NOTIFICATION_POLICIES = {
    'apiVersion': 1,
    'policies': [
        {
            'orgId': 1,
            'receiver': 'pushover',
            'group_by': ['alertname', 'namespace'],
            'group_wait': '30s',
            'group_interval': '5m',
            'repeat_interval': '12h',
        },
    ],
}


def _checksum(files: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def create_grafana(
    component_config: ComponentConfig,
    k8s_opts: p.ResourceOptions,
    depends_on: list[p.Resource],
):
    grafana_config = component_config.grafana
    hostname = f'{grafana_config.host}.{component_config.zone}'

    admin_password = random.RandomPassword('grafana-admin-password', length=32, special=False)
    secret_key = random.RandomPassword('grafana-secret-key', length=64, special=False)
    secrets = k8s.core.v1.Secret(
        SECRETS_NAME,
        metadata={'name': SECRETS_NAME},
        string_data={
            'GF_SECURITY_SECRET_KEY': secret_key.result,
            'PUSHOVER_API_TOKEN': grafana_config.pushover.api_token.value,
            'PUSHOVER_USER_KEY': grafana_config.pushover.user_key.value,
        },
        opts=k8s_opts,
    )
    alerting_files = {
        'contact-points.yaml': json.dumps(CONTACT_POINTS, indent=2),
        'policies.yaml': json.dumps(NOTIFICATION_POLICIES, indent=2),
        'rules.yaml': json.dumps(alert_rules.provisioning(), indent=2),
    }
    alerting = k8s.core.v1.ConfigMap(
        'grafana-alerting-provisioning',
        data=alerting_files,
        opts=k8s_opts,
    )
    dashboard_files = k8s.core.v1.ConfigMap(
        'grafana-dashboards',
        data=dashboards.provisioning_files(),
        opts=k8s_opts,
    )

    release = k8s.helm.v3.Release(
        'grafana',
        name='grafana',
        chart='grafana',
        version=grafana_config.version,
        repository_opts={'repo': 'https://grafana-community.github.io/helm-charts'},
        values={
            'adminUser': 'admin',
            'adminPassword': admin_password.result,
            'envFromSecrets': [{'name': secrets.metadata.name}],
            'persistence': {'enabled': True, 'size': f'{grafana_config.storage_size_gb}Gi'},
            'grafana.ini': {
                'server': {'domain': hostname, 'root_url': f'https://{hostname}'},
                'unified_alerting': {'enabled': True},
                'analytics': {'reporting_enabled': False, 'check_for_updates': False},
            },
            'testFramework': {'enabled': False},
            # Grafana reads alerting provisioning only at startup, so changed content rolls the pod.
            'podAnnotations': {'checksum/provisioning': _checksum(alerting_files)},
            'datasources': {
                'datasources.yaml': {
                    'apiVersion': 1,
                    'datasources': [
                        {
                            'name': 'Mimir',
                            'uid': alert_rules.MIMIR_DATASOURCE_UID,
                            'type': 'prometheus',
                            'access': 'proxy',
                            'url': f'{MIMIR_GATEWAY_URL}/prometheus',
                            'isDefault': True,
                            'jsonData': {'httpMethod': 'POST'},
                        },
                        {
                            'name': 'Loki',
                            'uid': dashboards.LOKI_DATASOURCE_UID,
                            'type': 'loki',
                            'access': 'proxy',
                            'url': LOKI_GATEWAY_URL,
                        },
                    ],
                },
            },
            'extraVolumes': [
                {'name': 'alerting-provisioning', 'configMap': {'name': alerting.metadata.name}},
            ],
            'extraVolumeMounts': [
                {
                    'name': 'alerting-provisioning',
                    'mountPath': ALERTING_MOUNT_PATH,
                    'readOnly': True,
                },
            ],
            'dashboardProviders': {
                'dashboardproviders.yaml': {
                    'apiVersion': 1,
                    'providers': [
                        {
                            'name': DASHBOARD_PROVIDER,
                            'orgId': 1,
                            'folder': alert_rules.FOLDER,
                            'type': 'file',
                            'disableDeletion': False,
                            'editable': False,
                            'options': {'path': DASHBOARD_PATH},
                        },
                    ],
                },
            },
            'dashboardsConfigMaps': {DASHBOARD_PROVIDER: dashboard_files.metadata.name},
        },
        opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=depends_on)),
    )

    _expose(component_config, hostname, k8s_opts, release)
    p.export('grafana-url', f'https://{hostname}')
    p.export('grafana-admin-password', p.Output.secret(admin_password.result))
    return release


def _expose(
    component_config: ComponentConfig,
    hostname: str,
    k8s_opts: p.ResourceOptions,
    release: k8s.helm.v3.Release,
):
    """Publish Grafana through the existing Traefik with its wildcard certificate."""
    traefik_service = k8s.core.v1.Service.get('traefik-service', 'traefik/traefik', opts=k8s_opts)
    utils.opnsense.dnsmasq.host.Host(
        'grafana',
        host=component_config.grafana.host,
        domain=component_config.zone,
        ipaddress=traefik_service.status.load_balancer.ingress[0].ip,
    )
    k8s.apiextensions.CustomResource(
        'grafana-ingress',
        api_version='traefik.io/v1alpha1',
        kind='IngressRoute',
        metadata={'name': 'grafana'},
        spec={
            'entryPoints': ['websecure'],
            'routes': [
                {
                    'kind': 'Rule',
                    'match': f'Host(`{hostname}`)',
                    'services': [{'name': 'grafana', 'port': GRAFANA_PORT}],
                },
            ],
            'tls': {},
        },
        opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[release])),
    )
