import pulumi as p
import pulumi_kubernetes as k8s

from kubernetes.config import ComponentConfig


def create_traefik(
    component_config: ComponentConfig,
    issuer: k8s.apiextensions.CustomResource,
    k8s_provider: k8s.Provider,
):
    namespace = k8s.core.v1.Namespace(
        'traefik',
        metadata={
            'name': 'traefik',
        },
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    namespaced_k8s_provider = k8s.Provider(
        'traefik',
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        namespace=namespace.metadata.name,
    )
    k8s_opts = p.ResourceOptions(provider=namespaced_k8s_provider)

    k8s.helm.v4.Chart(
        'traefik',
        chart='traefik',
        namespace=namespace.metadata.name,
        version=component_config.traefik.version,
        repository_opts={
            'repo': 'https://traefik.github.io/charts',
        },
        values={
            'additionalArguments': [
                # expose the API directly from the pod to allow getting access to dashboard at
                # http://localhost:8080/ after kubectl port-forwarding:
                '--api.insecure=true',
            ]
        },
        opts=k8s_opts,
    )

    wildcard_domain = f'*.{component_config.cloudflare.zone}'
    certificate = k8s.apiextensions.CustomResource(
        'certificate',
        api_version='cert-manager.io/v1',
        kind='Certificate',
        metadata={
            'name': 'certificate',
            'annotations': {
                # wait for certificate to be issued before starting deployment (and hence application
                # containers):
                'pulumi.com/waitFor': 'condition=Ready',
            },
        },
        spec={
            'secretName': 'certificate',
            'dnsNames': [wildcard_domain],
            'issuerRef': {'name': 'lets-encrypt', 'kind': 'ClusterIssuer'},
        },
        opts=p.ResourceOptions.merge(k8s_opts, p.ResourceOptions(depends_on=[issuer])),
    )

    # use this certificate as traefik's new default:
    k8s.apiextensions.CustomResource(
        'default',
        api_version='traefik.io/v1alpha1',
        kind='TLSStore',
        metadata={'name': 'default'},
        spec={
            'defaultCertificate': {
                'secretName': certificate.spec.apply(lambda spec: spec['secretName']),  # type: ignore
            }
        },
        opts=k8s_opts,
    )
