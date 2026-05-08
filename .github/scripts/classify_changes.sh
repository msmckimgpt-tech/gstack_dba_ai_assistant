#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=.github/scripts/contract_utils.sh
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$script_dir/contract_utils.sh"

base_ref="${BASE_REF:-main}"
if [[ -n "${CHANGED_FILES:-}" ]]; then
  files="${CHANGED_FILES}"
else
  files="$(git diff --name-only "origin/${base_ref}...HEAD")"
fi

docs_only="true"
risk_manual="false"
changed_count="0"

mapfile -t docs_only_patterns < <(contract_get '.classifiers.docs_only_patterns[]')
mapfile -t risk_manual_patterns < <(contract_get '.classifiers.risk_manual_patterns[]')

matches_any() {
  local file="$1"
  shift
  local pattern

  for pattern in "$@"; do
    if [[ "$file" =~ $pattern ]]; then
      return 0
    fi
  done

  return 1
}

if [[ -n "$files" ]]; then
  changed_count="$(wc -l <<<"$files" | tr -d ' ')"
fi

while IFS= read -r file; do
  [[ -z "$file" ]] && continue

  if ! matches_any "$file" "${docs_only_patterns[@]}"; then
    docs_only="false"
  fi

  if matches_any "$file" "${risk_manual_patterns[@]}"; then
    risk_manual="true"
  fi
done <<<"$files"

append_output "docs_only" "$docs_only"
append_output "risk_manual" "$risk_manual"
append_output "changed_count" "$changed_count"
append_multiline_output "changed_files" "$files"
