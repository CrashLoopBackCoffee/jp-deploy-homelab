import pulumi as p
import pulumi_kubernetes as k8s

LONGHORN_MANAGER_METRICS_PORT = 9500


def create_longhorn_metrics_access(k8s_provider: k8s.Provider):
    """Let Alloy scrape Longhorn's manager.

    The Longhorn chart ships NetworkPolicies that admit only Longhorn's own pods to the manager.
    Policies are additive, so this one opens a single port to a single workload.
    """
    return k8s.networking.v1.NetworkPolicy(
        'allow-alloy-to-longhorn-manager',
        metadata={'name': 'allow-alloy-metrics-scrape', 'namespace': 'longhorn-system'},
        spec={
            'pod_selector': {'match_labels': {'app': 'longhorn-manager'}},
            'policy_types': ['Ingress'],
            'ingress': [
                {
                    'from_': [
                        {
                            'namespace_selector': {
                                'match_labels': {'kubernetes.io/metadata.name': 'observability'},
                            },
                            'pod_selector': {'match_labels': {'app.kubernetes.io/name': 'alloy'}},
                        },
                    ],
                    'ports': [{'port': LONGHORN_MANAGER_METRICS_PORT, 'protocol': 'TCP'}],
                },
            ],
        },
        opts=p.ResourceOptions(provider=k8s_provider),
    )
