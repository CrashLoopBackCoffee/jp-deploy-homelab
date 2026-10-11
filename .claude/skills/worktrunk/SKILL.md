---
name: worktrunk
description: >
  This skill should be used when creating git worktrees for agent isolation, spawning parallel
  agents on separate branches, managing parallel feature development, using the `wt` CLI,
  switching between worktrees, merging worktree changes back to main, cleaning up worktrees
  after merging, or configuring worktrunk hooks. Triggers: "spawn parallel agents", "run
  agents in parallel", "create a worktree", "isolate agent work", "wt switch", "parallel
  feature work", "worktree for each", "agent handoff", "worktrunk".
version: 1.0.0
---

# Worktrunk — Git Worktree Management for Parallel Agents

[Worktrunk](https://worktrunk.dev) wraps `git worktree` to make parallel agent workflows
trivial. Each agent gets its own working directory so changes don't collide.

## Install (if not already present)

```bash
brew install worktrunk && wt config shell install
```

Shell integration is required for `wt switch` to change directories.

## Core Commands

| Goal | Worktrunk | Raw git equivalent |
|---|---|---|
| Switch to existing worktree | `wt switch <branch>` | `cd ../repo.branch` |
| Create worktree + switch | `wt switch --create <branch>` | `git worktree add -b <branch> ../repo.branch && cd ../repo.branch` |
| Create worktree + launch agent | `wt switch -c -x claude <branch>` | (multiple steps) |
| List all worktrees with status | `wt list` | `git worktree list` (paths only) |
| Merge back to main + clean up | `wt merge main` | squash + rebase + merge + remove (multiple steps) |
| Remove worktree | `wt remove` | `cd .. && git worktree remove repo.branch && git branch -d branch` |

## Spawn Parallel Agents

The primary pattern — create isolated worktrees and launch an agent in each:

```bash
wt switch -x claude -c feature-a -- 'Add user authentication'
wt switch -x claude -c feature-b -- 'Fix the pagination bug'
wt switch -x claude -c feature-c -- 'Write tests for the API'
```

- `-c` / `--create`: create a new branch + worktree from the default branch
- `-x <cmd>` / `--execute=<cmd>`: run this command after switching
- Arguments after `--` are passed to the executed command

To run agents in the background (detached), use tmux or zellij:

```bash
# tmux — new detached session per agent
tmux new-session -d -s fix-auth "wt switch -c -x claude fix-auth -- 'Fix session timeout'"

# zellij — new pane in current session
zellij run -- wt switch -c -x claude fix-auth -- 'Fix session timeout'
```

## Merge Workflow (PR or Local)

**PR workflow** — commit, push, open PR on GitHub, then clean up after merge:

```bash
wt step commit          # commit staged changes (uses LLM commit message if configured)
gh pr create            # open PR
wt remove               # after PR is merged
```

**Local merge** — squash, rebase onto main, fast-forward merge, clean up in one command:

```bash
wt merge main
```

## Check Status Across All Worktrees

```bash
wt list               # concise status view
wt list --full        # full view with CI status, PR links, LLM branch summaries
wt list --branches    # include branches without worktrees
```

Status indicators: `+` staged changes, `↑N` commits ahead of main, `⇡` unpushed commits.

## Configuration

| Scope | File | Purpose |
|---|---|---|
| Global (user) | `~/.config/worktrunk/config.toml` | Defaults, LLM commits, worktree path template |
| Project | `.config/wt.toml` (repo root) | Hooks, dev server, aliases |

See [references/config-and-hooks.md](references/config-and-hooks.md) for hook setup, the
`hash_port` template filter for per-worktree dev servers, and LLM commit message configuration.

## Claude Code Plugin (Claude Code CLI only)

If using Claude Code CLI, install the plugin for activity tracking (🤖/💬 markers in `wt list`)
and automatic `WorktreeCreate`/`WorktreeRemove` hook integration:

```bash
wt config plugins claude install
```

This does NOT affect VS Code Copilot agent — this skill serves that purpose instead.

## Key Shortcuts

```bash
wt switch -            # switch to previous worktree
wt switch pr:123       # check out PR #123 as a worktree
wt remove @            # remove current worktree
wt switch -c hotfix --base=@   # branch from current HEAD (stacked branches)
```
