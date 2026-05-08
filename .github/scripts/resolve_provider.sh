#!/usr/bin/env bash
set -euo pipefail

# shellcheck source=.github/scripts/contract_utils.sh
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$script_dir/contract_utils.sh"

labels_json="${LABELS_JSON:-[]}"
default_provider="${DEFAULT_PROVIDER:-$(contract_get '.providers.default')}"
claude_label="$(contract_get '.providers.labels.claude')"

normalize_provider() {
  local fallback_provider
  fallback_provider="$(contract_get '.providers.default')"
  case "${1,,}" in
    claude|"")
      echo "claude"
      ;;
    *)
      echo "$fallback_provider"
      ;;
  esac
}

claude_count="$(jq --arg label "$claude_label" '[.[] | select(. == $label)] | length' <<<"$labels_json")"
unknown_provider_count="$(jq '[.[] | select(startswith("agent:") and . != "agent:claude")] | length' <<<"$labels_json")"

if [[ "$unknown_provider_count" != "0" ]]; then
  echo "Unsupported agent:* label present; only agent:claude is allowed." >&2
  exit 1
fi

if [[ "$claude_count" != "0" ]]; then
  provider="claude"
else
  provider="$(normalize_provider "$default_provider")"
fi

case "$provider" in
  claude)
    provider_label="$claude_label"
    mention="@claude"
    ;;
  *)
    echo "Unsupported provider: $provider" >&2
    exit 1
    ;;
esac

{
  echo "provider=$provider"
  echo "provider_label=$provider_label"
  echo "mention=$mention"
} >> "$GITHUB_OUTPUT"
