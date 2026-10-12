---
type: Service
title: Kubernetes platform stack (Pulumi, prod)
description: What the Kubernetes Pulumi stack deploys on k0s, how it is configured, and how secrets, DNS, and certificates flow.
timestamp: 2026-10-12T00:00:00Z
tags: [homelab, kubernetes, pulumi, metallb, traefik, cert-manager, cloudnativepg, openebs, longhorn]
resource: https://app.pulumi.com/jaypee-solutions/kubernetes/prod
---

# What it deploys

Stack `jaypee-solutions/kubernetes/prod`, source `services/kubernetes`, 112 resources after adding Longhorn on 2026-10-11 (`pulumi preview --expect-no-changes` clean).

| Component | Notes |
| --- | --- |
| MetalLB | L2 pool `10.10.88.1`–`10.10.88.250` (chosen by the user, inside VLAN 10's `/16`) |
| NFS CSI driver | kubelet dir `/var/lib/k0s/kubelet`; no StorageClass defined |
| cert-manager | Let's Encrypt ClusterIssuer with DNS-01 through Cloudflare; ACME email `support@jaypee.solutions` (confirmed by the user on 2026-10-12); self-check forced to `1.1.1.1`/`1.0.0.1` because the LAN resolver answers NXDOMAIN for ACME records |
| Traefik | Service `10.10.88.1`, default TLS store with the wildcard certificate `*.4jp.de`, dnsmasq record `k8s-ingress-prod.4jp.de` |
| CloudNativePG | Operator only; no database cluster yet |
| OpenEBS LVM LocalPV | StorageClass `openebs-lvm-postgres` (`volgroup: postgres`, ext4, `WaitForFirstConsumer`, expansion allowed); snapshot CRDs and controller are on |
| Longhorn | Chart 1.13.0 as `helm.v3.Release` (the chart has hook jobs), namespace `longhorn-system`, data path `/var/lib/longhorn` on the Kingston NVMe, 1 replica, kubelet dir `/var/lib/k0s/kubelet`; the chart's StorageClass `longhorn` is the cluster default; no second snapshot controller (`docs/08-Decisions/ADR-0014 - Longhorn on a dedicated ext4 data disk.md`) |

# Configuration and secrets

- Cloudflare: account API token (item `Cloudflare [4jp.de]`, ref `op://Homelab/Cloudflare [4jp.de]/password`) and zone `4jp.de`; DNS Edit verified (`docs/08-Decisions/ADR-0010 - Cloudflare account token for the Kubernetes stack.md`). Cloudflare is DNS only; no tunnels (`docs/08-Decisions/ADR-0011 - LAN-first ingress and service cleanup.md`).
- The kubeconfig is the `Kubeconfig prod` item in the `Homelab` vault, published manually from `k0sctl kubeconfig`.
- The Pulumi resolver (`utils/onepassword.py`) looks 1Password items up by **title**; the `op` CLI rejects brackets in titles, so use item IDs with `op`.
- `.envrc` loads a read-only 1Password service account token (item `Pulumi Service Account`, `docs/08-Decisions/ADR-0013 - 1Password service account for Pulumi.md`), the OPNsense key, secret, and endpoint, and writes the kubeconfig to `.direnv/kubeconfig` for `kubectl`/`k9s`.

# Local DNS

Local records are dnsmasq host records created through the OPNsense API at `https://router.4jp.de` (`docs/08-Decisions/ADR-0012 - Local DNS records through dnsmasq on OPNsense.md`). The API user needs the privilege "Services: Dnsmasq DNS/DHCP: Settings"; the `OPNsense` item keeps the key in `username` and the secret in `password`. The helper is `utils.opnsense.dnsmasq.host.Host`, used by the kubernetes, paperless, n8n, iot, and monitoring stacks.

# Backup destination decision

The user selected the local QNAP's QuObjects S3-compatible service for Longhorn and CloudNativePG backups. Private buckets named `longhorn-backups` and `cnpg-backups`, and separate scoped access-key items `QuObjects Longhorn Backup` and `QuObjects CNPG Backup` in the `Homelab` vault, were approved but **not created**. An HBS 3 job with client-side encryption to a second, off-site QNAP is the selected secondary copy (ADR-0016). The supplied address `10.10.0.10:8010` responds on HTTPS, but the QNAP's self-signed certificate has no SAN and does not verify for that IP. The user chose a trusted certificate on an as-yet-unspecified DNS name; do not disable TLS verification. Buckets, credentials, the HBS job, and restores are not configured; no backup guarantee exists yet. A direct CNPG Barman Cloud integration to QuObjects supports physical base backups and WAL archiving, unlike plain NFS. The NAS deployment and HBS job remain outside this Pulumi stack.

QTS 5.2 exposes certificate replacement at **Control Panel → System → Security → SSL Certificate & Private Key → Server Certificate → Replace Certificate → Import certificate**; QuObjects documents HTTPS server mode but no separate certificate picker. The imported PEM certificate, matching key, and intermediate chain replace the NAS server certificate and may affect other QTS HTTPS endpoints. Verify that QuObjects serves the new certificate on port 8010 with a trusted name before client configuration; the live endpoint has not yet been rechecked after replacement. Import/renewal and DNS-01 issuance belong to the QNAP administration workflow, not this Pulumi stack. [QTS certificate instructions](https://docs.qnap.com/operating-system/qts/5.2.x/en-us/replacing-the-server-certificate-8E7C1926.html).

# Not done yet

- Other stacks (paperless, n8n, monitoring, backup, iot) still carry donor values (`tobiash.net`, `op://Pulumi/...`, Synology endpoints) and have not been previewed.
- No CloudNativePG cluster exists; Longhorn backups are not configured yet (the QuObjects target has been selected but not provisioned, ADR-0016). Public exposure through Caddy on OPNsense is future work.
- Related: [k0s0 node](./k0s0-node.md), [cluster plan](./k0s-cluster-plan.md), [operational lessons](./operational-lessons.md).
