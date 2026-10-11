---
name: okf-validate
description: >-
  This skill should be used when asked to "validate an OKF bundle", "lint OKF",
  "check an OKF bundle", or before committing Open Knowledge Format changes.
  Runs a deterministic Python checker for OKF v0.1 §9 conformance — not an
  eyeball pass.
user-invocable: true
argument-hint: "[bundle-dir] [--strict]"
allowed-tools: Bash(uv run *okf-validate/scripts/okf_validate.py *), Bash(python3 *okf-validate/scripts/okf_validate.py *), Bash(python3 -m pip install --user --quiet pyyaml)
---

# Validate an OKF bundle

Run the deterministic conformance checker against the target bundle. Default to
the project's `.okf/` directory when no path is given.

```bash
uv run "${CLAUDE_SKILL_DIR}/scripts/okf_validate.py" ${ARGUMENTS:-.okf}
```

If `uv` is unavailable, fall back to Python 3.11 or newer:

```bash
python3 -m pip install --user --quiet pyyaml
python3 "${CLAUDE_SKILL_DIR}/scripts/okf_validate.py" ${ARGUMENTS:-.okf}
```

`${CLAUDE_SKILL_DIR}` resolves whether this skill runs as part of the `okf`
plugin or is installed standalone (e.g. via `npx skills add`), so the checker is
always found alongside the skill.

Interpret the result:

- **ERROR** → a hard §9 conformance failure: no parseable concept
  frontmatter, missing/empty concept `type`, or reserved `index.md` / `log.md`
  structure that violates §6 / §7. The bundle is non-conformant. Fix every one.
- **warn** → soft guidance such as missing recommended fields or broken
  cross-links. Never blocks; broken links in particular are explicitly tolerated
  by the spec (§5.3). Fix when cheap.

Exit code is non-zero if any error is present (or any warning, when `--strict`).
Add `--json` for machine-readable output (useful in CI).
