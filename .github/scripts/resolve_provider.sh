#!/usr/bin/env bash
set -euo pipefail

labels_json="${LABELS_JSON:-[]}"
default_provider="${DEFAULT_PROVIDER:-codex}"

normalize_provider() {
  case "${1,,}" in
    claude)
      echo "claude"
      ;;
    codex|"")
      echo "codex"
      ;;
    *)
      echo "codex"
      ;;
  esac
}

codex_count="$(jq '[.[] | select(. == "agent:codex")] | length' <<<"$labels_json")"
claude_count="$(jq '[.[] | select(. == "agent:claude")] | length' <<<"$labels_json")"

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
    provider_label="agent:codex"
    mention="@codex"
    ;;
  claude)
    provider_label="agent:claude"
    mention="@claude"
    ;;
esac

{
  echo "provider=$provider"
  echo "provider_label=$provider_label"
  echo "mention=$mention"
} >> "$GITHUB_OUTPUT"
