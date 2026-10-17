"""Probe and scrape targets for Alloy.

The list lives in a 1Password Secure Note, so that no customer or endpoint names are committed to
this public repository. Pulumi turns it into the Secret `alloy-targets`, which Alloy mounts and
watches with `discovery.file`: a changed list reaches Alloy without a restart.
"""

import json
import re
import typing as t

import pulumi as p
import pulumi_kubernetes as k8s

from observability.config import ComponentConfig

SECRET_NAME = 'alloy-targets'
MOUNT_PATH = '/etc/alloy-targets'

# Group in the note -> blackbox module. The Alloy config maps the group to the job name.
PROBE_MODULES = {'http': 'http_2xx', 'slow': 'http_2xx', 'icmp': 'icmp', 'tcp': 'tcp_connect'}
SCRAPE_GROUPS = ('ax51', 'pretix')


def parse_targets(note: str) -> dict[str, list[str]]:
    """Parse `<group> <target>` lines; lines starting with `#` and empty lines are ignored."""
    groups: dict[str, list[str]] = {group: [] for group in (*PROBE_MODULES, *SCRAPE_GROUPS)}
    for number, raw in enumerate(note.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        group, _, target = line.partition(' ')
        target = target.strip()
        if group not in groups or not target:
            raise ValueError(f'Monitoring Targets, line {number}: expected "<group> <target>"')
        groups[group].append(target)
    return groups


def _slug(group: str, target: str) -> str:
    return f'{group}-{re.sub(r"[^a-z0-9]+", "-", target.lower()).strip("-")}'


def probe_entries(groups: dict[str, list[str]]) -> list[dict[str, t.Any]]:
    """`discovery.file` entries for the blackbox exporter; `name` must be unique per target."""
    return [
        {
            'targets': [target],
            'labels': {'name': _slug(group, target), 'module': module, 'group': group},
        }
        for group, module in PROBE_MODULES.items()
        for target in groups[group]
    ]


def create_targets_secret(component_config: ComponentConfig, k8s_opts: p.ResourceOptions):
    alloy = component_config.alloy
    groups = alloy.targets.value.apply(parse_targets)

    string_data: dict[str, p.Input[str]] = {
        'blackbox-targets.json': groups.apply(lambda g: json.dumps(probe_entries(g))),
        'ax51-username': alloy.ax51.username.value,
        'ax51-password': alloy.ax51.password.value,
        'pretix-username': alloy.pretix.username.value,
        'pretix-password': alloy.pretix.password.value,
    }
    for group in SCRAPE_GROUPS:
        string_data[f'{group}-targets.json'] = groups.apply(
            lambda g, group=group: json.dumps([{'targets': g[group]}])
        )

    # A fixed name lets the mounted files update in place, which Alloy picks up without a restart.
    return k8s.core.v1.Secret(
        'alloy-targets',
        metadata={'name': SECRET_NAME},
        string_data=string_data,
        opts=k8s_opts,
    )
