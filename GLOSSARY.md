# Wazuh Security Monitoring

This context describes endpoint inventory, vulnerability state, and security events for the homelab. It separates current posture from observed changes and from the freshness of vulnerability intelligence.

## Language

**Endpoint**:
A homelab system represented by an enrolled security agent.
_Avoid_: Host, node, device when referring specifically to an enrolled Wazuh subject.

**Software inventory**:
An endpoint’s observed operating-system, package, process, hardware, and network facts.
_Avoid_: Finding, alert.

**Current vulnerability finding**:
A present match between an endpoint’s software inventory and a known vulnerability, representing current state rather than a notification of a change.
_Avoid_: Vulnerability event, CVE alert.
**Fixable finding**:
A current vulnerability finding for which a package version that resolves it is known. Findings without a known fix are not fixable findings and are not notified.
_Avoid_: Actionable finding, patchable CVE.

**Vulnerability transition event**:
A time-stamped notification that a vulnerability was observed as active or solved; it is useful history, but not a complete ledger of every state change.
_Avoid_: Current finding, complete audit record.

**Security event**:
An observed authentication, integrity, network, or other security-relevant activity that may trigger detection rules.
_Avoid_: Vulnerability finding.

**Detection rule**:
A Wazuh classification rule that matches a security event and assigns a Wazuh alert level.
_Avoid_: Grafana alert rule.

**Grafana alert rule**:
A query-evaluation rule that determines when an operator should be notified and carries a notification severity such as warning or critical.
_Avoid_: Wazuh detection rule.

**CTI feed freshness**:
The recency of threat-intelligence content available for vulnerability detection.
_Avoid_: Manager health, age of the latest vulnerability alert.
