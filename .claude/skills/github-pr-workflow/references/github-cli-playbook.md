# GitHub CLI Playbook

Concrete `gh` CLI commands and GraphQL snippets for the `github-pr-workflow` skill.

## Prerequisites

```bash
gh auth status          # must succeed
jq --version            # needed for readable GraphQL output
```

## Low-Approval Helper Scripts

Prefer bundled scripts for repeated triage operations. They batch deterministic
surrounding work into one approval while keeping content changes behind the
approval gate described in `SKILL.md`.

Fetch PR context and unresolved threads:

```bash
~/.agents/skills/github-pr-workflow/scripts/pr-thread-summary.sh <PR_NUMBER>
```

Post replies and resolve addressed threads from a JSON plan:

```bash
cat > /tmp/thread-plan.json <<'JSON'
[
  {
    "threadId": "PRRT_or_node_id",
    "body": "Implemented this in <commit> by <change>. Verified with: <command>."
  }
]
JSON

~/.agents/skills/github-pr-workflow/scripts/reply-and-resolve-threads.sh \
  --host <HOST> /tmp/thread-plan.json
```

---

## A) Fetch PR Details

```bash
owner="OWNER"
repo="REPO"
pr="123"

gh pr view "$pr" --repo "$owner/$repo" \
  --json number,title,state,author,baseRefName,headRefName,url,body,reviews,commits
```

List all open PRs:

```bash
gh pr list --repo "$owner/$repo" --state open \
  --json number,title,author,baseRefName,headRefName,url
```

---

## B) Create a Pull Request

```bash
owner="OWNER"
repo="REPO"
base="main"
head="feature/my-branch"
title="Your PR title"
body="Summary of changes and testing notes."

gh pr create \
  --repo "$owner/$repo" \
  --title "$title" \
  --body "$body" \
  --base "$base" \
  --head "$head"
  # add --draft for draft PRs
```

Check for an existing open PR before creating:

```bash
gh pr list --repo "$owner/$repo" --state open \
  --json number,headRefName,baseRefName \
  | jq --arg head "$head" --arg base "$base" \
    '.[] | select(.headRefName == $head and .baseRefName == $base)'
```

---

## C) Fetch Unresolved Review Threads

```bash
owner="OWNER"
repo="REPO"
pr="123"

gh api graphql -f query='
query($owner:String!, $repo:String!, $pr:Int!) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$pr) {
      url
      reviewThreads(first:100) {
        pageInfo { hasNextPage endCursor }
        nodes {
          threadId: id
          isResolved
          isOutdated
          path
          line
          comments(last:20) {
            nodes {
              id
              author { login }
              body
              createdAt
              url
            }
          }
        }
      }
    }
  }
}' -f owner="$owner" -f repo="$repo" -F pr="$pr" \
| jq '.data.repository.pullRequest.reviewThreads.nodes
      | map(select(.isResolved == false))'
```

> **Note:** `reviewThreads(first:100)` caps at 100 threads per page. For PRs
> with more threads, use `pageInfo.hasNextPage` / `pageInfo.endCursor` to
> paginate with an `after:` argument.

---

## D) Post a Thread Reply

Use the `threadId` (format: `PRRT_xxx`) from the query above.

For multiple addressed threads, prefer
`scripts/reply-and-resolve-threads.sh` instead of calling this mutation
repeatedly.

```bash
thread_id="PRRT_xxx"
reply_body="Implemented the null-check in parser initialization and added regression coverage in tests/parser/test_init.py."

gh api graphql -f query='
mutation($threadId:ID!, $body:String!) {
  addPullRequestReviewThreadReply(input:{pullRequestReviewThreadId:$threadId, body:$body}) {
    comment { url }
  }
}' -f threadId="$thread_id" -f body="$reply_body"
```

---

## E) Resolve a Thread

Resolve **only after** a reply is posted and verification for touched areas is green.

```bash
thread_id="PRRT_xxx"

gh api graphql -f query='
mutation($threadId:ID!) {
  resolveReviewThread(input:{threadId:$threadId}) {
    thread { id isResolved }
  }
}' -f threadId="$thread_id"
```

---

## F) Unresolve a Thread (if resolved by mistake)

```bash
thread_id="PRRT_xxx"

gh api graphql -f query='
mutation($threadId:ID!) {
  unresolveReviewThread(input:{threadId:$threadId}) {
    thread { id isResolved }
  }
}' -f threadId="$thread_id"
```

---

## Triage Decision Table

| Label | When to use |
|---|---|
| `fix` | Correctness, security, reliability, or contract mismatch |
| `no-fix-explain` | Preference-only or already addressed; reply with rationale and evidence |
| `needs-clarification` | Ambiguous or conflicts with requirements; ask a targeted follow-up |

## Suggested Reply Format

Keep replies concrete and traceable:

```text
Implemented this by <change summary>. Updated <file(s)> and added/updated <test(s)>.
Verified with: <command>. This addresses the concern about <risk/behavior>.
```

---

## Prompt Examples That Should Trigger This Skill

- "Create a PR from `feature/auth` into `main` in `acme/api`."
- "Fetch all review comments from PR #128 in `acme/api`."
- "Get PR #42 status and summarize requested changes."
- "Resolve all addressed review threads on PR #10."
- "List open PRs for `acme/web` with review decisions."

## Non-Goals

- Repository administration (branch protection, webhooks).
- Auto-merging or force-updating branches unless explicitly asked.
- Secret management or token issuance.
