# Review Against NetBox

Use this checklist when the user asks for a review, audit, or reconciliation.

## Goal

Compare the state in the change under review against NetBox source-of-truth state and identify mismatches with actionable corrections.

## Inputs

- Change source (diff, plan, ticket, migration spec, or incident notes)
- NetBox baseline snapshot for the same scope
- Known assumptions and missing data

## Review Workflow

1. Define scope precisely.
   - Identify affected sites, devices, interfaces, VLANs, prefixes, and IP addresses.
2. Extract asserted state from the change.
   - Expected role/status/site, interface mode/tagging, VLAN/prefix/IP bindings.
3. Capture NetBox state.
   - Query corresponding objects and record timestamp and filters.
4. Compare field-by-field.
   - Mark each check as `match`, `mismatch`, or `unknown`.
5. Rate impact.
   - `High`: outage/routing/security risk.
   - `Medium`: automation or operational confusion risk.
   - `Low`: documentation drift with low immediate impact.
6. Propose correction path.
   - Update change implementation, update NetBox, or both.
7. Confirm closure criteria.
   - No unresolved high-impact mismatches.
   - NetBox documentation plan exists for all accepted changes.

## Required Checks

- Device role/status/site alignment
- Interface ownership and naming consistency
- Access/trunk mode and tagged/untagged VLAN assignments
- Prefix and IP address ownership/binding validity
- VRF/tenant/location scoping where used
- Deprecated/retired object handling (status and references)

## Output Template

1. Scope
2. NetBox baseline
3. Findings by severity
4. Recommended corrections
5. Documentation and follow-ups
