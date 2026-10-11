import typing as t

import pulumi as p
import requests

from utils.opnsense.base import OpnSenseBaseProvider


def _host_payload(props: dict[str, t.Any]) -> dict[str, t.Any]:
    return {
        'host': {
            'host': props['host'],
            'domain': props['domain'],
            'ip': props['ipaddress'],
            'descr': props.get('description') or '',
        },
    }


class HostProvider(OpnSenseBaseProvider):
    """Manages Dnsmasq DNS host records on OPNsense (Services: Dnsmasq DNS/DHCP)."""

    def _reconfigure_dnsmasq(self, client: requests.Session) -> None:
        response = client.post(self.get_api_path('dnsmasq', 'service', 'reconfigure'), json={})
        response.raise_for_status()
        data = response.json()
        assert data.get('status') == 'ok', 'Failed to reconfigure dnsmasq'

    def create(self, props: dict[str, t.Any]) -> p.dynamic.CreateResult:
        client = self.get_client()
        response = client.post(
            self.get_api_path('dnsmasq', 'settings', 'addHost'),
            json=_host_payload(props),
        )
        response.raise_for_status()
        data = response.json()
        assert data.get('result') == 'saved', f'Failed to create dnsmasq host: {data}'

        self._reconfigure_dnsmasq(client)

        return p.dynamic.CreateResult(id_=data['uuid'], outs=props)

    def update(
        self,
        _id: str,
        _olds: dict[str, t.Any],
        _news: dict[str, t.Any],
    ) -> p.dynamic.UpdateResult:
        client = self.get_client()
        response = client.post(
            f'{self.get_api_path("dnsmasq", "settings", "setHost")}/{_id}',
            json=_host_payload(_news),
        )
        response.raise_for_status()
        data = response.json()
        assert data.get('result') == 'saved', f'Failed to update dnsmasq host: {data}'

        self._reconfigure_dnsmasq(client)

        return p.dynamic.UpdateResult(outs=_news)

    def delete(self, _id: str, _props: dict[str, t.Any]) -> None:
        client = self.get_client()
        response = client.post(
            f'{self.get_api_path("dnsmasq", "settings", "delHost")}/{_id}',
            json={},
        )
        response.raise_for_status()
        data = response.json()
        assert data.get('result') == 'deleted', f'Failed to delete dnsmasq host: {data}'

        self._reconfigure_dnsmasq(client)


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
