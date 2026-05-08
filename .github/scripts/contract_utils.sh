#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
contract_file="${CONTRACT_FILE:-$repo_root/.github/automation-contract.json}"

contract_get() {
  jq -er "$1" "$contract_file"
}

append_output() {
  if [[ -z "${GITHUB_OUTPUT:-}" ]]; then
    printf '%s=%s\n' "$1" "$2"
    return
  fi

  printf '%s=%s\n' "$1" "$2" >> "$GITHUB_OUTPUT"
}

append_multiline_output() {
  if [[ -z "${GITHUB_OUTPUT:-}" ]]; then
    printf '%s<<EOF\n%s\nEOF\n' "$1" "$2"
    return
  fi

  {
    printf '%s<<EOF\n' "$1"
    printf '%s\n' "$2"
    printf 'EOF\n'
  } >> "$GITHUB_OUTPUT"
}
