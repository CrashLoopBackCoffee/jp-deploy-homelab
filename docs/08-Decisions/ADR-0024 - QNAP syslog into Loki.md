---
tags:
  - homelab
  - adr
  - kubernetes
  - observability
  - qnap
type: adr
status: accepted
date: 2026-10-17
created: 2026-10-17
updated: 2026-10-17
adr: 24
---

# ADR-0024 - QNAP syslog into Loki

## Status

Accepted on 2026-10-17. The receiver is **deployed and verified with test messages**; the QNAP itself still has to be pointed at it (see Consequences).

## Context

The QNAP holds every backup target of the cluster (QuObjects buckets for Longhorn, CloudNativePG and Mimir) and is the intake for Paperless. On the night of 2026-10-15 to 2026-10-16 it was overloaded (load average up to 112) and the cluster's backups failed ([[ADR-0022 - CloudNativePG base backups at 21:00 UTC]]). The cause is still unknown because nothing collected the QNAP's own logs; the evidence came from the legacy Prometheus on `dockerhost`. The user wants the QNAP's logs in the new Loki "so we see there for future".

The QNAP can forward its event and access logs from QuLog Center (Log Sender, Send to Syslog Server) with a host or IP, a port, a transfer protocol, a log type and a format. The user asked for both syslog formats, RFC 5424 and RFC 3164. The QNAP (`10.10.0.10` and `10.10.0.6`, two NICs) sits in the same `/16` as the cluster, so no routing is involved.

## Decision

- **Receive with Alloy** (`loki.source.syslog`) in the existing Alloy deployment and write to the existing Loki. Alloy needs one listener per format, so there are four listeners: **1514 for RFC 5424 and 1515 for RFC 3164, each over TCP and UDP**.
- **Publish them on a fixed MetalLB address**, `10.10.88.2`, through the LoadBalancer Service `alloy-syslog` and the local DNS name `syslog.4jp.de` (the existing dnsmasq record helper). `externalTrafficPolicy: Local` keeps the sender's address, and `loadBalancerSourceRanges` admits only the QNAP's two NIC addresses; kube-proxy enforces this for the load balancer address. The Service has `allocateLoadBalancerNodePorts: false`, because MetalLB does not need node ports and a node port would admit any host that can reach the node (see the correction below).
- **Labels** are low-cardinality only: `job="qnap-syslog"`, `source="qnap"`, and `host`, `app`, `severity`, `facility` and `source_ip` from the syslog header. The line is the message. The timestamp is the arrival time, because an RFC 3164 timestamp has no year and no time zone and Loki rejects samples that lie in its future.
- Retention is Loki's existing 30 days.

## Consequences

- **Verified 2026-10-17:** test messages in both formats over TCP and over UDP arrived in Loki with the labels above (4 of 4 combinations); Alloy reported 0 parse errors; a sender outside the allowed range (the workstation) could not connect to `10.10.88.2:1514`; `syslog.4jp.de` resolves to `10.10.88.2` in the cluster. After the user configured QuLog Center, its test message arrived from `10.10.0.6` (the second NIC) as host `qnap`, app `qulogd:` (the trailing colon is part of the tag the QNAP sends).
- **The QNAP must be configured by the user:** QuLog Center, Log Sender, Send to Syslog Server, enable it and add a destination `syslog.4jp.de` (or `10.10.88.2`). TCP is recommended for delivery; port 1514 for RFC 5424 (recommended), port 1515 for RFC 3164; log types event and access.
- If the QNAP sends from an address other than `10.10.0.10` or `10.10.0.6`, its packets are dropped silently. Widen `alloy.syslog.allowed-sources` in the stack config.
- Syslog is unauthenticated and unencrypted, and UDP can be spoofed; the source range and the LAN are the only protection. Do not forward anything sensitive. TLS is not configured.
- Nothing alerts yet when the QNAP stops sending. A Grafana rule on the absence of `{job="qnap-syslog"}` is a follow-up once the real log rate is known; whether HBS 3 job results arrive through this channel is to be checked on the first real logs.
- The 10 GiB Loki volume now also holds these logs; watch its usage (`kubelet_volume_stats_used_bytes`) after the first weeks.
- The legacy `BackupNAS` syslog path (Promtail on `dockerhost`, port 1514) is a different, still-deferred item.
- **Correction, 2026-10-17:** the first deployment was not restricted as written. A test message from the workstation to a **node port** (`10.10.8.1:31135`) was accepted and appeared in Loki with the source `10.10.1.17`, because kube-proxy applies `loadBalancerSourceRanges` only to the load balancer address. Setting `allocateLoadBalancerNodePorts: false` did not release the ports already allocated (the API keeps existing ones), so the Service was recreated (`delete_before_replace`, because its name and address are fixed; syslog delivery was interrupted for a few seconds). Afterwards both former node ports refuse connections from the workstation and the load balancer address is unchanged.

## Alternatives considered

- **One listener per protocol with a single format:** the user wants both formats, and Alloy cannot detect the format per message.
- **The `raw` format and parsing in `loki.process`:** experimental in Alloy and unnecessary for two standard formats.
- **Sending through Traefik or a ClusterIP only:** syslog is not HTTP, and the QNAP is outside the pod network.
- **An agent on the QNAP (Container Station) that pushes to Loki:** a heavier moving part on the device that is the problem.
- **Allowing the whole `10.10.0.0/24`:** simpler, but admits every host on that network to the receiver.

## Related notes

- [[ADR-0019 - LGTM observability stack on k0s]]
- [[ADR-0022 - CloudNativePG base backups at 21:00 UTC]]
- [[ADR-0023 - Retire the legacy dockerhost monitoring stack]]

## References

- [Alloy `loki.source.syslog`](https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.syslog/)
- [QTS: Configuring log sender settings](https://docs.qnap.com/operating-system/qts/5.2.x/en-us/configuring-log-sender-settings-66DE0C94.html)
