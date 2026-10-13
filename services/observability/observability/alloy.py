import pathlib

import pulumi as p
import pulumi_kubernetes as k8s

from observability.config import ComponentConfig
from observability.loki import LOKI_GATEWAY_URL
from observability.mimir import MIMIR_GATEWAY_URL

ALLOY_CONFIG = pathlib.Path(__file__).parent.parent / 'assets' / 'alloy' / 'config.alloy'


def create_alloy(
    component_config: ComponentConfig,
    k8s_opts: p.ResourceOptions,
    depends_on: list[p.Resource],
):
    """One collector for cluster metrics and logs; single node, so a single replica suffices."""
    config = ALLOY_CONFIG.read_text()
    config = config.replace('MIMIR_PUSH_URL', f'{MIMIR_GATEWAY_URL}/api/v1/push')
    config = config.replace('LOKI_PUSH_URL', f'{LOKI_GATEWAY_URL}/loki/api/v1/push')

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
