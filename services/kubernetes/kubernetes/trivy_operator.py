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
                # Standalone scan jobs run one container per image in parallel on a shared cache, so
                # multi-container workloads fail with "cache may be in use by another process".
                # The built-in server owns one database and cache for all scans.
                'builtInTrivyServer': True,
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
                'mode': 'ClientServer',
                'image': {'tag': component_config.trivy_operator.trivy_image_version},
                'resources': {
                    'requests': {'cpu': '500m', 'memory': '512Mi'},
                    'limits': {'memory': '2Gi'},
                },
                'server': {
                    'resources': {
                        'requests': {'cpu': '200m', 'memory': '512Mi'},
                        # None deletes the chart default `cpu: 1` (no CPU limits)
                        'limits': {'cpu': None, 'memory': '1Gi'},
                    },
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
