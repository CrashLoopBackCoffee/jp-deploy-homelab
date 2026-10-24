---
type: Service
title: Kubernetes platform stack (Pulumi, prod)
description: What the Kubernetes Pulumi stack deploys on k0s, how it is configured, and how secrets, DNS, and certificates flow.
timestamp: 2026-10-24T13:46:00Z
tags: [homelab, kubernetes, pulumi, metallb, traefik, cert-manager, cloudnativepg, openebs, longhorn]
resource: https://app.pulumi.com/jaypee-solutions/kubernetes/prod
---

# What it deploys

Stack `jaypee-solutions/kubernetes/prod`, source `services/kubernetes`, 134 resources after the 2026-10-24 rollout updates. Longhorn's QuObjects target remains Available and a disposable volume passed backup/restore. PostgreSQL's Barman base backup and archived WAL passed an independent restore; production application backups and time-targeted PITR have the evidence recorded below.

| Component | Notes |
| --- | --- |
| MetalLB | Chart 0.16.1 deployed; FRR-K8s disabled because this stack uses L2 only. The L2 pool remains `10.10.88.1`–`10.10.88.250`; controller and speaker are ready, Traefik retains `10.10.88.1`, and NetBox, Paperless, and Tandoor ingress returned HTTP 302. |
| NFS CSI driver | Version 4.13.6; kubelet dir `/var/lib/k0s/kubelet`; no StorageClass defined. Controller and node plugin are ready; Paperless's QNAP NFS intake remains mounted. |
| cert-manager | Version 1.21.3 (upgraded 1.19.1 → 1.20.4 → 1.21.2 → 1.21.3, one minor at a time); Let's Encrypt ClusterIssuer with DNS-01 through Cloudflare; ACME email `support@jaypee.solutions`; self-check forced to public recursive nameservers because the LAN resolver answers NXDOMAIN for ACME records. Deployments are available and all cluster certificates are Ready. |
| Traefik | Service `10.10.88.1`, default TLS store with the wildcard certificate `*.4jp.de`, dnsmasq record `k8s-ingress-prod.4jp.de` |
| CloudNativePG | Operator 1.30.1 (chart 0.29.1, upgraded from 1.27.0 / chart 0.26.0); Barman Cloud plugin 0.15.1 (chart 0.8.1) unchanged. Upgrade followed four completed pre-upgrade backups; all four clusters are healthy with `ContinuousArchiving=True`, and post-upgrade `paperless-db-post-cnpg-1-30` completed. Single-instance PostgreSQL clusters use daily physical backups at 21:00 UTC year-round (ADR-0022), continuous compressed WAL archiving and 14-day retention to QuObjects. |
| OpenEBS LVM LocalPV | StorageClass `openebs-lvm-postgres` (`volgroup: postgres`, ext4, `WaitForFirstConsumer`, expansion allowed); snapshot CRDs and controller are on |
| Longhorn | Chart 1.13.0 as `helm.v3.Release` (the chart has hook jobs), namespace `longhorn-system`, data path `/var/lib/longhorn` on the Kingston NVMe, 1 replica, kubelet dir `/var/lib/k0s/kubelet`; the chart's StorageClass `longhorn` is the cluster default. The QuObjects S3 backup target is Available and the daily `02:00` job belongs to the `default` group (retain 14). A disposable volume automatically joined that group and completed a backup and separate restore. No second snapshot controller (`docs/08-Decisions/ADR-0014 - Longhorn on a dedicated ext4 data disk.md`) |

# Configuration and secrets

- Cloudflare: account API token (item `Cloudflare [4jp.de]`, ref `op://Homelab/Cloudflare [4jp.de]/password`) and zone `4jp.de`; DNS Edit verified (`docs/08-Decisions/ADR-0010 - Cloudflare account token for the Kubernetes stack.md`). Cloudflare is DNS only; no tunnels (`docs/08-Decisions/ADR-0011 - LAN-first ingress and service cleanup.md`).
- The kubeconfig is the `Kubeconfig prod` item in the `Homelab` vault, published manually from `k0sctl kubeconfig`.
- The Pulumi resolver (`utils/onepassword.py`) looks 1Password items up by **title**; the `op` CLI rejects brackets in titles, so use item IDs with `op`.
- `.envrc` loads a read-only 1Password service account token (item `Pulumi Service Account`, `docs/08-Decisions/ADR-0013 - 1Password service account for Pulumi.md`), the OPNsense key, secret, and endpoint, and writes the kubeconfig to `.direnv/kubeconfig` for `kubectl`/`k9s`.

# Local DNS

Local records are dnsmasq host records created through the OPNsense API at `https://router.4jp.de` (`docs/08-Decisions/ADR-0012 - Local DNS records through dnsmasq on OPNsense.md`). The API user needs the privilege "Services: Dnsmasq DNS/DHCP: Settings"; the `OPNsense` item keeps the key in `username` and the secret in `password`. The helper is `utils.opnsense.dnsmasq.host.Host`, used by the kubernetes, paperless, n8n, iot, and monitoring stacks.

# Backup destination decision

The user selected the local QNAP's QuObjects S3-compatible service for Longhorn and CloudNativePG backups. Both private buckets, `longhorn-backups` and `cnpg-backups`, and separate access-key items `QuObjects Longhorn Backup` and `QuObjects CNPG Backup` in the `Homelab` vault exist. Initially each key could list the other bucket; after the user moved `cnpg-backups` into a dedicated storage space, each key can list its own bucket but receives `NoSuchBucket` when listing the other. QuObjects scopes access by NAS user and storage space rather than key name alone; do not claim object-write/delete isolation beyond this read-only test. The endpoint `https://qnap.4jp.de:8443` presents a certificate trusted for its name from the workstation; the earlier QNAP administration endpoint `10.10.0.10:8010` presented a self-signed certificate without a SAN and is not used. Do not disable TLS verification. Longhorn's credentials, target, and recurring job are applied. An OPNsense Unbound host override chosen and applied by the user points `qnap.4jp.de` to S3 NIC `10.10.0.10` instead of the other QNAP NIC `.6`; both router DNS ports now return `.10`, and `BackupTarget/default` is Available. Both QNAP NICs advertise `qnap` in active DHCP leases; neither reservation was deleted. A 256 MiB test volume created with `longhorn` automatically joined the `default` recurring-job group, was written and backed up to QuObjects, then restored into a separate volume; the restored PVC contained the same marker. Test resources and the test S3 volume prefix were removed afterward. An HBS 3 job with client-side encryption to a second, off-site QNAP is the selected secondary copy but is not verified. CloudNativePG's supported Barman Cloud plugin will provide physical base backups and WAL archiving; the NAS and HBS configuration remain outside Pulumi (ADR-0016).

CoreDNS forwards external names to its pod's `/etc/resolv.conf` and caches for up to 30 seconds (`kube-system/coredns` Corefile). Earlier direct queries to OPNsense at `10.10.0.1:53` and dnsmasq at `10.10.0.1:53053` both returned `.6` (TTL 1 second); the user's Unbound override corrected both to `.10`. Longhorn became Available without a CoreDNS restart. Resolve upstream DNS faults at the router before considering a CoreDNS cache flush.

QTS 5.2 exposes certificate replacement at **Control Panel → System → Security → SSL Certificate & Private Key → Server Certificate → Replace Certificate → Import certificate**; QuObjects documents HTTPS server mode but no separate certificate picker. The imported PEM certificate, matching key, and intermediate chain replace the NAS server certificate and may affect other QTS HTTPS endpoints. Verify that QuObjects serves the new certificate with a trusted name on its S3 port before client configuration; `https://qnap.4jp.de:8443` passes hostname and chain verification and is the endpoint in use. Import/renewal and DNS-01 issuance belong to the QNAP administration workflow, not this Pulumi stack. [QTS certificate instructions](https://docs.qnap.com/operating-system/qts/5.2.x/en-us/replacing-the-server-certificate-8E7C1926.html).

# Not done yet

- Other stacks (paperless, n8n, monitoring, backup, iot) still carry donor values (`tobiash.net`, `op://Pulumi/...`, Synology endpoints) and have not been previewed.
- The `postgres-pilot` Cluster is live; a scheduled backup ran, a base-backup-plus-WAL restore and a time-targeted PITR restore both passed, and their temporary restore resources were removed (ADR-0017, ADR-0018). **A Longhorn restore from a scheduled backup passed on 2026-10-17:** the `media-paperless-0` volume (30 GiB, real document) was restored from the 02:05 UTC backup into a disposable Longhorn `Volume` (`spec.fromBackup` with the backup's `s3://longhorn-backups@us-east-1/?backup=<name>&volume=<pvc volume>` URL, 1 replica), mounted read-only through a hand-made PV (`csi.driver.longhorn.io`, `volumeHandle` = volume name) and PVC, and its four files had the same combined SHA-256 as the live volume; the restore took about three minutes. The namespace, pod, PV and Longhorn volume were deleted with approval and the backup volume list was unchanged. A restored volume joins the `default` recurring-job group (02:00 UTC) unless deleted first. The encrypted off-site HBS copy is not yet verified. Public exposure through Caddy on OPNsense is future work (ADR-0016, ADR-0017).
- Related: [k0s0 node](./k0s0-node.md), [cluster plan](./k0s-cluster-plan.md), [operational lessons](./operational-lessons.md).
