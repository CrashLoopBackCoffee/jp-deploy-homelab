import typing as t

import pulumi as p
import requests

from utils.opnsense.base import OpnSenseBaseProvider


def _host_payload(props: dict[str, t.Any]) -> dict[str, t.Any]:
    return {
        'host': {
            'enabled': '1',
            'hostname': props['host'],
            'domain': props['domain'],
            'rr': 'A',
            'server': props['ipaddress'],
            'description': props.get('description') or '',
        },
    }


class HostProvider(OpnSenseBaseProvider):
    """Manages Unbound host overrides on OPNsense (Services: Unbound DNS: Overrides).

    For names that must resolve inside the network only and have no public record (ADR-0048).
    """

    def _reconfigure_unbound(self, client: requests.Session) -> None:
        response = client.post(self.get_api_path('unbound', 'service', 'reconfigure'), json={})
        response.raise_for_status()
        data = response.json()
        assert data.get('status') == 'ok', 'Failed to reconfigure unbound'

    def create(self, props: dict[str, t.Any]) -> p.dynamic.CreateResult:
        client = self.get_client()
        response = client.post(
            self.get_api_path('unbound', 'settings', 'addHostOverride'),
            json=_host_payload(props),
        )
        response.raise_for_status()
        data = response.json()
        assert data.get('result') == 'saved', f'Failed to create unbound host override: {data}'

        self._reconfigure_unbound(client)

        return p.dynamic.CreateResult(id_=data['uuid'], outs=props)

    def update(
        self,
        _id: str,
        _olds: dict[str, t.Any],
        _news: dict[str, t.Any],
    ) -> p.dynamic.UpdateResult:
        client = self.get_client()
        response = client.post(
            f'{self.get_api_path("unbound", "settings", "setHostOverride")}/{_id}',
            json=_host_payload(_news),
        )
        response.raise_for_status()
        data = response.json()
        assert data.get('result') == 'saved', f'Failed to update unbound host override: {data}'

        self._reconfigure_unbound(client)

        return p.dynamic.UpdateResult(outs=_news)

    def delete(self, _id: str, _props: dict[str, t.Any]) -> None:
        client = self.get_client()
        response = client.post(
            f'{self.get_api_path("unbound", "settings", "delHostOverride")}/{_id}',
            json={},
        )
        response.raise_for_status()
        data = response.json()
        assert data.get('result') == 'deleted', f'Failed to delete unbound host override: {data}'

        self._reconfigure_unbound(client)


class Host(p.dynamic.Resource):
    host: p.Output[str]
    domain: p.Output[str]
    ipaddress: p.Output[str]
    description: p.Output[str]

    def __init__(
        self,
        name: str,
        host: p.Input[str],
        domain: p.Input[str],
        ipaddress: p.Input[str],
        description: p.Input[str | None] = None,
        opts: p.ResourceOptions | None = None,
    ):
        super().__init__(
            HostProvider(),
            name,
            {
                'host': host,
                'domain': domain,
                'ipaddress': ipaddress,
                'description': description,
            },
            opts,
        )
