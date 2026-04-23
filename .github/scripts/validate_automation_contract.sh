#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=.github/scripts/contract_utils.sh
source "$script_dir/contract_utils.sh"

cd "$repo_root"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

assert_contains() {
  local file="$1"
  local pattern="$2"

  if ! grep -Eq "$pattern" "$file"; then
    fail "$file does not match pattern: $pattern"
  fi
}

assert_not_contains() {
  local file="$1"
  local pattern="$2"

  if grep -Eq "$pattern" "$file"; then
    fail "$file unexpectedly matches pattern: $pattern"
  fi
}

read_output() {
  local file="$1"
  local key="$2"
  sed -n "s/^${key}=//p" "$file" | tail -n 1
}

jq -e '
  (.providers.allowed | length == 1) and
  (.providers.allowed[0] == "claude") and
  (.issues.types | length == 3) and
  (.checks.required | length == 4) and
  (.commits.subject_regex | length > 0) and
  (.branches.public_pr_regex | length > 0)
' "$contract_file" >/dev/null || fail "automation contract schema validation failed"

assert_contains "AGENTS.md" 'issue/<issue-number>-<short-slug>'
assert_contains "AGENTS.md" 'ai/<agent-id>/<issue-number>/<slice>'
assert_contains "AGENTS.md" '`main` 직접 push 또는 로컬 `main` 병합은 금지한다'
assert_not_contains "AGENTS.md" 'git push origin main'

assert_contains "CONTRIBUTING.md" '공개 PR 브랜치: `issue/<issue-number>-<short-slug>`'
assert_contains "CONTRIBUTING.md" '내부 병렬 브랜치: `ai/<agent-id>/<issue-number>/<slice>`'
assert_contains "CONTRIBUTING.md" '`status:ready`는 권장 라벨'

assert_contains "docs/GITHUB_AUTOMATION.md" '공개 PR 브랜치는 항상 `issue/<번호>-<short-slug>`'
assert_contains "docs/GITHUB_AUTOMATION.md" '내부 병렬 작업 브랜치는 `ai/<agent-id>/<issue-number>/<slice>`'
assert_contains "docs/GITHUB_AUTOMATION.md" '`status:ready`는 권장 라벨'

assert_not_contains "docs/PROJECT.md" '현재 설정: 없음'
assert_contains "docs/PROJECT.md" 'GitHub Actions'

assert_contains "docs/CODEBASE_MAP.md" 'PB-0001 ~ PB-0006'
assert_contains "docs/CODEBASE_MAP.md" '\.github/automation-contract\.json'

for check_name in $(contract_get '.checks.required[]'); do
  assert_contains "docs/GITHUB_AUTOMATION.md" "\`${check_name}\`"
done

provider_output="$(mktemp)"
if LABELS_JSON='["agent:codex"]' GITHUB_OUTPUT="$provider_output" "$script_dir/resolve_provider.sh" >/dev/null 2>&1; then
  rm -f "$provider_output"
  fail "resolve_provider.sh must fail when an unsupported agent:* label is present"
fi
rm -f "$provider_output"

provider_output="$(mktemp)"
LABELS_JSON='["agent:claude"]' GITHUB_OUTPUT="$provider_output" "$script_dir/resolve_provider.sh" >/dev/null
[[ "$(read_output "$provider_output" provider)" == "claude" ]] || fail "resolve_provider.sh must resolve agent:claude label to claude"
rm -f "$provider_output"

provider_output="$(mktemp)"
LABELS_JSON='[]' GITHUB_OUTPUT="$provider_output" "$script_dir/resolve_provider.sh" >/dev/null
[[ "$(read_output "$provider_output" provider)" == "claude" ]] || fail "resolve_provider.sh must fall back to claude when no provider label is present"
rm -f "$provider_output"

gate_output="$(mktemp)"
LABELS_JSON='["feature"]' GITHUB_OUTPUT="$gate_output" "$script_dir/issue_gate.sh" >/dev/null
[[ "$(read_output "$gate_output" should_run)" == "true" ]] || fail "issue gate should run without status:ready"
rm -f "$gate_output"

gate_output="$(mktemp)"
LABELS_JSON='["task","status:in-progress"]' GITHUB_OUTPUT="$gate_output" "$script_dir/issue_gate.sh" >/dev/null
[[ "$(read_output "$gate_output" should_run)" == "false" ]] || fail "issue gate must block in-progress issues"
rm -f "$gate_output"

classify_output="$(mktemp)"
CHANGED_FILES=$'README.md\ndocs/GITHUB_AUTOMATION.md' GITHUB_OUTPUT="$classify_output" "$script_dir/classify_changes.sh" >/dev/null
[[ "$(read_output "$classify_output" docs_only)" == "true" ]] || fail "docs-only classification failed"
[[ "$(read_output "$classify_output" risk_manual)" == "false" ]] || fail "docs-only changes must not be risk manual"
rm -f "$classify_output"

classify_output="$(mktemp)"
CHANGED_FILES=$'AGENTS.md\n.github/workflows/ai-review.yml' GITHUB_OUTPUT="$classify_output" "$script_dir/classify_changes.sh" >/dev/null
[[ "$(read_output "$classify_output" docs_only)" == "false" ]] || fail "policy file changes must not be docs-only"
[[ "$(read_output "$classify_output" risk_manual)" == "true" ]] || fail "sensitive changes must be risk manual"
rm -f "$classify_output"

subject="$(
  ISSUE_NUMBER=12 \
  ISSUE_TITLE='[Bug] 세션 정리 실패 수정' \
  LABELS_JSON='["bug"]' \
  COMMIT_SCOPE='project' \
  "$script_dir/format_issue_commit.sh"
)"
subject_regex="$(contract_get '.commits.subject_regex')"
[[ "$subject" =~ $subject_regex ]] || fail "formatted commit subject does not satisfy contract regex"

echo "automation contract validation passed"
