import hashlib

import bcrypt
import pulumi as p
import pulumi_kubernetes as k8s
import pulumi_random as random
import pulumi_tls as tls

_USERS = {
    'admin': ('admin-password', True, ['admin']),
    'kibanaserver': ('dashboard-password', True, []),
    'grafana_reader': ('grafana-reader-password', False, ['wazuh_grafana_reader']),
    'metrics_reader': ('metrics-reader-password', False, ['wazuh_metrics_reader']),
}
_SERVICE_USERS = {
    'api': 'api-password',
    'enrollment': 'enrollment-password',
}


def _bcrypt_salt(seed: str) -> str:
    alphabet = './ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    data = hashlib.sha256(seed.encode()).digest()[:16]
    encoded = []
    for offset in range(0, len(data), 3):
        first = data[offset]
        second = data[offset + 1] if offset + 1 < len(data) else 0
        third = data[offset + 2] if offset + 2 < len(data) else 0
        encoded.append(alphabet[first >> 2])
        encoded.append(alphabet[((first & 3) << 4) | (second >> 4)])
        if offset + 1 < len(data):
            encoded.append(alphabet[((second & 15) << 2) | (third >> 6)])
        if offset + 2 < len(data):
            encoded.append(alphabet[third & 63])
    return ''.join(encoded)


def _hash(password: p.Output[str], salt_seed: p.Output[str]) -> p.Output[str]:
    return p.Output.all(password, salt_seed).apply(
        lambda values: bcrypt.hashpw(
            values[0].encode(), f'$2b$12${_bcrypt_salt(values[1])}'.encode()
        ).decode()
    )


def create_pki(
    config, provider: k8s.Provider, namespace: p.Input[str]
) -> tuple[k8s.core.v1.Secret, k8s.core.v1.Secret]:
    opts = p.ResourceOptions(provider=provider)
    ca_key = tls.PrivateKey('wazuh-ca-key', algorithm='RSA', rsa_bits=4096)
    ca_cert = tls.SelfSignedCert(
        'wazuh-ca-cert',
        private_key_pem=ca_key.private_key_pem_pkcs8,
        subject={'common_name': 'Wazuh Internal CA', 'organization': 'Homelab'},
        validity_period_hours=87600,
        is_ca_certificate=True,
        allowed_uses=['cert_signing', 'crl_signing', 'digital_signature'],
    )
    ca_secret = k8s.core.v1.Secret(
        'wazuh-ca-secret',
        metadata={'name': 'wazuh-ca', 'namespace': namespace},
        string_data={
            'tls.crt': ca_cert.cert_pem,
            'tls.key': ca_key.private_key_pem_pkcs8,
            'ca.crt': ca_cert.cert_pem,
        },
        type='kubernetes.io/tls',
        opts=opts,
    )
    issuer = k8s.apiextensions.CustomResource(
        'wazuh-ca-issuer',
        api_version='cert-manager.io/v1',
        kind='Issuer',
        metadata={'name': 'wazuh-ca', 'namespace': namespace},
        spec={'ca': {'secretName': 'wazuh-ca'}},
        opts=p.ResourceOptions.merge(opts, p.ResourceOptions(depends_on=[ca_secret])),
    )

    leaf_names = {
        'wazuh-indexer': [
            'wazuh-indexer',
            f'wazuh-indexer.{config.namespace}.svc',
            f'wazuh-indexer.{config.namespace}.svc.cluster.local',
        ],
        'wazuh-manager': [
            'wazuh-manager',
            f'wazuh-manager.{config.namespace}.svc',
            f'wazuh-manager.{config.namespace}.svc.cluster.local',
            config.manager_hostname,
        ],
        'wazuh-dashboard': [
            config.dashboard_hostname,
            'wazuh-dashboard',
            f'wazuh-dashboard.{config.namespace}.svc.cluster.local',
        ],
        'wazuh-admin': ['wazuh-admin'],
        'wazuh-filebeat': ['wazuh-filebeat'],
        'wazuh-grafana-reader': ['wazuh-grafana-reader'],
        'wazuh-metrics-reader': ['wazuh-metrics-reader'],
    }
    for name, dns_names in leaf_names.items():
        k8s.apiextensions.CustomResource(
            f'{name}-certificate',
            api_version='cert-manager.io/v1',
            kind='Certificate',
            metadata={'name': name, 'namespace': namespace},
            spec={
                'secretName': name,
                'commonName': name,
                'dnsNames': dns_names,
                'usages': [
                    'digital signature',
                    'key encipherment',
                    'server auth',
                    'client auth',
                ],
                'privateKey': {
                    'algorithm': 'RSA',
                    'size': 2048,
                    'encoding': 'PKCS8',
                    'rotationPolicy': 'Always',
                },
                'issuerRef': {'name': 'wazuh-ca', 'kind': 'Issuer', 'group': 'cert-manager.io'},
                'renewBefore': '720h',
            },
            opts=p.ResourceOptions.merge(opts, p.ResourceOptions(depends_on=[issuer])),
        )

    passwords = {
        name: random.RandomPassword(f'wazuh-{key}', length=32, special=False).result
        for name, (key, _, _) in _USERS.items()
    }
    service_passwords = {
        name: random.RandomPassword(f'wazuh-{key}', length=32, special=False).result
        for name, key in _SERVICE_USERS.items()
    }
    hash_salts = {
        name: random.RandomPassword(
            f'wazuh-{name}-bcrypt-salt',
            length=32,
            special=False,
        ).result
        for name in passwords
    }
    hashes = {name: _hash(password, hash_salts[name]) for name, password in passwords.items()}
    internal_users = p.Output.all(**hashes).apply(
        lambda values: (
            '---\n_meta:\n  type: "internalusers"\n  config_version: 2\n'
            + ''.join(
                f'\n{name}:\n  hash: "{values[name]}"\n  reserved: {str(reserved).lower()}\n'
                + (f'  backend_roles: {roles!r}\n' if roles else '')
                for name, (_, reserved, roles) in _USERS.items()
            )
        )
    )
    credentials = k8s.core.v1.Secret(
        'wazuh-credentials',
        metadata={'name': 'wazuh-credentials', 'namespace': namespace},
        string_data={
            **passwords,
            **service_passwords,
            'internal_users.yml': internal_users,
        },
        type='Opaque',
        opts=opts,
    )
    p.export('ca_pem', ca_cert.cert_pem)
    for name, password in {**passwords, **service_passwords}.items():
        p.export(f'{name}_password', p.Output.secret(password))
    return ca_secret, credentials
