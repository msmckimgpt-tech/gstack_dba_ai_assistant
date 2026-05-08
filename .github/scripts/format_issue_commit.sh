#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=.github/scripts/contract_utils.sh
source "$script_dir/contract_utils.sh"

issue_number="${ISSUE_NUMBER:?ISSUE_NUMBER is required}"
issue_title="${ISSUE_TITLE:?ISSUE_TITLE is required}"
labels_json="${LABELS_JSON:-[]}"
commit_scope="${COMMIT_SCOPE:-$(contract_get '.commits.default_scope')}"

issue_type="$(
  jq -r '
    map(select(. == "feature" or . == "bug" or . == "task"))[0] // "task"
  ' <<<"$labels_json"
)"

commit_type="$(contract_get ".commits.issue_type_to_commit_type.${issue_type}")"
summary="$(
  sed -E 's/^\[[^]]+\][[:space:]]*//' <<<"$issue_title" |
    sed -E 's/[[:space:]]+/ /g; s/^ //; s/ $//'
)"

if [[ -z "$summary" ]]; then
  summary="issue ${issue_number}"
fi

subject="${commit_type}(${commit_scope}): ${summary} (#${issue_number})"
printf '%s\n' "$subject"
