---
name: homelab-ops
description: This skill should be used when the user asks to "change homelab networking", "configure OPNsense", "plan VLAN segmentation", "migrate homelab services", "troubleshoot a homelab incident", "verify runtime state", "plan Proxmox VM placement", or "review 10G SFP+ design". Covers safe local homelab operations for OPNsense, VLANs, Proxmox/VMs, service migration, incident triage, rollback planning, and runtime validation. Pair with netbox-ops for NetBox/IPAM/inventory documentation and reconciliation.
---

# Homelab Ops

**Runtime scope:** local-filesystem-only | **Depends on:** netbox-ops

Use this skill when the user asks to operate, change, troubleshoot, or document this homelab.
This skill is intentionally optimized for local usage only.
This skill handles execution and operational safety; `netbox-ops` handles NetBox source-of-truth quality.

## When to Use

Activate this skill when requests involve:
- OPNsense, VLANs, trunk/access ports, DHCP scopes, or segmentation.
- Proxmox hosts, VMs/containers, NAS/network paths, or service placement.
- 10G design decisions (SFP+ vs RJ45, DAC vs fiber, switch topology).
- Incident triage, outage containment, or rollback planning.
- Runtime validation of network/service behavior in this homelab.

Do not use this skill for generic app-only coding work that has no homelab impact.
Do not use this skill alone for NetBox/IPAM inventory governance; use `netbox-ops`.

## Operating Principles

- Stability over speed: prioritize low-risk, reversible steps.
- One variable at a time for network changes.
- Explicit rollback before execution.
- Keep management-plane access preserved during every step.
- NetBox/IPAM consistency is delegated to `netbox-ops`.
- Repository reference docs are supporting context, not authoritative runtime state.
- Complete runtime changes and documentation in the same work session.

## Safety Rules (always)

1. Start with a change plan: objective, scope, preconditions, steps, validation, rollback, docs.
2. Run manual preflight checklist before any risky action.
3. State assumptions and unknowns explicitly; do not hide uncertainty.
4. Avoid destructive commands unless user explicitly approves.
5. For remote/networking changes, include an out-of-band recovery path.
6. Stop and ask before proceeding if rollback cannot be executed with current access.
7. If scope includes NetBox, VLAN/CIDR/IP addressing, or network inventory, activate `netbox-ops` first.

## Workflow

1. Load context:
   - [ops-checklists](references/ops-checklists.md)
2. Load only the minimum additional references needed:
   - [baseline-setup](references/baseline-setup.md) for planning context
   - [personal-preferences](references/personal-preferences.md) for decision preferences
3. If task scope touches NetBox/VLAN/CIDR/private IP/network inventory, activate [NetBox Ops](../../../apm_modules/jaypee-solutions/apm-homelab/.apm/skills/netbox-ops/SKILL.md).
4. Classify the task:
   - Network/VLAN execution
   - Host lifecycle (Proxmox/VM/container)
   - Service deployment/migration
   - Incident triage
5. Build plan using the relevant checklist from [ops-checklists](references/ops-checklists.md).
6. Run manual preflight checklist from [ops-checklists](references/ops-checklists.md).
7. Execute smallest safe step, validate, then continue.
8. If validation fails, trigger rollback path immediately and report status.
9. Update relevant homelab notes with final runtime state, deviations, and follow-ups.
10. For NetBox updates/reconciliation, complete `netbox-ops` documentation steps before closeout.

## Response Format

For every homelab operation response, output these sections in order:

1. `Planned change`
   - What is changing and why now.
   - Blast radius and risk level.
2. `Current state and assumptions`
   - Runtime snapshot used and freshness.
   - NetBox baseline from `netbox-ops` when in scope.
   - Preconditions, dependencies, unknowns.
3. `Preflight`
   - Manual preflight checklist results and blockers.
4. `Actions`
   - Ordered commands/actions with smallest safe increments.
5. `Validation`
   - Exact checks run and observed results.
6. `Rollback`
   - Trigger conditions, rollback steps, and current rollback status.
7. `Documentation`
   - Local files updated and outstanding follow-ups.
   - NetBox updates/review status from `netbox-ops` when applicable.

## Incident Mode

If the task is incident triage, use this sequence:

1. Capture symptoms, start time, and suspected blast radius.
2. Identify last known good state and most recent relevant changes.
3. Stabilize first (containment), optimize second.
4. If inventory/IPAM drift is relevant, use `netbox-ops` to reconcile against NetBox.
5. Provide incident note: root cause, fix, prevention items.
6. Add short follow-up plan to reduce repeat risk.

## Defaults for This Homelab

- Router/firewall: OPNsense.
- Segmentation-first design with VLANs.
- 10G strategy: prefer SFP+ over RJ45 where practical.
- Decision priority: stability/driver maturity, then power, then cost.
- Prefer open-source options first.
- `netbox-ops` is responsible for NetBox source-of-truth governance.

## References

- [Baseline Setup](references/baseline-setup.md)
- [Personal Preferences](references/personal-preferences.md)
- [Ops Checklists](references/ops-checklists.md)
- [NetBox Ops Skill](../../../apm_modules/jaypee-solutions/apm-homelab/.apm/skills/netbox-ops/SKILL.md)
