---
name: netbox-ops
description: This skill should be used when the user asks to "operate NetBox", "update network inventory", "document VLANs", "review CIDR ranges", "reconcile IPAM data", "compare changes against NetBox", "audit private IP addresses", or "fix NetBox drift". Covers NetBox-first operations, network inventory, IPAM, VLANs, prefixes, private IP addresses, reconciliation, and reviews that compare proposed or observed state to NetBox.
---

# NetBox Ops

**Runtime scope:** local-filesystem-only | **Source of truth:** netbox

Use this skill for NetBox-first operations, reconciliation, and documentation quality.
This skill is the NetBox expert and owns consistency checks for network inventory data.

## When to Use

Activate this skill when requests involve any of the following:
- NetBox explicitly.
- VLAN definitions, VLAN assignments, or trunk/access tagging data.
- CIDR ranges, prefixes, subnetting, or private IP addressing.
- Network-related inventory (devices, interfaces, cabling, roles, locations, IPAM relations).
- Reviews/audits where proposed or changed state must be compared to NetBox.
- Drift detection between observed state and source-of-truth state.

If a task includes both homelab execution and NetBox/IPAM scope, use this skill alongside `homelab-ops`.

## Operating Principles

- NetBox is authoritative for desired-state network inventory and IPAM.
- Runtime telemetry is evidence, not source of truth.
- Model with native NetBox objects before custom fields/plugins.
- Prefer explicit relationships over free-text notes.
- Never leave successful changes undocumented in NetBox.
- Keep naming, roles, statuses, and scoping consistent across related objects.
- Use least-privilege tokens and never expose secrets in output.

## Safety Rules (always)

1. Capture current NetBox state for in-scope objects before risky changes.
2. Reconcile drift before high-impact execution; if unresolved, run diagnostics only.
3. Use smallest safe update increments; validate after each increment.
4. For write operations, include clear change context (`changelog_message` or equivalent).
5. If NetBox is unavailable, provide a manual update checklist and a dated follow-up task.
6. During reviews, distinguish confirmed mismatch, likely mismatch, and unknown due to missing data.

## Workflow

1. Load context:
   - [netbox-operations](references/netbox-operations.md)
   - [review-against-netbox](references/review-against-netbox.md) when the user asks for a review/audit
2. Determine scope objects:
   - Sites, devices, interfaces, VLAN groups/VLANs, prefixes, IP addresses, VRFs, related tenancy/location objects.
3. Capture baseline from NetBox:
   - Record query scope and timestamp.
4. Classify task:
   - NetBox update/reconciliation
   - VLAN/CIDR/IPAM design or correction
   - Inventory modeling/cleanup
   - Review against change state
5. Execute the relevant checklist from references.
6. Validate consistency:
   - Required relations exist.
   - Status/role/naming conventions are coherent.
   - VLAN/IP/prefix/interface bindings are internally consistent.
7. Complete documentation:
   - Apply NetBox updates in-session.
   - If blocked, create explicit follow-up with owner and due date.

## Review Mode (required for "review" requests)

When asked for a review, compare change state to NetBox state:

1. Extract intended/current state from the change under review.
2. Query corresponding NetBox objects in the same scope.
3. Compare field-by-field for critical attributes (role/status/site/interface/VLAN/prefix/IP bindings).
4. Report findings by severity with exact mismatches and expected NetBox representation.
5. Include recommended NetBox or change-side correction for each mismatch.
6. If data is missing, call it out as a blocker with precise object/field gaps.

## Response Format

For NetBox operations and reviews, output these sections in order:

1. `Scope`
   - Objects and boundaries evaluated.
2. `NetBox baseline`
   - Snapshot timestamp, query filters, and coverage.
3. `Findings`
   - Drift/mismatches, missing links, and data quality issues.
4. `Actions`
   - Ordered updates or review recommendations.
5. `Validation`
   - Checks performed and observed outcomes.
6. `Documentation status`
   - NetBox objects updated, deferred items, owners, and due dates.

## References

- [NetBox Operations](references/netbox-operations.md)
- [Review Against NetBox](references/review-against-netbox.md)
