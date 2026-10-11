---
name: github-pr-workflow
description: >
  This skill should be used when the user asks to "create a PR", "open pull
  request", "show PR details", "fetch review comments", "resolve review
  threads", "triage PR feedback", "inspect PR status", "collect review
  feedback", "handle PR review comments", or "clear unresolved review threads".
  Covers GitHub pull request operations with the gh CLI, including PR metadata,
  PR creation, review-thread triage, replies, and resolving addressed threads.
version: 1.1.0
allowed-tools: Read, Edit, Grep, Glob, Bash(gh auth status *), Bash(gh repo view *), Bash(gh pr view *), Bash(gh pr list *), Bash(gh api *), Bash(git status *), Bash(git diff *), Bash(git branch *), Bash(git add *), Bash(git commit *), Bash(git push *), Bash(jq *), Bash(*github-pr-workflow/scripts/pr-thread-summary.sh *), Bash(*github-pr-workflow/scripts/reply-and-resolve-threads.sh *)
---

# GitHub PR Workflow

Use this skill to perform GitHub pull request operations using the `gh` CLI: read PR metadata, create PRs, and manage review threads end-to-end.

## Quick Start

1. Resolve repository context (`owner/repo`, PR number if known).
2. For comment triage, prefer `scripts/pr-thread-summary.sh` to combine auth,
   repository, PR metadata, and unresolved-thread discovery in one shell call.
3. Choose operation:
   - **Read**: fetch PR details or unresolved review threads.
   - **Create**: open a new pull request.
   - **Resolve**: triage, reply, and resolve review threads.

See [references/github-cli-playbook.md](references/github-cli-playbook.md) for concrete commands and GraphQL snippets.

## Low-Approval Operating Model

Minimize tool approvals by batching surrounding work. Do not ask the user before
read-only GitHub/git context collection, unresolved-thread fetches, local file
inspection, status/diff checks, targeted validation, final status checks,
committing/pushing approved local edits to the PR branch, or posting factual
replies and resolving threads after the decision is clear. Use a single shell
call when several `gh`/`git`/`jq` commands are deterministic and non-interactive.

Ask the user before changing repository content such as source, docs, config,
tests, PR title/body, or generated files that will be committed. Present a
concise triage table and one grouped approval request for all clear proposed
content edits. If a comment's validity is uncertain, conflicts with
requirements, or implies a design choice, ask for guidance and leave that thread
open until the user decides.

After approved edits are verified, prefer `scripts/reply-and-resolve-threads.sh`
with a JSON plan to batch GitHub replies and resolve mutations. Do not use this
script for threads marked `needs-clarification`.

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth login`).
- `jq` available for readable GraphQL output.
- `repo` scope permission to post comments and resolve threads.

## Operations

### A — Fetch PR Details

Gather minimum context: `owner/repo` and PR number.

```bash
gh pr view <PR_NUMBER> --repo <OWNER/REPO> \
  --json number,title,state,author,baseRefName,headRefName,url,body,reviews,commits
```

Normalize output into: title, state, author, base/head branches, URL, and review summary.

### B — Create Pull Request

Require: `owner/repo`, `base` branch, `head` branch, title, and body.

1. Verify no existing open PR already targets the same `head -> base`.
2. Create the PR:

```bash
gh pr create \
  --repo <OWNER/REPO> \
  --title "<title>" \
  --body "<body>" \
  --base <base> \
  --head <branch>
  # add --draft if requested
```

3. Return created PR number and URL.

### C — Fetch Unresolved Review Threads

Require: `owner/repo` and PR number.

Prefer the bundled summary script:

```bash
scripts/pr-thread-summary.sh <PR_NUMBER>
```

It prints repository/PR context plus unresolved review threads and writes the
full unresolved-thread JSON to a temporary file. Use the playbook GraphQL query
only when the script is unavailable or pagination/custom fields are needed.

### D — Triage, Reply, and Resolve Threads

For each unresolved thread, decide:

| Decision | Criteria |
|---|---|
| `fix` | Correctness, security, reliability, or contract mismatch |
| `no-fix-explain` | Preference-only feedback or already satisfied; respond with rationale |
| `needs-clarification` | Ambiguous or conflicts with requirements; ask a targeted follow-up |

Then:
1. Inspect affected files in parallel where possible.
2. Present proposed content edits for user approval before modifying files.
3. Implement only the approved `fix` edits.
4. Run targeted verification (tests/lint/typecheck for touched areas).
5. Batch replies and resolve mutations with `scripts/reply-and-resolve-threads.sh`
   or one shell call where possible.
6. Resolve a thread **only after** reply is posted and verification is green.
7. Leave `needs-clarification` threads open.

## Safety Rules

- Do not perform write actions beyond requested scope.
- Do not change repository content without explicit user approval during comment triage.
- Do not resolve a thread without first posting a reply.
- Do not merge, close, or request reviewers unless explicitly asked.
- Do not force-push or rewrite history unless explicitly asked.
- Never expose tokens or secrets in output.
- Flag permission/authentication failures with concrete remediation steps.

## Output Format

1. **Scope** — repository, PR number, and requested operation.
2. **Actions Taken** — CLI commands executed (high level, no secret payloads).
3. **Results** — PR details, created PR URL, triage decisions, approvals requested, threads resolved.
4. **Open Items** — remaining threads, blockers, guidance needed, or data gaps.
