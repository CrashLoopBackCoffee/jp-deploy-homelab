---
tags:
  - homelab
  - adr
  - kubernetes
  - security
type: adr
status: accepted
date: 2026-10-10
created: 2026-10-10
updated: 2026-10-10
adr: 7
---

# ADR-0007 - Dedicated k0sctl automation account

## Status

Accepted on 2026-10-10. Implemented on `k0s0`.

## Context

k0sctl manages hosts over SSH and needs a Linux user that is root or has passwordless `sudo`. The administrator account on `k0s0` (`alten`) authenticates with a key that needs fingerprint confirmation and uses `sudo` with a password, so it cannot drive k0sctl non-interactively. See [[ADR-0006 - Ubuntu Server 24.04 LTS for k0s nodes]] and [[ADR-0005 - Phased bare-metal k0s cluster]].

## Decision

- Keep the personal account for interactive administration.
- Each k0s node gets a dedicated `k0sctl` user with no password, one authorized SSH key, and `/etc/sudoers.d/k0sctl` containing `k0sctl ALL=(ALL) NOPASSWD:ALL` (validated with `visudo -cf`).
- The authorized key is the ed25519 key labelled `k0s` held in the SSH agent on the administrator machine. No new private key is created or stored on disk.
- sshd is not pinned to a source address, because the administrator machine's address is DHCP-assigned. Restrict reachability of SSH on the k0s nodes at the VLAN firewall instead.

## Consequences

- `k0sctl` has root-equivalent access to every node; compromise of the `k0s` key is compromise of the cluster. Protect the key in the agent and remove the account's authorized key if the key is rotated.
- The same account setup must be repeated on Nodes 2 and 3 before they join.
- Narrower sudo rules are not viable: k0sctl runs arbitrary commands as root.

## Related notes

- [[ADR-0006 - Ubuntu Server 24.04 LTS for k0s nodes]]
- [[Runbook - k0s Node OS Preparation]]
- [[k0s]]
