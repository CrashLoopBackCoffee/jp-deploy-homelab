import pulumi as p
import pulumi_kubernetes as k8s

from kubernetes.config import ComponentConfig


def create_certmanager(
    component_config: ComponentConfig,
    k8s_provider: k8s.Provider,
) -> k8s.apiextensions.CustomResource:
    namespace = k8s.core.v1.Namespace(
        'cert-manager',
        metadata={'name': 'cert-manager'},
        opts=p.ResourceOptions(provider=k8s_provider),
    )

    namespaced_k8s_provider = k8s.Provider(
        'cert-manager-provider',
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        namespace=namespace.metadata['name'],
    )
    k8s_opts = p.ResourceOptions(provider=namespaced_k8s_provider)

    # Note we use Release instead of Chart in order to have one resource instead of 25
    chart = k8s.helm.v3.Release(
        'cert-manager',
        chart='cert-manager',
        version=component_config.cert_manager.version,
        namespace=namespace.metadata.name,
        repository_opts={'repo': 'https://charts.jetstack.io'},
        values={
            'crds': {
                'enabled': True,
            },
            # The LAN resolver (dnsmasq) is authoritative for the zone and answers NXDOMAIN for
            # the ACME TXT record, so the DNS-01 self-check must ask public resolvers.
            'extraArgs': [
                '--dns01-recursive-nameservers-only',
                '--dns01-recursive-nameservers=1.1.1.1:53,1.0.0.1:53',
            ],
        },
        opts=k8s_opts,
    )

    k8s_opts = p.ResourceOptions(provider=k8s_provider, depends_on=[chart])

    # Cloudflare DNS API Secret
    cloudflare_secret = k8s.core.v1.Secret(
        'cloudflare-api-token',
        metadata={'namespace': 'cert-manager'},
        type='Opaque',
        string_data={'api-token': component_config.cloudflare.api_token.value},
        opts=k8s_opts,
    )

    # Issuer
    return k8s.apiextensions.CustomResource(
        'letsencrypt-issuer',
        api_version='cert-manager.io/v1',
        kind='ClusterIssuer',
        metadata={'namespace': 'cert-manager', 'name': 'lets-encrypt'},
        spec={
            'acme': {
                'server': component_config.cert_manager.issuer_server,
                'email': component_config.cert_manager.acme_email,
                'privateKeySecretRef': {'name': 'lets-encrypt-private-key'},
                'solvers': [
                    {
                        'dns01': {
                            'cloudflare': {
                                'apiTokenSecretRef': {
                                    'name': cloudflare_secret.metadata.name,
                                    'key': 'api-token',
                                },
                            },
                        },
                    },
                ],
            },
        },
        opts=k8s_opts,
    )
