#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=.github/scripts/contract_utils.sh
source "$script_dir/contract_utils.sh"

labels_json="${LABELS_JSON:-[]}"
type_filter="$(contract_get '.issues.types | map(select(length > 0) | @json) | join(" or . == ")')"
blocked_filter="$(contract_get '.issues.status_labels.blocking | map(select(length > 0) | @json) | join(" or . == ")')"

type_count="$(jq "[.[] | select(. == ${type_filter})] | length" <<<"$labels_json")"
blocked_count="$(jq "[.[] | select(. == ${blocked_filter})] | length" <<<"$labels_json")"

should_run="false"
reason="missing supported issue type label"

if [[ "$type_count" != "0" && "$blocked_count" == "0" ]]; then
  should_run="true"
  reason="eligible for execution"
elif [[ "$blocked_count" != "0" ]]; then
  reason="blocked by active status label"
fi

append_output "should_run" "$should_run"
append_output "reason" "$reason"
