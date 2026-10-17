import pathlib

import pulumi as p
import pulumi_kubernetes as k8s
import utils.opnsense.dnsmasq.host

from observability.config import ComponentConfig
from observability.loki import LOKI_GATEWAY_URL
from observability.mimir import MIMIR_GATEWAY_URL

ALLOY_CONFIG = pathlib.Path(__file__).parent.parent / 'assets' / 'alloy' / 'config.alloy'

# The QNAP can send RFC 5424 or RFC 3164, and Alloy needs one listener per format, so each
# format has its own port, served over TCP and UDP.
SYSLOG_PORTS = {'rfc5424': 1514, 'rfc3164': 1515}
SYSLOG_PROTOCOLS = ('TCP', 'UDP')


def _syslog_ports() -> list[tuple[str, int, str]]:
    """Port name, number and protocol of every syslog listener."""
    return [
        (f'syslog{syslog_format[3:]}-{protocol.lower()}', port, protocol)
        for syslog_format, port in SYSLOG_PORTS.items()
        for protocol in SYSLOG_PROTOCOLS
    ]


def create_alloy(
    component_config: ComponentConfig,
    k8s_opts: p.ResourceOptions,
    depends_on: list[p.Resource],
):
    """One collector for cluster metrics and logs; single node, so a single replica suffices."""
    config = ALLOY_CONFIG.read_text()
    config = config.replace('MIMIR_PUSH_URL', f'{MIMIR_GATEWAY_URL}/api/v1/push')
    config = config.replace('LOKI_PUSH_URL', f'{LOKI_GATEWAY_URL}/loki/api/v1/push')
    config = config.replace('SYSLOG_RFC5424_PORT', str(SYSLOG_PORTS['rfc5424']))
    config = config.replace('SYSLOG_RFC3164_PORT', str(SYSLOG_PORTS['rfc3164']))

    return k8s.helm.v3.Release(
        'alloy',
        name='alloy',
        chart='alloy',
        version=component_config.alloy.version,
        repository_opts={'repo': 'https://grafana.github.io/helm-charts'},
        values={
            'controller': {'type': 'deployment', 'replicas': 1},
            'alloy': {'configMap': {'content': config}},
        },
        opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=depends_on)),
    )


def create_node_proxy_access(k8s_opts: p.ResourceOptions, alloy: k8s.helm.v3.Release):
    """Allow Alloy to read kubelet and cAdvisor metrics through the API server's node proxy."""
    role = k8s.rbac.v1.ClusterRole(
        'alloy-node-proxy',
        metadata={'name': 'alloy-node-proxy'},
        rules=[{'api_groups': [''], 'resources': ['nodes/proxy'], 'verbs': ['get']}],
        opts=k8s_opts,
    )
    k8s.rbac.v1.ClusterRoleBinding(
        'alloy-node-proxy',
        metadata={'name': 'alloy-node-proxy'},
        role_ref={
            'api_group': 'rbac.authorization.k8s.io',
            'kind': 'ClusterRole',
            'name': role.metadata.name,
        },
        subjects=[{'kind': 'ServiceAccount', 'name': 'alloy', 'namespace': 'observability'}],
        opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[alloy])),
    )


def create_syslog_service(
    component_config: ComponentConfig,
    k8s_opts: p.ResourceOptions,
    alloy: k8s.helm.v3.Release,
):
    """Expose Alloy's syslog listeners on a fixed MetalLB address and a local DNS name."""
    syslog = component_config.alloy.syslog
    k8s.core.v1.Service(
        'alloy-syslog',
        metadata={
            'name': 'alloy-syslog',
            'annotations': {'metallb.io/loadBalancerIPs': syslog.address},
        },
        spec={
            'type': 'LoadBalancer',
            # Keeps the sender's address, which loadBalancerSourceRanges are matched against.
            'external_traffic_policy': 'Local',
            'load_balancer_source_ranges': syslog.allowed_sources,
            'selector': {
                'app.kubernetes.io/name': 'alloy',
                'app.kubernetes.io/instance': 'alloy',
            },
            'ports': [
                {'name': name, 'port': port, 'target_port': port, 'protocol': protocol}
                for name, port, protocol in _syslog_ports()
            ],
        },
        opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[alloy])),
    )
    utils.opnsense.dnsmasq.host.Host(
        'syslog',
        host=syslog.host,
        domain=component_config.zone,
        ipaddress=syslog.address,
    )
