---
name: okf-visualize
description: >-
  This skill should be used when asked to "visualize an OKF bundle", "graph an
  OKF bundle", "preview OKF", or "explore an OKF bundle". Renders an Open
  Knowledge Format bundle as an interactive HTML graph (viz.html): concepts as
  nodes, markdown links as edges, and a wiki-style detail panel with rendered
  markdown plus "Links to" / "Cited by" backlinks.
user-invocable: true
argument-hint: "[bundle-dir] [-o viz.html]"
allowed-tools: Bash(uv run *okf-visualize/scripts/okf_visualize.py *), Bash(python3 *okf-visualize/scripts/okf_visualize.py *), Bash(python3 -m pip install --user --quiet pyyaml)
---

# Visualize an OKF bundle

Generate a single HTML graph of the target bundle (default the project's
`.okf/`). No backend is required; the generated page loads Cytoscape and Marked
from jsDelivr CDN when opened, so viewing it can make external network requests.
Bundle content is embedded locally in the page.

```bash
uv run "${CLAUDE_SKILL_DIR}/scripts/okf_visualize.py" $ARGUMENTS
```

If `uv` is unavailable, fall back to Python 3.11 or newer:

```bash
python3 -m pip install --user --quiet pyyaml
python3 "${CLAUDE_SKILL_DIR}/scripts/okf_visualize.py" $ARGUMENTS
```

The output defaults to `<bundle>/viz.html`. Pass `-o <path>` to write elsewhere.
Open it in any browser; `${CLAUDE_SKILL_DIR}` resolves whether this runs as part
of the `okf` plugin or as a standalone skills.sh skill.
