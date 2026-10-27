import hashlib

import pulumi as p
import pulumi_kubernetes as k8s

from observability.config import ComponentConfig

OPNSENSE_EXPORTER_PORT = 8080
OPNSENSE_EXPORTER_LABELS = {'app.kubernetes.io/name': 'opnsense-exporter'}
# Services this OPNsense does not run (dnsmasq instead of Kea, no CARP, OpenVPN or IPsec); Unbound
# would need its extended statistics and an extra privilege for three metrics.
DISABLED_COLLECTORS = ('unbound', 'kea-dhcpv4', 'kea-dhcpv6', 'carp', 'openvpn', 'ipsec')


def create_opnsense_exporter(component_config: ComponentConfig, k8s_opts: p.ResourceOptions):
    """Exporter that reads the OPNsense API with the read-only user `metrics-exporter` (ADR-0038)."""
    opnsense = component_config.opnsense
    secret = k8s.core.v1.Secret(
        'opnsense-exporter',
        metadata={'name': 'opnsense-exporter'},
        string_data={
            'OPNSENSE_EXPORTER_OPS_API_KEY': opnsense.api_key.value,
            'OPNSENSE_EXPORTER_OPS_API_SECRET': opnsense.api_secret.value,
        },
        opts=k8s_opts,
    )
    # The exporter reads the credentials only at start, so a rotated key must roll the pod.
    credentials_checksum = p.Output.all(opnsense.api_key.value, opnsense.api_secret.value).apply(
        lambda values: hashlib.sha256('\n'.join(values).encode()).hexdigest()
    )

    deployment = k8s.apps.v1.Deployment(
        'opnsense-exporter',
        metadata={'name': 'opnsense-exporter'},
        spec={
            'replicas': 1,
            'selector': {'match_labels': OPNSENSE_EXPORTER_LABELS},
            'template': {
                'metadata': {
                    'labels': OPNSENSE_EXPORTER_LABELS,
                    'annotations': {'checksum/credentials': credentials_checksum},
                },
                'spec': {
                    'containers': [
                        {
                            'name': 'opnsense-exporter',
                            'image': f'ghcr.io/athennamind/opnsense-exporter:{opnsense.version}',
                            'args': [
                                '--opnsense.protocol=https',
                                f'--opnsense.address={opnsense.api_host}',
                                '--exporter.instance-label=opnsense',
                                f'--web.listen-address=:{OPNSENSE_EXPORTER_PORT}',
                                *(f'--exporter.disable-{name}' for name in DISABLED_COLLECTORS),
                            ],
                            'env_from': [{'secret_ref': {'name': 'opnsense-exporter'}}],
                            # Not named `metrics`, so the generic pod scrape in Alloy ignores it
                            # and the explicit `opnsense` job owns it.
                            'ports': [{'name': 'http', 'container_port': OPNSENSE_EXPORTER_PORT}],
                            'resources': {
                                'requests': {'cpu': '10m', 'memory': '32Mi'},
                                'limits': {'memory': '128Mi'},
                            },
                        },
                    ],
                },
            },
        },
        opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[secret])),
    )

    return k8s.core.v1.Service(
        'opnsense-exporter',
        metadata={'name': 'opnsense-exporter'},
        spec={
            'selector': OPNSENSE_EXPORTER_LABELS,
            'ports': [{'name': 'http', 'port': OPNSENSE_EXPORTER_PORT, 'target_port': 'http'}],
        },
        opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[deployment])),
    )
