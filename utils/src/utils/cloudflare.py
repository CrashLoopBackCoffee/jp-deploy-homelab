import pulumi as p
import pulumi_cloudflare as cloudflare

from utils.model import CloudflareConfig


def get_provider(config: CloudflareConfig) -> cloudflare.Provider:
    return cloudflare.Provider(
        'cloudflare',
        api_key=config.api_key.value,
        email=config.email,
    )


def get_zone(
    name: str, cloudflare_provider: cloudflare.Provider
) -> p.Output[cloudflare.GetZoneResult]:
    return cloudflare.get_zone_output(
        filter={'match': 'all', 'name': name},
        opts=p.InvokeOptions(provider=cloudflare_provider),
    )


def create_cloudflare_cname(
    name: str, zone_name: str, cloudflare_provider: cloudflare.Provider
) -> cloudflare.DnsRecord:
    zone = cloudflare.get_zone_output(
        filter={'match': 'all', 'name': zone_name},
        opts=p.InvokeOptions(provider=cloudflare_provider),
    )

    return cloudflare.DnsRecord(
        name,
        proxied=False,
        name=name,
        type='CNAME',
        content=f'home.{zone_name}',
        ttl=60,
        zone_id=zone.zone_id,
        opts=p.ResourceOptions(provider=cloudflare_provider),
    )


def get_token_provider(api_token: p.Input[str]) -> cloudflare.Provider:
    """Provider for a scoped account API token (DNS Edit and Zone Read), see ADR-0010."""
    return cloudflare.Provider('cloudflare', api_token=api_token)


def create_a_record(
    resource_name: str,
    *,
    host: str,
    zone_name: str,
    address: p.Input[str],
    cloudflare_provider: cloudflare.Provider,
    opts: p.ResourceOptions | None = None,
) -> cloudflare.DnsRecord:
    """A record in the public zone that points at a private cluster address (ADR-0029).

    Never proxied: Cloudflare cannot reach a private address, and the name is only useful on the LAN.
    """
    zone = get_zone(zone_name, cloudflare_provider)
    return cloudflare.DnsRecord(
        resource_name,
        zone_id=zone.zone_id,
        name=f'{host}.{zone_name}',
        type='A',
        content=address,
        proxied=False,
        ttl=1,  # automatic
        opts=p.ResourceOptions.merge(p.ResourceOptions(provider=cloudflare_provider), opts),
    )
