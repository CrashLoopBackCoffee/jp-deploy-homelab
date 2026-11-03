"""The Thanos archive of curated Home Assistant sensors (services/thanos, ADR-0047)."""

# Services of the `thanos` stack; the chart prefixes its resources with `thanos-`.
RECEIVE_REMOTE_WRITE_URL = (
    'http://thanos-receive-router.thanos.svc.cluster.local:19291/api/v1/receive'
)
QUERY_URL = 'http://thanos-query.thanos.svc.cluster.local:10902'
THANOS_DATASOURCE_UID = 'thanos-archive'

# Home Assistant serves HTTPS only; OPNsense resolves the name (ADR-0048).
HOME_ASSISTANT_HOST = 'home-assistant.4jp.de'
