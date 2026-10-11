---
type: Service
title: Kubernetes platform stack (Pulumi, prod)
description: What the Kubernetes Pulumi stack deploys on k0s, how it is configured, and how secrets, DNS, and certificates flow.
timestamp: 2026-10-10T20:00:00Z
tags: [homelab, kubernetes, pulumi, metallb, traefik, cert-manager, cloudnativepg, openebs]
resource: https://app.pulumi.com/jaypee-solutions/kubernetes/prod
---

# What it deploys

Stack `jaypee-solutions/kubernetes/prod`, source `services/kubernetes`, applied on 2026-10-10 (109 resources, `pulumi preview --expect-no-changes` clean).

| Component | Notes |
| --- | --- |
| MetalLB | L2 pool `10.10.88.1`–`10.10.88.250` (chosen by the user, inside VLAN 10's `/16`) |
| NFS CSI driver | kubelet dir `/var/lib/k0s/kubelet`; no StorageClass defined |
| cert-manager | Let's Encrypt ClusterIssuer with DNS-01 through Cloudflare; ACME email `github@jaypee.solutions` (git identity, unconfirmed as desired contact); self-check forced to `1.1.1.1`/`1.0.0.1` because the LAN resolver answers NXDOMAIN for ACME records |
| Traefik | Service `10.10.88.1`, default TLS store with the wildcard certificate `*.4jp.de`, dnsmasq record `k8s-ingress-prod.4jp.de` |
| CloudNativePG | Operator only; no database cluster yet |
| OpenEBS LVM LocalPV | StorageClass `openebs-lvm-postgres` (`volgroup: postgres`, ext4, `WaitForFirstConsumer`, expansion allowed); snapshot CRDs and controller are on |

# Configuration and secrets

- Cloudflare: account API token (item `Cloudflare [4jp.de]`, ref `op://Homelab/Cloudflare [4jp.de]/password`) and zone `4jp.de`; DNS Edit verified (`docs/08-Decisions/ADR-0010 - Cloudflare account token for the Kubernetes stack.md`). Cloudflare is DNS only; no tunnels (`docs/08-Decisions/ADR-0011 - LAN-first ingress and service cleanup.md`).
- The kubeconfig is the `Kubeconfig prod` item in the `Homelab` vault, published manually from `k0sctl kubeconfig`.
- The Pulumi resolver (`utils/onepassword.py`) looks 1Password items up by **title**; the `op` CLI rejects brackets in titles, so use item IDs with `op`.
- `.envrc` loads a read-only 1Password service account token (item `Pulumi Service Account`, `docs/08-Decisions/ADR-0013 - 1Password service account for Pulumi.md`), the OPNsense key, secret, and endpoint, and writes the kubeconfig to `.direnv/kubeconfig` for `kubectl`/`k9s`.

# Local DNS

Local records are dnsmasq host records created through the OPNsense API at `https://router.4jp.de` (`docs/08-Decisions/ADR-0012 - Local DNS records through dnsmasq on OPNsense.md`). The API user needs the privilege "Services: Dnsmasq DNS/DHCP: Settings"; the `OPNsense` item keeps the key in `username` and the secret in `password`. The helper is `utils.opnsense.dnsmasq.host.Host`, used by the kubernetes, paperless, n8n, iot, and monitoring stacks.

# Not done yet

- Other stacks (paperless, n8n, monitoring, s3, backup, iot) still carry donor values (`tobiash.net`, `op://Pulumi/...`, Synology endpoints) and have not been previewed.
- Longhorn is not deployed; no CloudNativePG cluster exists; public exposure through Caddy on OPNsense is future work.
- Related: [k0s0 node](./k0s0-node.md), [cluster plan](./k0s-cluster-plan.md), [operational lessons](./operational-lessons.md).
