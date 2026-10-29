"""Deploy Trivy Operator with workload image vulnerability scanning."""

import pulumi as p
import pulumi_kubernetes as k8s

from kubernetes.config import ComponentConfig

NAMESPACE = 'trivy-operator'
REPOSITORY = 'https://aquasecurity.github.io/helm-charts'


def create_trivy_operator(
    component_config: ComponentConfig, k8s_provider: k8s.Provider
) -> k8s.helm.v4.Chart:
    """Install a single-node, vulnerability-only Trivy Operator."""
    namespace = k8s.core.v1.Namespace(
        'trivy-operator',
        metadata={
            'name': NAMESPACE,
            'labels': {'pod-security.kubernetes.io/enforce': 'baseline'},
        },
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    namespaced_provider = k8s.Provider(
        'trivy-operator-provider',
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        namespace=namespace.metadata['name'],
    )
    return k8s.helm.v4.Chart(
        'trivy-operator',
        chart='trivy-operator',
        version=component_config.trivy_operator.version,
        namespace=namespace.metadata.name,
        repository_opts={'repo': REPOSITORY},
        values={
            'operator': {
                'namespace': NAMESPACE,
                'scanJobsConcurrentLimit': 1,
                'vulnerabilityScannerEnabled': True,
                'sbomGenerationEnabled': False,
                'configAuditScannerEnabled': False,
                'rbacAssessmentScannerEnabled': False,
                'infraAssessmentScannerEnabled': False,
                'exposedSecretScannerEnabled': False,
                'clusterComplianceEnabled': False,
                'metricsFindingsEnabled': True,
                'metricsVulnIdEnabled': False,
            },
            'trivy': {
                'mode': 'Standalone',
                'image': {'tag': '0.75.0'},
                'resources': {
                    'requests': {'cpu': '500m', 'memory': '512Mi'},
                    'limits': {'memory': '2Gi'},
                },
            },
            'compliance': {'specs': []},
            'serviceMonitor': {'enabled': False},
            'resources': {
                'requests': {'cpu': '100m', 'memory': '128Mi'},
                'limits': {'memory': '512Mi'},
            },
        },
        opts=p.ResourceOptions(
            provider=namespaced_provider,
            depends_on=[namespace],
        ),
    )
