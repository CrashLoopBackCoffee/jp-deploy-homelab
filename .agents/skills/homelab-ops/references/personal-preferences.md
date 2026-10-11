# Personal Preferences

This file encodes explicit operator preferences from current homelab notes.

## Decision Priorities

1. Stability and driver maturity (especially Linux/Proxmox)
2. Low power consumption
3. Reasonable cost

## Technology Preferences

- Prefer open-source first.
- Prefer SFP+ for 10G where practical.
- Use RJ45/10GBASE-T only when adapter or cabling practicality clearly wins.
- Avoid introducing new control planes without a clear operational benefit.

## Change Management Preferences

- Prefer small, reversible changes.
- Prefer explicit rollback plans before execution.
- Prefer NetBox as the primary source of truth for active network/inventory state.
- Prefer updating source-of-truth documentation in the same work session.
- Prefer conservative defaults for firewall and segmentation changes.

## Communication Preferences (for assistant output)

- Keep plans concise and checklists concrete.
- Call out risk, blast radius, and validation criteria before execution.
- Flag unresolved assumptions explicitly.
