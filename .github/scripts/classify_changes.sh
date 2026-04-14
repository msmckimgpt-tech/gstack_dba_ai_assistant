#!/usr/bin/env bash
set -euo pipefail

base_ref="${BASE_REF:-main}"
files="$(git diff --name-only "origin/${base_ref}...HEAD")"

docs_only="true"
risk_manual="false"
changed_count="0"

if [[ -n "$files" ]]; then
  changed_count="$(wc -l <<<"$files" | tr -d ' ')"
fi

while IFS= read -r file; do
  [[ -z "$file" ]] && continue

  if [[ ! "$file" =~ ^(README\.md|CONTRIBUTING\.md|docs/.*|unit/[^/]+/docs/.*|\.github/ISSUE_TEMPLATE/.*|\.github/pull_request_template\.md)$ ]]; then
    docs_only="false"
  fi

  if [[ "$file" =~ ^(\.github/workflows/.*|AGENTS\.md|CLAUDE\.md|docs/SECURITY\.md)$ ]]; then
    risk_manual="true"
  fi
done <<<"$files"

{
  echo "docs_only=$docs_only"
  echo "risk_manual=$risk_manual"
  echo "changed_count=$changed_count"
  echo "changed_files<<EOF"
  printf '%s\n' "$files"
  echo "EOF"
} >> "$GITHUB_OUTPUT"
