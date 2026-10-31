import pulumi as p
import pulumi_kubernetes as k8s

_OBSERVABILITY_NAMESPACE = 'observability'


def _same_namespace(namespace: p.Input[str], app_name: str) -> dict:
    return {
        'namespace_selector': {'match_labels': {'kubernetes.io/metadata.name': namespace}},
        'pod_selector': {'match_labels': {'app.kubernetes.io/name': app_name}},
    }


def _observability_pod(app_name: str) -> dict:
    return {
        'namespace_selector': {
            'match_labels': {'kubernetes.io/metadata.name': _OBSERVABILITY_NAMESPACE}
        },
        'pod_selector': {'match_labels': {'app.kubernetes.io/name': app_name}},
    }


def create_network_policies(provider: k8s.Provider, namespace: p.Input[str]) -> None:
    """Restrict Wazuh ingress to its required in-cluster and agent traffic."""
    opts = p.ResourceOptions(provider=provider)
    k8s.networking.v1.NetworkPolicy(
        'wazuh-default-deny-ingress',
        metadata={'name': 'default-deny-ingress', 'namespace': namespace},
        spec={'pod_selector': {}, 'policy_types': ['Ingress']},
        opts=opts,
    )

    indexer_sources = [
        _same_namespace(namespace, 'wazuh-manager'),
        _same_namespace(namespace, 'wazuh-dashboard'),
        _same_namespace(namespace, 'wazuh-indexer-security'),
        _same_namespace(namespace, 'wazuh-indexer-exporter'),
        _same_namespace(namespace, 'wazuh-findings-exporter'),
        _observability_pod('grafana'),
    ]
    k8s.networking.v1.NetworkPolicy(
        'wazuh-indexer-ingress',
        metadata={'name': 'wazuh-indexer-ingress', 'namespace': namespace},
        spec={  # type: ignore[reportArgumentType]  # Nested Kubernetes input inference loses the generated spec type.
            'pod_selector': {'match_labels': {'app.kubernetes.io/name': 'wazuh-indexer'}},
            'policy_types': ['Ingress'],
            'ingress': [
                {'from_': indexer_sources, 'ports': [{'port': 9200, 'protocol': 'TCP'}]},
                {
                    'from_': [_same_namespace(namespace, 'wazuh-indexer')],
                    'ports': [{'port': 9300, 'protocol': 'TCP'}],
                },
            ],
        },
        opts=opts,
    )

    k8s.networking.v1.NetworkPolicy(
        'wazuh-manager-ingress',
        metadata={'name': 'wazuh-manager-ingress', 'namespace': namespace},
        spec={  # type: ignore[reportArgumentType]  # Nested Kubernetes input inference loses the generated spec type.
            'pod_selector': {'match_labels': {'app.kubernetes.io/name': 'wazuh-manager'}},
            'policy_types': ['Ingress'],
            'ingress': [
                {
                    'from_': [
                        {'ip_block': {'cidr': '10.10.0.0/16'}},
                        {'ip_block': {'cidr': '192.168.178.125/32'}},
                    ],
                    'ports': [
                        {'port': 1514, 'protocol': 'TCP'},
                        {'port': 1515, 'protocol': 'TCP'},
                    ],
                },
                {
                    'from_': [_same_namespace(namespace, 'wazuh-dashboard')],
                    'ports': [{'port': 55000, 'protocol': 'TCP'}],
                },
            ],
        },
        opts=opts,
    )

    k8s.networking.v1.NetworkPolicy(
        'wazuh-dashboard-ingress',
        metadata={'name': 'wazuh-dashboard-ingress', 'namespace': namespace},
        spec={
            'pod_selector': {'match_labels': {'app.kubernetes.io/name': 'wazuh-dashboard'}},
            'policy_types': ['Ingress'],
            'ingress': [
                {
                    'from_': [
                        {
                            'namespace_selector': {
                                'match_labels': {'kubernetes.io/metadata.name': 'traefik'}
                            }
                        }
                    ],
                    'ports': [{'port': 5601, 'protocol': 'TCP'}],
                }
            ],
        },
        opts=opts,
    )

    for resource_name, app_name, port in [
        ('wazuh-indexer-exporter-ingress', 'wazuh-indexer-exporter', 9114),
        ('wazuh-findings-exporter-ingress', 'wazuh-findings-exporter', 7979),
    ]:
        k8s.networking.v1.NetworkPolicy(
            resource_name,
            metadata={'name': resource_name, 'namespace': namespace},
            spec={  # type: ignore[reportArgumentType]  # Nested Kubernetes input inference loses the generated spec type.
                'pod_selector': {'match_labels': {'app.kubernetes.io/name': app_name}},
                'policy_types': ['Ingress'],
                'ingress': [
                    {
                        'from_': [_observability_pod('alloy')],
                        'ports': [{'port': port, 'protocol': 'TCP'}],
                    }
                ],
            },
            opts=opts,
        )
