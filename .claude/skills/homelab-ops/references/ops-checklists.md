# Ops Checklists

## Manual Preflight Checklist

Use this before risky changes (especially network and routing):

- Confirm current-state snapshot source and freshness:
  - Runtime objects reviewed for affected systems.
  - If VLAN/CIDR/private IP/inventory scope exists, run NetBox snapshot via `netbox-ops`.
  - Timestamp of snapshot.
- Confirm access and recovery:
  - Management-plane access method(s) available.
  - Out-of-band recovery path exists for network-impacting changes.
- Confirm change safety:
  - Backups/snapshots are available where relevant.
  - Rollback steps are written and executable now.
  - Maintenance window/dependency constraints are identified.
- Confirm scope integrity:
  - Blast radius is identified.
  - Required approvals are recorded.

## Change Plan Template

Use this structure before implementation:

1. Objective
- What is changing and why now?
2. Scope
- Hosts, VLANs, services, users affected.
3. Preconditions
- Backups, access method, maintenance window, dependencies.
- NetBox state reviewed and reconciled via `netbox-ops` when applicable.
4. Steps
- Ordered, smallest safe increments.
5. Validation
- Exact checks and expected results.
6. Rollback
- Trigger conditions and exact rollback steps.
7. Documentation
- Which local files/notes will be updated.
- Which NetBox objects will be updated via `netbox-ops`.

## Network/VLAN Change Checklist

- Run `netbox-ops` baseline capture for VLAN/interface/IP/prefix state first.
- If observed state differs from NetBox, resolve discrepancy with `netbox-ops` before risky changes.
- Confirm current port mode (access/trunk) and allowed VLANs.
- Confirm gateway and DHCP scope impact.
- Apply one VLAN/trunk change at a time.
- Validate connectivity from at least two relevant segments.
- Confirm management-plane access is preserved before next step.
- Complete NetBox VLAN/interface/IP updates using `netbox-ops` after successful change.

## Proxmox/Host Change Checklist

- Confirm runtime host/interface mappings; use `netbox-ops` for NetBox consistency checks.
- Confirm host health and resource headroom.
- Snapshot/backup critical VM/CT if impact is non-trivial.
- Validate network path and storage path separately.
- After change, validate boot, service status, and reachability.
- Update NetBox device role/status, interfaces, and IP assignments via `netbox-ops` if changed.

## Service Migration Checklist

- Baseline current state and data paths.
- Verify destination capacity/performance assumptions.
- Run migration in phased mode where possible.
- Validate data integrity, latency, and error rate.
- Keep old path intact until post-cutover validation passes.
- Update NetBox records via `netbox-ops` if service location, addressing, or dependencies changed.

## Incident Triage Checklist

- Capture symptoms, start time, and blast radius.
- Identify last known good state and recent changes.
- Stabilize first (containment), optimize second.
- Compare impacted devices/interfaces/prefixes against NetBox using `netbox-ops` for drift signals.
- Produce short incident note with: root cause, fix, prevention.
- Record corrective NetBox updates via `netbox-ops` after incident stabilization.
