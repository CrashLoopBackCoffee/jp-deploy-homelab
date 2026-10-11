# NetBox Operations

Use this reference to run NetBox operations with official best practices and keep data reliable for automation.

## Official Guidance Baseline

Align operations to the NetBox Labs "Zero to Hero" guidance and official NetBox docs:
- NetBox is an authoritative network source of truth for desired state.
- NetBox is not an operational telemetry system.
- NetBox data should be human-vetted; avoid blind auto-import of live state.
- Operators should use both the Web UI/data model and REST API intentionally.

## Source of Truth Boundaries

Treat NetBox as authoritative for active desired-state infrastructure data:
- Devices and roles
- Interfaces and cabling/logical links
- VLANs and interface tagging
- IP addresses and prefixes
- Site/rack/location placement where used

Treat repository notes as planning and execution context only.
Treat runtime observations (ping, logs, metrics) as operational-state evidence only.

If these disagree, resolve and document drift before risky changes.

## NetBox Instance

URL: stored in local private notes (not tracked in this repo)
API Key: stored in your secret manager — retrieve it from there; do not hardcode

Also nbcli is available. Use docs at https://nbcli.codeberg.page/latest/quick-start/

## Data Modeling Rules

1. Model with native NetBox objects first.
   - If NetBox has a model, use it before adding custom fields/plugins.
2. Keep domain ownership explicit.
   - For every domain (inventory, IPAM, VLANs, circuits), define one authority.
3. Validate before import/update.
   - Follow GIGO discipline: verify source data quality before writing to NetBox.
4. Prefer structured links over free text.
   - Encode relationships in object fields/relations, not comments.
5. Keep statuses and roles current.
   - Status/role drift breaks downstream automation assumptions.

## Recommended Object Creation/Import Order (Official Pattern)

Use this order for first-time modeling or large rebuilds:

1. Tenant groups and tenants (if used)
2. Regions, site groups, sites, and locations
3. Rack roles and racks
4. Manufacturers, device types, and module types
5. Platforms and device roles
6. Devices and modules
7. Route targets and VRFs
8. RIRs and aggregates
9. IP/VLAN roles
10. Prefixes, IP ranges, and IP addresses
11. VLAN groups and VLANs
12. Clusters, virtual machines, and VM interfaces (if used)

## Data Ingestion Method Selection

- Manual UI creation:
  - Best for small, careful edits.
  - Not ideal for large imports.
- Bulk import (CSV/YAML):
  - Use for structured migrations.
  - CSV import supports creating and updating objects.
  - Including `id` updates existing records instead of creating new ones.
- Custom scripts:
  - Use for patterned data (for example standard VLAN sets per site).
- REST API:
  - Use for repeatable programmatic operations and bulk create/update.

## DCIM/IPAM Modeling Best Practices

- Assign IP addresses to interfaces (not directly to devices).
- Use VLAN groups with clear scope (site/location/rack).
- Enforce unique VLAN ID and name within each VLAN group.
- Set interface 802.1Q mode explicitly and apply tagged/untagged VLANs accordingly.
- Use device types with interface templates so interfaces are created consistently.

## NetBox-First Change Workflow

1. Pre-change state capture:
   - Query only the NetBox objects in planned blast radius.
   - Record timestamp, filters used, and query context.

2. Reconciliation gate:
   - If observed runtime state conflicts with NetBox, stop and resolve drift before risky changes.
   - If drift cannot be resolved immediately, run only low-risk diagnostics and flag follow-up.

3. Execution:
   - Apply smallest safe change increment.
   - Validate on runtime systems.

4. Post-change documentation:
   - Update NetBox objects changed by the operation.
   - Update local notes/checklists as needed.
   - Record any deferred NetBox updates as explicit follow-up tasks.
   - Attach change context (`changelog_message`, ticket/change ID) when using API writes.

## REST API Best Practices

Use these defaults when interacting with NetBox API:

- Use `PATCH` for partial updates; reserve `PUT` for full object replacement.
- Use pagination intentionally (`limit`/`offset`); avoid unbounded fetches by default.
- Use field selection for performance:
  - `?fields=` to request only needed fields
  - `?omit=` to suppress expensive fields
  - `?brief=true` for lightweight representations
- For device/VM lists at scale, use `?exclude=config_context` when context data is not required.
- Add `changelog_message` on create/update/delete operations.
- Capture `X-Request-ID` for traceability and correlate with object changes.
- Use least-privilege API tokens:
  - read-only token for read workflows
  - write token only where required
  - restrict token by client IP where possible
- Never print API tokens in output/logs.

## Minimum Update Set by Change Type

Network and VLAN changes:
- VLAN definitions (if added/removed/renamed)
- Interface mode/tagging/untagged VLAN assignments
- Related IP/prefix relationships if altered

Host lifecycle changes:
- Device status/role/platform
- Management and service interfaces
- IP assignments and tenancy metadata (if used)

Service migrations:
- Interface/IP ownership where service endpoints moved
- Relevant dependency notes in local docs if NetBox plugin/model is not used

## Data Quality Rules

- Do not leave NetBox in a partially updated state after successful change windows.
- Use consistent naming for devices/interfaces/VLAN groups.
- Prefer explicit links and interface assignments over free-text notes.
- Include change reference IDs in comments/custom fields when possible.
- If NetBox was unavailable during execution, add a dated follow-up task and owner.

## Official References

- NetBox Labs Zero to Hero module 1 (introduction): https://netboxlabs.com/zero-to-hero-1-introduction/
- NetBox getting started and data migration planning: https://netbox.readthedocs.io/en/stable/getting-started/populating-data/
- NetBox REST API guide: https://netbox.readthedocs.io/en/stable/integrations/rest-api/
- NetBox VLAN model reference: https://netbox.readthedocs.io/en/stable/models/ipam/vlan/
- NetBox interface model reference: https://netbox.readthedocs.io/en/stable/models/dcim/interface/

## Local-Only Practice

This skill is local-usage oriented:
- If NetBox API access is unavailable, provide manual UI update steps and a checklist.
- If NetBox API access is available, provide minimal, safe API examples without exposing secrets.

Never print API tokens in command output or logs.
