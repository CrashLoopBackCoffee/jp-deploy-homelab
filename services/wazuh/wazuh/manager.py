"""Provision the Wazuh standalone manager, API, and restricted agent endpoint."""

import hashlib

import pulumi as p
import pulumi_cloudflare as cloudflare
import pulumi_kubernetes as k8s
import utils.cloudflare

from wazuh.config import ComponentConfig

_ALERTS_TAIL = 'exec tail -n 0 -F /var/ossec/logs/alerts/alerts.json'
_LOG_TAIL = 'exec tail -n 0 -F /var/ossec/logs/ossec.log'


def _secret_env(name: str, key: str) -> dict[str, object]:
    return {
        'name': name,
        'valueFrom': {
            'secretKeyRef': {'name': 'wazuh-credentials', 'key': key},
        },
    }


def create_manager(
    config: ComponentConfig,
    provider: k8s.Provider,
    namespace: p.Input[str],
    credentials: k8s.core.v1.Secret,
    cloudflare_provider: cloudflare.Provider,
) -> None:
    """Create the persistent standalone manager and source-restricted agent endpoint."""
    opts = p.ResourceOptions(provider=provider)
    indexer_url = f'https://wazuh-indexer.{config.namespace}.svc:9200'
    ossec_conf = f"""<ossec_config>
  <global>
    <jsonout_output>yes</jsonout_output>
    <alerts_log>yes</alerts_log>
    <logall>no</logall>
    <logall_json>no</logall_json>
    <email_notification>no</email_notification>
    <queue_size>131072</queue_size>
  </global>
  <alerts>
    <log_alert_level>3</log_alert_level>
    <email_alert_level>12</email_alert_level>
  </alerts>
  <logging>
    <log_format>plain</log_format>
  </logging>
  <remote>
    <connection>secure</connection>
    <port>1514</port>
    <protocol>tcp</protocol>
    <queue_size>131072</queue_size>
  </remote>
  <wodle name="syscollector">
    <disabled>no</disabled>
    <interval>1h</interval>
    <scan_on_start>yes</scan_on_start>
    <hardware>yes</hardware>
    <os>yes</os>
    <network>yes</network>
    <packages>yes</packages>
    <ports all="yes">yes</ports>
    <processes>yes</processes>
  </wodle>
  <vulnerability-detection>
    <enabled>yes</enabled>
    <index-status>yes</index-status>
    <feed-update-interval>60m</feed-update-interval>
  </vulnerability-detection>

  <ruleset>
    <decoder_dir>ruleset/decoders</decoder_dir>
    <rule_dir>ruleset/rules</rule_dir>
    <rule_exclude>0215-policy_rules.xml</rule_exclude>
    <list>etc/lists/audit-keys</list>
    <list>etc/lists/amazon/aws-sources</list>
    <list>etc/lists/amazon/aws-eventnames</list>
    <list>etc/lists/malicious-ioc/malicious-ip</list>
    <list>etc/lists/malicious-ioc/malicious-domains</list>
    <list>etc/lists/malicious-ioc/malware-hashes</list>
    <decoder_dir>etc/decoders</decoder_dir>
    <rule_dir>etc/rules</rule_dir>
  </ruleset>

  <indexer>
    <enabled>yes</enabled>
    <hosts>
      <host>{indexer_url}</host>
    </hosts>
    <ssl>
      <certificate_authorities>
        <ca>/etc/ssl/root-ca.pem</ca>
      </certificate_authorities>
      <certificate>/etc/ssl/filebeat.pem</certificate>
      <key>/etc/ssl/filebeat.key</key>
    </ssl>
  </indexer>
  <auth>
    <disabled>no</disabled>
    <port>1515</port>
    <use_source_ip>no</use_source_ip>
    <use_password>yes</use_password>
    <ssl_manager_cert>/var/ossec/etc/sslmanager.cert</ssl_manager_cert>
    <ssl_manager_key>/var/ossec/etc/sslmanager.key</ssl_manager_key>
  </auth>
</ossec_config>
"""
    manager_config = k8s.core.v1.ConfigMap(
        'wazuh-manager-config',
        metadata={'name': 'wazuh-manager-config', 'namespace': namespace},
        data={'ossec.conf': ossec_conf},
        opts=opts,
    )

    labels = {'app.kubernetes.io/name': 'wazuh-manager'}
    stateful_set = k8s.apps.v1.StatefulSet(
        'wazuh-manager',
        metadata={'name': 'wazuh-manager', 'namespace': namespace},
        spec={  # type: ignore
            'serviceName': 'wazuh-manager-headless',
            'replicas': 1,
            'selector': {'matchLabels': labels},
            'template': {
                'metadata': {
                    'labels': labels,
                    'annotations': {
                        'checksum/manager-config': hashlib.sha256(ossec_conf.encode()).hexdigest(),
                        'checksum/credentials': credentials.data.apply(
                            lambda data: hashlib.sha256(data['admin'].encode()).hexdigest()
                        ),
                    },
                },
                'spec': {
                    'securityContext': {'fsGroup': 101},
                    'initContainers': [
                        {
                            'name': 'seed-manager-state',
                            'image': f'wazuh/wazuh-manager:{config.version}',
                            'command': [
                                '/bin/sh',
                                '-c',
                                'set -eu; '
                                'if [ ! -f /state/etc/shared/ar.conf ]; then '
                                'mkdir -p /state/etc; '
                                'cp -a /var/ossec/etc/. /state/etc/; '
                                'fi; '
                                'if [ ! -f /state/api/configuration/api.yaml ]; then '
                                'mkdir -p /state/api/configuration; '
                                'cp -a /var/ossec/api/configuration/. /state/api/configuration/; '
                                'fi; '
                                'mkdir -p /state/api/configuration/ssl; '
                                'cp /run/wazuh-api-cert/server.crt /state/api/configuration/ssl/server.crt; '
                                'cp /run/wazuh-api-cert/server.key /state/api/configuration/ssl/server.key; '
                                'chmod 640 /state/api/configuration/ssl/server.key',
                            ],
                            'volumeMounts': [
                                {'name': 'manager-data', 'mountPath': '/state'},
                                {
                                    'name': 'manager-api-cert',
                                    'mountPath': '/run/wazuh-api-cert',
                                    'readOnly': True,
                                },
                            ],
                        },
                        {
                            'name': 'configure-indexer-keystore',
                            'image': f'wazuh/wazuh-manager:{config.version}',
                            'command': [
                                '/bin/sh',
                                '-c',
                                'set -eu; '
                                'printf \'%s\\n\' "$INDEXER_USERNAME" | '
                                '/var/ossec/bin/wazuh-keystore -f indexer -k username; '
                                'printf \'%s\\n\' "$INDEXER_PASSWORD" | '
                                '/var/ossec/bin/wazuh-keystore -f indexer -k password',
                            ],
                            'env': [
                                {'name': 'INDEXER_USERNAME', 'value': 'admin'},
                                _secret_env('INDEXER_PASSWORD', 'admin'),
                            ],
                            'volumeMounts': [
                                {
                                    'name': 'manager-data',
                                    'mountPath': '/var/ossec/etc',
                                    'subPath': 'etc',
                                },
                            ],
                        },
                    ],
                    'containers': [
                        {
                            'name': 'manager',
                            'image': f'wazuh/wazuh-manager:{config.version}',
                            'ports': [
                                {'name': 'agents', 'containerPort': 1514, 'protocol': 'TCP'},
                                {
                                    'name': 'enrollment',
                                    'containerPort': 1515,
                                    'protocol': 'TCP',
                                },
                                {'name': 'api', 'containerPort': 55000, 'protocol': 'TCP'},
                            ],
                            'env': [
                                {'name': 'INDEXER_URL', 'value': indexer_url},
                                {'name': 'INDEXER_USERNAME', 'value': 'admin'},
                                _secret_env('INDEXER_PASSWORD', 'admin'),
                                {'name': 'FILEBEAT_SSL_VERIFICATION_MODE', 'value': 'full'},
                                {
                                    'name': 'SSL_CERTIFICATE_AUTHORITIES',
                                    'value': '/etc/ssl/root-ca.pem',
                                },
                                {'name': 'SSL_CERTIFICATE', 'value': '/etc/ssl/filebeat.pem'},
                                {'name': 'SSL_KEY', 'value': '/etc/ssl/filebeat.key'},
                                {'name': 'API_USERNAME', 'value': 'wazuh-wui'},
                                _secret_env('API_PASSWORD', 'api'),
                            ],
                            'resources': {
                                'requests': {'cpu': '500m', 'memory': '1536Mi'},
                                'limits': {'memory': '3Gi'},
                            },
                            'securityContext': {
                                'allowPrivilegeEscalation': False,
                                'capabilities': {'add': ['SYS_CHROOT']},
                            },
                            'volumeMounts': [
                                {
                                    'name': 'manager-config',
                                    'mountPath': '/wazuh-config-mount/etc/ossec.conf',
                                    'subPath': 'ossec.conf',
                                    'readOnly': True,
                                },
                                {
                                    'name': 'manager-data',
                                    'mountPath': '/var/ossec/api/configuration',
                                    'subPath': 'api/configuration',
                                },
                                {
                                    'name': 'manager-data',
                                    'mountPath': '/var/ossec/etc',
                                    'subPath': 'etc',
                                },
                                {
                                    'name': 'manager-data',
                                    'mountPath': '/var/ossec/logs',
                                    'subPath': 'logs',
                                },
                                {
                                    'name': 'manager-data',
                                    'mountPath': '/var/ossec/queue',
                                    'subPath': 'queue',
                                },
                                {
                                    'name': 'manager-data',
                                    'mountPath': '/var/ossec/var/multigroups',
                                    'subPath': 'var/multigroups',
                                },
                                {
                                    'name': 'manager-data',
                                    'mountPath': '/var/ossec/integrations',
                                    'subPath': 'integrations',
                                },
                                {
                                    'name': 'manager-data',
                                    'mountPath': '/var/ossec/active-response/bin',
                                    'subPath': 'active-response/bin',
                                },
                                {
                                    'name': 'manager-data',
                                    'mountPath': '/var/ossec/agentless',
                                    'subPath': 'agentless',
                                },
                                {
                                    'name': 'manager-data',
                                    'mountPath': '/var/ossec/wodles',
                                    'subPath': 'wodles',
                                },
                                {
                                    'name': 'manager-data',
                                    'mountPath': '/etc/filebeat',
                                    'subPath': 'filebeat/etc',
                                },
                                {
                                    'name': 'manager-data',
                                    'mountPath': '/var/lib/filebeat',
                                    'subPath': 'filebeat/var',
                                },
                                {
                                    'name': 'ca-cert',
                                    'mountPath': '/etc/ssl/root-ca.pem',
                                    'subPath': 'root-ca.pem',
                                    'readOnly': True,
                                },
                                {
                                    'name': 'filebeat-cert',
                                    'mountPath': '/etc/ssl/filebeat.pem',
                                    'subPath': 'filebeat.pem',
                                    'readOnly': True,
                                },
                                {
                                    'name': 'filebeat-cert',
                                    'mountPath': '/etc/ssl/filebeat.key',
                                    'subPath': 'filebeat.key',
                                    'readOnly': True,
                                },
                                {
                                    'name': 'manager-cert',
                                    'mountPath': '/var/ossec/etc/sslmanager.cert',
                                    'subPath': 'manager.crt',
                                    'readOnly': True,
                                },
                                {
                                    'name': 'manager-cert',
                                    'mountPath': '/var/ossec/etc/sslmanager.key',
                                    'subPath': 'manager.key',
                                    'readOnly': True,
                                },
                                {
                                    'name': 'authd-password',
                                    'mountPath': '/var/ossec/etc/authd.pass',
                                    'subPath': 'authd.pass',
                                    'readOnly': True,
                                },
                            ],
                            'readinessProbe': {
                                'tcpSocket': {'port': 55000},
                                'periodSeconds': 10,
                                'failureThreshold': 6,
                            },
                            'startupProbe': {
                                'tcpSocket': {'port': 55000},
                                'periodSeconds': 10,
                                'failureThreshold': 60,
                            },
                        },
                        {
                            'name': 'alerts-tail',
                            'image': 'busybox:1.37.0',
                            'command': ['/bin/sh', '-c', _ALERTS_TAIL],
                            'resources': {
                                'requests': {'cpu': '10m', 'memory': '16Mi'},
                                'limits': {'memory': '32Mi'},
                            },
                            'securityContext': {
                                'allowPrivilegeEscalation': False,
                                'readOnlyRootFilesystem': True,
                                'runAsNonRoot': True,
                                'runAsUser': 1000,
                                'runAsGroup': 999,
                            },
                            'volumeMounts': [
                                {
                                    'name': 'manager-data',
                                    'mountPath': '/var/ossec/logs',
                                    'subPath': 'logs',
                                    'readOnly': True,
                                },
                            ],
                        },
                        {
                            'name': 'ossec-log-tail',
                            'image': 'busybox:1.37.0',
                            'command': ['/bin/sh', '-c', _LOG_TAIL],
                            'resources': {
                                'requests': {'cpu': '10m', 'memory': '16Mi'},
                                'limits': {'memory': '32Mi'},
                            },
                            'securityContext': {
                                'allowPrivilegeEscalation': False,
                                'readOnlyRootFilesystem': True,
                                'runAsNonRoot': True,
                                'runAsUser': 1000,
                                'runAsGroup': 999,
                            },
                            'volumeMounts': [
                                {
                                    'name': 'manager-data',
                                    'mountPath': '/var/ossec/logs',
                                    'subPath': 'logs',
                                    'readOnly': True,
                                },
                            ],
                        },
                    ],
                    'volumes': [
                        {
                            'name': 'manager-config',
                            'configMap': {'name': manager_config.metadata.name},
                        },
                        {
                            'name': 'ca-cert',
                            'secret': {
                                'secretName': 'wazuh-ca',
                                'items': [{'key': 'ca.crt', 'path': 'root-ca.pem'}],
                            },
                        },
                        {
                            'name': 'filebeat-cert',
                            'secret': {
                                'secretName': 'wazuh-filebeat',
                                'items': [
                                    {'key': 'tls.crt', 'path': 'filebeat.pem'},
                                    {'key': 'tls.key', 'path': 'filebeat.key'},
                                ],
                            },
                        },
                        {
                            'name': 'manager-cert',
                            'secret': {
                                'secretName': 'wazuh-manager',
                                'items': [
                                    {'key': 'tls.crt', 'path': 'manager.crt'},
                                    {'key': 'tls.key', 'path': 'manager.key'},
                                ],
                            },
                        },
                        {
                            'name': 'manager-api-cert',
                            'secret': {
                                'secretName': 'wazuh-manager',
                                'items': [
                                    {'key': 'tls.crt', 'path': 'server.crt'},
                                    {'key': 'tls.key', 'path': 'server.key'},
                                ],
                            },
                        },
                        {
                            'name': 'authd-password',
                            'secret': {
                                'secretName': 'wazuh-credentials',
                                'items': [{'key': 'enrollment', 'path': 'authd.pass'}],
                                'defaultMode': 288,
                            },
                        },
                    ],
                },
            },
            'volumeClaimTemplates': [
                {
                    'metadata': {
                        'name': 'manager-data',
                        'labels': {'recurring-job-group.longhorn.io/default': 'enabled'},
                    },
                    'spec': {
                        'accessModes': ['ReadWriteOnce'],
                        'resources': {'requests': {'storage': config.manager_storage}},
                    },
                },
            ],
        },
        opts=p.ResourceOptions.merge(
            opts,
            p.ResourceOptions(depends_on=[manager_config, credentials]),
        ),
    )

    k8s.core.v1.Service(
        'wazuh-manager-headless',
        metadata={'name': 'wazuh-manager-headless', 'namespace': namespace},
        spec={'clusterIP': 'None', 'selector': labels, 'ports': [{'name': 'api', 'port': 55000}]},  # type: ignore
        opts=p.ResourceOptions.merge(opts, p.ResourceOptions(depends_on=[stateful_set])),
    )
    k8s.core.v1.Service(
        'wazuh-manager',
        metadata={'name': 'wazuh-manager', 'namespace': namespace},
        spec={  # type: ignore
            'type': 'ClusterIP',
            'selector': labels,
            'ports': [{'name': 'api', 'port': 55000, 'targetPort': 55000}],
        },
        opts=p.ResourceOptions.merge(opts, p.ResourceOptions(depends_on=[stateful_set])),
    )
    k8s.core.v1.Service(
        'wazuh-manager-internal',
        metadata={'name': 'wazuh-manager-internal', 'namespace': namespace},
        spec={  # type: ignore
            'type': 'ClusterIP',
            'selector': labels,
            'ports': [
                {'name': 'agents', 'port': 1514, 'targetPort': 1514, 'protocol': 'TCP'},
                {
                    'name': 'enrollment',
                    'port': 1515,
                    'targetPort': 1515,
                    'protocol': 'TCP',
                },
            ],
        },
        opts=p.ResourceOptions.merge(opts, p.ResourceOptions(depends_on=[stateful_set])),
    )
    k8s.core.v1.Service(
        'wazuh-manager-agents',
        metadata={'name': 'wazuh-manager-agents', 'namespace': namespace},
        spec={  # type: ignore
            'type': 'LoadBalancer',
            'loadBalancerIP': config.agent_address,
            'loadBalancerSourceRanges': ['10.10.0.0/16', '192.168.178.125/32'],
            'externalTrafficPolicy': 'Local',
            'selector': labels,
            'ports': [
                {'name': 'agents', 'port': 1514, 'targetPort': 1514, 'protocol': 'TCP'},
                {
                    'name': 'enrollment',
                    'port': 1515,
                    'targetPort': 1515,
                    'protocol': 'TCP',
                },
            ],
        },
        opts=p.ResourceOptions.merge(opts, p.ResourceOptions(depends_on=[stateful_set])),
    )

    # The stack creates one Cloudflare provider and shares it across records.
    utils.cloudflare.create_a_record(
        'wazuh-manager-dns',
        host=config.manager_hostname.removesuffix(f'.{config.zone}'),
        zone_name=config.zone,
        address=config.agent_address,
        cloudflare_provider=cloudflare_provider,
    )
