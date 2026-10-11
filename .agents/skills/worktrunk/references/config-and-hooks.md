# Worktrunk Config & Hooks Reference

Full reference for `wt.toml` configuration and the hooks system.

## Config File Locations

```toml
# ~/.config/worktrunk/config.toml  — global (user)
# .config/wt.toml                  — project (repo root), committed to git
```

Project config is layered on top of global config.

## Worktree Path Template

Controls where new worktrees are created. Default: sibling directory with branch name appended.

```toml
# ~/.config/worktrunk/config.toml
worktree-path = "{{ repo_path }}/../{{ repo }}.{{ branch | sanitize }}"
```

For bare repositories (all branches as equal worktrees):

```toml
worktree-path = "{{ repo_path }}/../{{ branch | sanitize }}"
```

## Hooks

Hooks run shell commands at lifecycle events. Multiple hooks run in order (pipeline).

### Hook Types

| Hook | When it runs |
|---|---|
| `pre-start` | Before creating the worktree |
| `post-start` | After worktree is created and switched into |
| `pre-merge` | Before merging — failure aborts merge |
| `post-merge` | After merge completes |
| `pre-remove` | Before removing worktree |
| `post-remove` | After worktree is removed |
| `pre-commit` | Before committing (via `wt step commit`) |

### Hook Syntax

Single hook:
```toml
[post-start]
setup = "npm install"
```

Multiple hooks in sequence (pipeline array):
```toml
[[post-start]]
vars = "wt config state vars set port='{{ branch | hash_port }}'"

[[post-start]]
server = "npm run dev -- --port {{ vars.port }}"
```

### Template Variables in Hooks

| Variable | Value |
|---|---|
| `{{ branch }}` | Current branch name |
| `{{ repo }}` | Repository name |
| `{{ repo_path }}` | Absolute path to the repo root |
| `{{ worktree_path }}` | Absolute path to this worktree |
| `{{ vars.key }}` | Per-branch state variable |
| `{{ branch \| hash_port }}` | Stable port 10000–19999 derived from branch name |
| `{{ branch \| sanitize }}` | Branch name safe for shell use |
| `{{ branch \| sanitize_db }}` | Branch name safe for database identifiers |

## Common Recipes

### Dev Server Per Worktree

```toml
# .config/wt.toml
[post-start]
server = "npm run dev -- --port {{ branch | hash_port }}"

[list]
url = "http://localhost:{{ branch | hash_port }}"

[pre-remove]
server = "lsof -ti :{{ branch | hash_port }} -sTCP:LISTEN | xargs kill 2>/dev/null || true"
```

### Copy Build Caches from Main Worktree

Skips cold starts by sharing `node_modules/`, `target/`, `.venv/`, etc.:

```toml
[pre-start]
copy = "wt step copy-ignored"
```

### Local CI Gate Before Merge

```toml
[[pre-merge]]
lint = "uv run ruff check"

[[pre-merge]]
test = "uv run pytest"
```

### Database Per Worktree

```toml
[[post-start]]
set-vars = """
wt config state vars set \
  container='{{ repo }}-{{ branch | sanitize }}-postgres' \
  port='{{ ("db-" ~ branch) | hash_port }}' \
  db_url='postgres://postgres:dev@localhost:{{ ("db-" ~ branch) | hash_port }}/{{ branch | sanitize_db }}'
"""

[[post-start]]
db = """
docker run -d --rm \
  --name {{ vars.container }} \
  -p {{ vars.port }}:5432 \
  -e POSTGRES_DB={{ branch | sanitize_db }} \
  -e POSTGRES_PASSWORD=dev \
  postgres:16
"""

[pre-remove]
db-stop = "docker stop {{ vars.container }} 2>/dev/null || true"
```

## LLM Commit Messages

```toml
# ~/.config/worktrunk/config.toml
[commit.generation]
command = "claude -p"     # or: "llm", "openai", etc.
```

Used by `wt step commit` and `wt merge` to auto-generate commit messages from diffs.

Enable branch summaries in `wt list --full`:

```toml
[list]
summary = true
```

## Per-Branch State Variables

Store and read branch-scoped state accessible in templates and hooks:

```bash
wt config state vars set key=value       # set a variable for current branch
wt config state vars get key             # read it
DATABASE_URL=$(wt config state vars get db_url) npm start
```

## Aliases

Define custom `wt <name>` shortcuts:

```toml
# .config/wt.toml or ~/.config/worktrunk/config.toml
[aliases]
open = "open http://localhost:{{ branch | hash_port }}"
test = "cargo test --features {{ vars.features | default('default') }}"
```

Run with `wt open` or `wt test`.
