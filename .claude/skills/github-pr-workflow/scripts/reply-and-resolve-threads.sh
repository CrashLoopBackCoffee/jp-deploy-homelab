#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: reply-and-resolve-threads.sh --host HOST PLAN.json

PLAN.json must be an array of objects:
[
  {
    "threadId": "PRRT_or_node_id",
    "body": "Reply text to post before resolving"
  }
]

The script posts each reply and resolves the same thread. Use only after the
triage decision is clear, required content changes are approved and verified,
and no listed thread needs clarification.
USAGE
}

host_arg=""
plan_file=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --host|--hostname)
      host_arg="${2:?--host requires a hostname}"
      shift 2
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [[ -n "$plan_file" ]]; then
        echo "Only one plan file may be provided" >&2
        usage >&2
        exit 2
      fi
      plan_file="$1"
      shift
      ;;
  esac
done

[[ -n "$host_arg" ]] || { echo "--host is required" >&2; usage >&2; exit 2; }
[[ -n "$plan_file" ]] || { echo "PLAN.json is required" >&2; usage >&2; exit 2; }
[[ -f "$plan_file" ]] || { echo "Plan file not found: $plan_file" >&2; exit 2; }

command -v gh >/dev/null || { echo "gh is required" >&2; exit 127; }
command -v jq >/dev/null || { echo "jq is required" >&2; exit 127; }

gh auth status --hostname "$host_arg" >/dev/null

jq -e '
  type == "array"
  and all(.[]; (.threadId | type == "string" and length > 0) and (.body | type == "string" and length > 0))
' "$plan_file" >/dev/null

# shellcheck disable=SC2016
reply_query='mutation($threadId:ID!, $body:String!) {
  addPullRequestReviewThreadReply(input:{pullRequestReviewThreadId:$threadId, body:$body}) {
    comment { url }
  }
}'
# shellcheck disable=SC2016
resolve_query='mutation($threadId:ID!) {
  resolveReviewThread(input:{threadId:$threadId}) {
    thread { id isResolved }
  }
}'

jq -c '.[]' "$plan_file" | while IFS= read -r item; do
  thread_id="$(jq -r '.threadId' <<<"$item")"
  body="$(jq -r '.body' <<<"$item")"

  comment_url="$(
    gh api --hostname "$host_arg" graphql \
      -f query="$reply_query" \
      -f threadId="$thread_id" \
      -f body="$body" \
      --jq '.data.addPullRequestReviewThreadReply.comment.url'
  )"
  resolved="$(
    gh api --hostname "$host_arg" graphql \
      -f query="$resolve_query" \
      -f threadId="$thread_id" \
      --jq '.data.resolveReviewThread.thread.isResolved'
  )"
  printf '%s\tresolved=%s\t%s\n' "$thread_id" "$resolved" "$comment_url"
done
