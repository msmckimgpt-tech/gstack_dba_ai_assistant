#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=.github/scripts/contract_utils.sh
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$script_dir/contract_utils.sh"

labels_json="${LABELS_JSON:-[]}"
default_provider="${DEFAULT_PROVIDER:-$(contract_get '.providers.default')}"
codex_label="$(contract_get '.providers.labels.codex')"
claude_label="$(contract_get '.providers.labels.claude')"

normalize_provider() {
  local fallback_provider
  fallback_provider="$(contract_get '.providers.default')"
  case "${1,,}" in
    claude)
      echo "claude"
      ;;
    codex|"")
      echo "codex"
      ;;
    *)
      echo "$fallback_provider"
      ;;
  esac
}

codex_count="$(jq --arg label "$codex_label" '[.[] | select(. == $label)] | length' <<<"$labels_json")"
claude_count="$(jq --arg label "$claude_label" '[.[] | select(. == $label)] | length' <<<"$labels_json")"

if [[ "$codex_count" != "0" && "$claude_count" != "0" ]]; then
  echo "Both agent:codex and agent:claude labels are present." >&2
  exit 1
fi

if [[ "$codex_count" != "0" ]]; then
  provider="codex"
elif [[ "$claude_count" != "0" ]]; then
  provider="claude"
else
  provider="$(normalize_provider "$default_provider")"
fi

case "$provider" in
  codex)
    provider_label="$codex_label"
    mention="@codex"
    ;;
  claude)
    provider_label="$claude_label"
    mention="@claude"
    ;;
esac

{
  echo "provider=$provider"
  echo "provider_label=$provider_label"
  echo "mention=$mention"
} >> "$GITHUB_OUTPUT"
