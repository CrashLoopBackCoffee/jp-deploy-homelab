#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: pr-thread-summary.sh [PR_NUMBER] [--repo OWNER/REPO] [--host HOST]

Fetch PR context and unresolved review threads with one command. If PR_NUMBER is
omitted, gh resolves the PR for the current branch.
USAGE
}

pr_arg=""
repo_arg=""
host_arg=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --repo)
      repo_arg="${2:?--repo requires OWNER/REPO}"
      shift 2
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
      if [[ -n "$pr_arg" ]]; then
        echo "Only one PR number may be provided" >&2
        usage >&2
        exit 2
      fi
      pr_arg="$1"
      shift
      ;;
  esac
done

command -v gh >/dev/null || { echo "gh is required" >&2; exit 127; }
command -v jq >/dev/null || { echo "jq is required" >&2; exit 127; }

repo_view_args=()
pr_repo_args=()
if [[ -n "$repo_arg" ]]; then
  repo_view_args=("$repo_arg")
  pr_repo_args=(--repo "$repo_arg")
fi

if [[ -n "$host_arg" ]]; then
  export GH_HOST="$host_arg"
fi

repo_json="$(gh repo view "${repo_view_args[@]}" --json nameWithOwner,url)"
repo_full="$(jq -r '.nameWithOwner' <<<"$repo_json")"
repo_url="$(jq -r '.url' <<<"$repo_json")"
owner="${repo_full%%/*}"
repo="${repo_full#*/}"

if [[ -z "$host_arg" ]]; then
  host_arg="$(sed -E 's#^[a-zA-Z][a-zA-Z0-9+.-]*://([^/]+)/?.*#\1#' <<<"$repo_url")"
  export GH_HOST="$host_arg"
fi

gh auth status --hostname "$host_arg" >/dev/null

if [[ -n "$pr_arg" ]]; then
  pr_json="$(gh pr view "$pr_arg" "${pr_repo_args[@]}" --json number,title,state,author,baseRefName,headRefName,url,reviewDecision)"
else
  pr_json="$(gh pr view "${pr_repo_args[@]}" --json number,title,state,author,baseRefName,headRefName,url,reviewDecision)"
fi

pr_number="$(jq -r '.number' <<<"$pr_json")"
old_umask="$(umask)"
umask 077
threads_file="$(mktemp "${TMPDIR:-/tmp}/gh-pr-${pr_number}-unresolved-threads.XXXXXX")"
umask "$old_umask"

# shellcheck disable=SC2016
threads_response="$(gh api --hostname "$host_arg" graphql -f query='
query($owner:String!, $repo:String!, $pr:Int!) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$pr) {
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
}' -f owner="$owner" -f repo="$repo" -F pr="$pr_number")"

if jq -e '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage == true' <<<"$threads_response" >/dev/null; then
  echo "PR #${pr_number} has more than 100 review threads; rerun with paginated GraphQL handling before triage." >&2
  exit 3
fi

jq '.data.repository.pullRequest.reviewThreads.nodes | map(select(.isResolved == false))' <<<"$threads_response" > "$threads_file"

jq -r '
  "repository=\($repo)",
  "host=\($host)",
  "pr=#\($pr.number) \($pr.title)",
  "state=\($pr.state) reviewDecision=\($pr.reviewDecision // "UNKNOWN")",
  "head=\($pr.headRefName) base=\($pr.baseRefName)",
  "url=\($pr.url)",
  "unresolved_count=\(length)",
  (
    .[] |
    "thread=\(.threadId) path=\(.path):\(.line // "null") outdated=\(.isOutdated) latest_author=\(.comments.nodes[-1].author.login // "unknown") body=\((.comments.nodes[-1].body // "") | gsub("[\r\n]+"; " ") | .[0:300])"
  ),
  "threads_json=\($threads_file)"
' --arg repo "$repo_full" --arg host "$host_arg" --arg threads_file "$threads_file" --argjson pr "$pr_json" "$threads_file"
