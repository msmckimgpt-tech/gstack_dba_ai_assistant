#!/usr/bin/env bash
#
# verify-completion.sh — AI가 작업 완료를 선언하기 전에 의무적으로 호출하는 검증 도구.
#
# 설계 근거: AGENTS.md §16.3 (Git 동기화 절차 — 이 스크립트가 흡수)
#           AGENTS.md §17 (외부 앵커 정책)
#           ~/.gstack/projects/ai_delegated_dev_template/root-main-design-20260423-235935.md
#
# Requires: bash >= 4, git >= 2.20, awk (POSIX), grep (POSIX), date (POSIX)
# NOT required: jq (deliberately avoided for portability)
#
# Usage:
#   bin/verify-completion.sh --pre-commit <feature-id>
#   bin/verify-completion.sh --post-commit <feature-id>
#   bin/verify-completion.sh --shared
#   bin/verify-completion.sh --help
#
# Exit codes:
#   0 — all checks pass
#   1 — one or more checks failed (stderr lists hints)
#   2 — usage error (bad args, not in git repo, etc.)
#
# Output format (stderr, one line per check):
#   CHECK#<N> PASS <name>
#   CHECK#<N> FAIL <name> :: <hint>
#
# Pilot scope (v1): checks #2, #3, #4, #6, #7, #8.
# Deferred to v1.1: check #1 (feature file scope), check #5 (STATUS.md).

set -euo pipefail

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

readonly MIN_BODY_CHARS=200
readonly BOOTSTRAP_GRACE_HOURS=24

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------

log_check() {
  local num="$1" status="$2" name="$3" hint="${4:-}"
  if [ -n "$hint" ]; then
    printf 'CHECK#%s %s %s :: %s\n' "$num" "$status" "$name" "$hint" >&2
  else
    printf 'CHECK#%s %s %s\n' "$num" "$status" "$name" >&2
  fi
}

die() {
  printf 'ERROR: %s\n' "$1" >&2
  exit "${2:-2}"
}

usage() {
  cat >&2 <<'EOF'
Usage:
  bin/verify-completion.sh --pre-commit <feature-id>    # before git commit
  bin/verify-completion.sh --post-commit <feature-id>   # after git commit (HEAD check)
  bin/verify-completion.sh --shared                     # shared/ scope commits
  bin/verify-completion.sh --help                       # show this message

Feature IDs take the form: feature-NNNN-name or META-NNNN-name
EOF
  exit 2
}

# -----------------------------------------------------------------------------
# Environment validation
# -----------------------------------------------------------------------------

require_git_repo() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    die "not inside a git work tree"
  fi
  # Jump to repo root so relative paths below work regardless of invocation cwd.
  cd "$(git rev-parse --show-toplevel)"
}

validate_feature_id() {
  local fid="$1"
  if [[ ! "$fid" =~ ^(feature|META)-[0-9]+(-[a-zA-Z0-9-]+)?$ ]]; then
    die "invalid feature-id: $fid (expected: feature-NNNN-name or META-NNNN-name)"
  fi
}

feature_dir() {
  local fid="$1"
  # Search for the feature directory (exact or prefix match)
  local matches
  matches=$(find unit -maxdepth 1 -type d -name "${fid}*" 2>/dev/null | head -5)
  if [ -z "$matches" ]; then
    die "feature directory not found: unit/${fid}*"
  fi
  # If exact match exists, prefer it; otherwise use the single prefix match
  local exact="unit/${fid}"
  if [ -d "$exact" ]; then
    printf '%s\n' "$exact"
    return
  fi
  local count
  count=$(printf '%s\n' "$matches" | wc -l | tr -d ' ')
  if [ "$count" -gt 1 ]; then
    die "ambiguous feature-id: multiple matches under unit/"
  fi
  printf '%s\n' "$matches"
}

# -----------------------------------------------------------------------------
# META detection (operational vs meta layer)
# Path convention: edits under these paths auto-switch to META mode.
# META commits skip checks that target operational feature docs.
# -----------------------------------------------------------------------------

is_meta_path() {
  local path="$1"
  case "$path" in
    AGENTS.md|CLAUDE.md) return 0 ;;
    bin/*|shared/docs/*|docs/*) return 0 ;;
    unit/_template/*) return 0 ;;
    unit/META-*) return 0 ;;
    TEMPLATE_CHANGELOG.md|CONTRIBUTING.md) return 0 ;;
    *) return 1 ;;
  esac
}

# Return 0 if ALL files in the provided list are META paths (pure-meta commit).
# The AGENTS.md §17 rule: pure-meta commits skip verify-completion entirely.
# Mixed commits (meta + operational) are treated as operational (strict gate).
is_pure_meta_changeset() {
  local any=0
  local f
  for f in "$@"; do
    any=1
    if ! is_meta_path "$f"; then
      return 1
    fi
  done
  [ "$any" = "1" ]
}

# -----------------------------------------------------------------------------
# Diff helpers
# -----------------------------------------------------------------------------

staged_files() {
  git diff --cached --name-only
}

unstaged_files() {
  git diff --name-only
}

all_changed_files() {
  { staged_files; unstaged_files; } | sort -u
}

head_commit_files() {
  git log -1 --name-only --format='' | grep -v '^$' || true
}

# Check if any changed file matches a glob-ish pattern under the feature dir.
staged_or_unstaged_touches() {
  local path="$1"
  all_changed_files | grep -Fx "$path" >/dev/null 2>&1
}

staged_touches() {
  local path="$1"
  staged_files | grep -Fx "$path" >/dev/null 2>&1
}

# -----------------------------------------------------------------------------
# Code-file detection (for check #4: FUNCTION.md companion rule)
# Code file = anything under feature_dir except docs/** or tests/README.md scaffolds.
# -----------------------------------------------------------------------------

is_code_file() {
  local path="$1" fdir="$2"
  case "$path" in
    "${fdir}/docs/"*) return 1 ;;    # docs don't count as code
    "${fdir}/"*) return 0 ;;          # everything else under feature = code
    *) return 1 ;;
  esac
}

# -----------------------------------------------------------------------------
# ANCHOR.md frontmatter helpers
# canonical_created_at: minimum of frontmatter created_at vs git first-add timestamp.
# Prevents frontmatter manipulation for grace extension.
# -----------------------------------------------------------------------------

read_frontmatter_created_at() {
  local anchor_path="$1"
  # Extract YAML created_at field (first occurrence).
  awk '
    /^---$/ { n++; next }
    n == 1 && /^created_at:/ {
      sub(/^created_at:[[:space:]]*/, "")
      gsub(/["\047]/, "")
      print
      exit
    }
  ' "$anchor_path"
}

git_first_add_iso() {
  local path="$1"
  # Most recent add commit of this path. Fallback silent if file untracked.
  git log --follow --diff-filter=A --format=%aI -- "$path" 2>/dev/null | tail -1
}

# Compare two ISO8601 timestamps; echo the earlier one.
earlier_iso() {
  local a="$1" b="$2"
  if [ -z "$a" ]; then printf '%s\n' "$b"; return; fi
  if [ -z "$b" ]; then printf '%s\n' "$a"; return; fi
  if [ "$(printf '%s\n%s\n' "$a" "$b" | sort | head -1)" = "$a" ]; then
    printf '%s\n' "$a"
  else
    printf '%s\n' "$b"
  fi
}

# Returns 0 if canonical_created_at is within BOOTSTRAP_GRACE_HOURS of now.
within_bootstrap_grace() {
  local created_iso="$1"
  [ -n "$created_iso" ] || return 1
  local created_epoch now_epoch diff_h
  created_epoch=$(date -d "$created_iso" +%s 2>/dev/null || echo "")
  [ -n "$created_epoch" ] || return 1
  now_epoch=$(date -u +%s)
  diff_h=$(( (now_epoch - created_epoch) / 3600 ))
  [ "$diff_h" -lt "$BOOTSTRAP_GRACE_HOURS" ]
}

# -----------------------------------------------------------------------------
# ANCHOR.md §1~§3 blank check
# A section is "blank" if it contains only placeholder text like "(작성 필요...)"
# or has zero non-comment non-heading content lines.
# -----------------------------------------------------------------------------

section_is_blank() {
  local anchor_path="$1" section="$2"
  # Extract the section body (between "## §N" and the next "## " or EOF),
  # strip HTML comments, strip blank lines, strip the heading itself,
  # check if any substantive non-placeholder text remains.
  awk -v marker="## §${section}\\." '
    $0 ~ marker { in_sec = 1; next }
    in_sec && /^## / { in_sec = 0 }
    in_sec { print }
  ' "$anchor_path" \
    | awk '
      # Strip multi-line HTML comments
      /<!--/ { in_comment = 1 }
      in_comment { if (/-->/) in_comment = 0; next }
      { print }
    ' \
    | grep -Ev '^\s*$' \
    | grep -Ev '^\s*\(작성 필요' \
    | grep -Ev '^\s*\(엔트리 없음' \
    | head -3 \
    | grep -q .
  # grep -q returns 0 when content found → section NOT blank. Invert:
  [ $? -ne 0 ]
}

# -----------------------------------------------------------------------------
# ANCHOR.md §4 entry quality gate
# Entry format (markdown h3):
#   ### <ISO8601> — source: <source-spec>
#   **challenge:** <one line>
#   **body:**
#   <body paragraph(s)>
#
# Quality requirements (pilot):
#   - source matches: human:<name>
#   - challenge field present and non-empty
#   - body is ≥ MIN_BODY_CHARS non-whitespace characters
# -----------------------------------------------------------------------------

extract_section_4() {
  local anchor_path="$1"
  awk '
    /^## §4\./ { in_sec = 1; next }
    in_sec && /^## / { in_sec = 0 }
    in_sec { print }
  ' "$anchor_path"
}

# Parse §4 and return 0 if at least one well-formed entry exists; 1 otherwise.
# Writes rejection reasons (per-entry) to the global REJECT_REASONS array.
declare -a REJECT_REASONS
declare -g GOOD_ENTRY_COUNT

check_section_4_quality() {
  local anchor_path="$1"
  REJECT_REASONS=()
  GOOD_ENTRY_COUNT=0

  local section
  section=$(extract_section_4 "$anchor_path")

  if [ -z "$(printf '%s' "$section" | grep -v '^<!--' | grep -v '^-->' | grep -v '^\s*$' | grep -v '^(엔트리 없음')" ]; then
    REJECT_REASONS+=("§4 has no entries at all")
    return 1
  fi

  # Split into entries at lines starting with "### "
  local current_header="" current_body="" in_entry=0
  local entry_count=0
  local line

  # Use a temporary file to work around shell subshell var-loss.
  local tmpfile
  tmpfile=$(mktemp)
  printf '%s\n\n---END---' "$section" >"$tmpfile"

  # Strip HTML comments in-place (single pass).
  awk 'BEGIN{c=0} /<!--/{c=1} { if(!c) print } /-->/{c=0}' "$tmpfile" > "${tmpfile}.clean"
  mv "${tmpfile}.clean" "$tmpfile"

  # Parse entries
  while IFS= read -r line; do
    if [[ "$line" =~ ^###[[:space:]] ]] || [ "$line" = "---END---" ]; then
      # Evaluate the previous entry (if any)
      if [ "$in_entry" = "1" ]; then
        if _validate_entry "$current_header" "$current_body"; then
          entry_count=$((entry_count + 1))
        fi
      fi
      current_header="$line"
      current_body=""
      in_entry=1
      continue
    fi
    if [ "$in_entry" = "1" ]; then
      current_body+="${line}"$'\n'
    fi
  done < "$tmpfile"

  rm -f "$tmpfile"

  GOOD_ENTRY_COUNT="$entry_count"
  [ "$entry_count" -gt 0 ]
}

_validate_entry() {
  local header="$1" body="$2"
  # Header must match: ### <ISO8601> — source: <spec>
  if ! [[ "$header" =~ ^\#\#\#[[:space:]]+[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z[[:space:]]+—[[:space:]]+source:[[:space:]]+(human:[A-Za-z0-9_.-]+)[[:space:]]*$ ]]; then
    REJECT_REASONS+=("entry header malformed: $header")
    return 1
  fi
  # Body must contain challenge field
  if ! printf '%s' "$body" | grep -q '^\*\*challenge:\*\*'; then
    REJECT_REASONS+=("entry missing challenge field: $header")
    return 1
  fi
  # Body field must exist
  if ! printf '%s' "$body" | grep -q '^\*\*body:\*\*'; then
    REJECT_REASONS+=("entry missing body field: $header")
    return 1
  fi
  # Body content: lines after **body:** that aren't header-style
  local body_text
  body_text=$(printf '%s' "$body" | awk '
    /^\*\*body:\*\*/ { found = 1; next }
    found && /^\*\*[a-z]+:\*\*/ { found = 0 }
    found { print }
  ')
  local body_chars
  body_chars=$(printf '%s' "$body_text" | tr -d '[:space:]' | wc -c | tr -d ' ')
  if [ "$body_chars" -lt "$MIN_BODY_CHARS" ]; then
    REJECT_REASONS+=("entry body too short ($body_chars/$MIN_BODY_CHARS chars): $header")
    return 1
  fi
  # Anti-cargo-cult: reject "pass"/"looks good"/"OK" alone as body
  local body_lower
  body_lower=$(printf '%s' "$body_text" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:][:punct:]')
  case "$body_lower" in
    pass|passed|ok|okay|good|looksgood|lookedgood|fine|approved)
      REJECT_REASONS+=("entry body is cargo-cult filler: $header")
      return 1
      ;;
  esac
  return 0
}

# -----------------------------------------------------------------------------
# Check implementations (pilot core 6: #2, #3, #4, #6, #7, #8)
# -----------------------------------------------------------------------------

# Check #2: TASK.md has staged checkbox delta for this feature.
check_2_task_md() {
  local fdir="$1" mode="$2"
  local task_md="${fdir}/docs/TASK.md"

  if [ ! -f "$task_md" ]; then
    log_check 2 FAIL "TASK.md checkbox" "TASK.md not found at $task_md"
    return 1
  fi

  local diff_output=""
  case "$mode" in
    pre-commit) diff_output=$(git diff --cached -- "$task_md" 2>/dev/null || true) ;;
    post-commit) diff_output=$(git log -1 -p -- "$task_md" 2>/dev/null || true) ;;
  esac

  # Unstaged TASK.md in pre-commit mode is FAIL
  if [ "$mode" = "pre-commit" ]; then
    if git diff --name-only -- "$task_md" 2>/dev/null | grep -Fxq "$task_md"; then
      log_check 2 FAIL "TASK.md checkbox" "TASK.md has unstaged changes. Run: git add $task_md"
      return 1
    fi
  fi

  # A checkbox delta means adding/removing `[x]` or `[ ]` transitions.
  if printf '%s' "$diff_output" | grep -qE '^\+.*\[[ x]\]'; then
    log_check 2 PASS "TASK.md checkbox"
    return 0
  fi

  log_check 2 FAIL "TASK.md checkbox" "No checkbox delta in ${task_md}. Update Task Queue or Completion Checklist."
  return 1
}

# Check #3: MODIFY.md has a new appended entry for this feature.
check_3_modify_md() {
  local fdir="$1" mode="$2"
  local modify_md="${fdir}/docs/MODIFY.md"

  if [ ! -f "$modify_md" ]; then
    log_check 3 FAIL "MODIFY.md entry" "MODIFY.md not found at $modify_md"
    return 1
  fi

  local diff_output=""
  case "$mode" in
    pre-commit) diff_output=$(git diff --cached -- "$modify_md" 2>/dev/null || true) ;;
    post-commit) diff_output=$(git log -1 -p -- "$modify_md" 2>/dev/null || true) ;;
  esac

  # New append should introduce a CHG- header line
  if printf '%s' "$diff_output" | grep -qE '^\+## CHG-'; then
    log_check 3 PASS "MODIFY.md entry"
    return 0
  fi

  log_check 3 FAIL "MODIFY.md entry" "No new ## CHG- entry in ${modify_md}. Append a change log entry."
  return 1
}

# Check #4: FUNCTION.md is staged when code files are staged.
check_4_function_md() {
  local fdir="$1" mode="$2"
  local function_md="${fdir}/docs/FUNCTION.md"

  # Determine if any code file was staged/committed
  local changed_files
  case "$mode" in
    pre-commit) changed_files=$(staged_files) ;;
    post-commit) changed_files=$(head_commit_files) ;;
  esac

  local has_code=0
  local f
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    if is_code_file "$f" "$fdir"; then
      has_code=1
      break
    fi
  done <<<"$changed_files"

  if [ "$has_code" = "0" ]; then
    log_check 4 PASS "FUNCTION.md staged (no code change — skip)"
    return 0
  fi

  # Code file staged — FUNCTION.md must also be in the changeset
  if printf '%s' "$changed_files" | grep -Fxq "$function_md"; then
    log_check 4 PASS "FUNCTION.md staged"
    return 0
  fi

  log_check 4 FAIL "FUNCTION.md staged" "Code files changed but $function_md not staged. Update FUNCTION.md and re-add."
  return 1
}

# Check #6: ANCHOR.md §1~§3 blank check with 24h bootstrap grace.
check_6_anchor_1_3() {
  local fdir="$1"
  local anchor_md="${fdir}/docs/ANCHOR.md"

  if [ ! -f "$anchor_md" ]; then
    log_check 6 FAIL "ANCHOR §1-§3" "ANCHOR.md missing at $anchor_md. Run bin/anchor-migrate.sh or copy from _template."
    return 1
  fi

  # Canonical created_at: earlier of frontmatter vs git first-add
  local frontmatter_at git_first_at canonical_at
  frontmatter_at=$(read_frontmatter_created_at "$anchor_md" || true)
  git_first_at=$(git_first_add_iso "$anchor_md" || true)
  canonical_at=$(earlier_iso "$frontmatter_at" "$git_first_at")

  if within_bootstrap_grace "$canonical_at"; then
    log_check 6 PASS "ANCHOR §1-§3 (within 24h bootstrap grace)"
    return 0
  fi

  # Past grace: §1, §2, §3 must each have content
  local blanks=()
  local sec
  for sec in 1 2 3; do
    if section_is_blank "$anchor_md" "$sec"; then
      blanks+=("§${sec}")
    fi
  done

  if [ "${#blanks[@]}" -eq 0 ]; then
    log_check 6 PASS "ANCHOR §1-§3"
    return 0
  fi

  log_check 6 FAIL "ANCHOR §1-§3" "Blank sections: ${blanks[*]}. Fill in (grace expired at canonical_created_at=$canonical_at)."
  return 1
}

# Check #7: ANCHOR.md §4 quality gate (≥1 well-formed entry).
check_7_anchor_4() {
  local fdir="$1"
  local anchor_md="${fdir}/docs/ANCHOR.md"

  if [ ! -f "$anchor_md" ]; then
    log_check 7 FAIL "ANCHOR §4 quality" "ANCHOR.md missing at $anchor_md"
    return 1
  fi

  # Bootstrap grace: allow §4 to be empty during the first 24h too.
  local frontmatter_at git_first_at canonical_at
  frontmatter_at=$(read_frontmatter_created_at "$anchor_md" || true)
  git_first_at=$(git_first_add_iso "$anchor_md" || true)
  canonical_at=$(earlier_iso "$frontmatter_at" "$git_first_at")

  if within_bootstrap_grace "$canonical_at"; then
    log_check 7 PASS "ANCHOR §4 (within 24h bootstrap grace)"
    return 0
  fi

  if check_section_4_quality "$anchor_md"; then
    log_check 7 PASS "ANCHOR §4 quality (${GOOD_ENTRY_COUNT} well-formed entries)"
    return 0
  fi

  local reasons
  reasons=$(printf '%s; ' "${REJECT_REASONS[@]}" | sed 's/; $//')
  log_check 7 FAIL "ANCHOR §4 quality" "$reasons"
  return 1
}

# Check #8: unstaged residual — everything intended must be staged (pre-commit).
# Post-commit mode: check that working tree is clean after HEAD commit.
check_8_unstaged_residual() {
  local mode="$1"
  local residual
  case "$mode" in
    pre-commit) residual=$(git status --porcelain 2>/dev/null | grep -E '^ [MADRC]|^\?\?' || true) ;;
    post-commit) residual=$(git status --porcelain 2>/dev/null || true) ;;
  esac

  if [ -z "$residual" ]; then
    log_check 8 PASS "unstaged residual"
    return 0
  fi

  local count
  count=$(printf '%s\n' "$residual" | wc -l | tr -d ' ')
  log_check 8 FAIL "unstaged residual" "$count unstaged file(s) remaining: $(printf '%s' "$residual" | head -3 | tr '\n' '; ')"
  return 1
}

# -----------------------------------------------------------------------------
# Shared-scope check set (when --shared is invoked).
# -----------------------------------------------------------------------------

check_shared_modify() {
  local mode="$1"
  local modify_md="shared/docs/MODIFY.md"
  local diff_output=""
  case "$mode" in
    pre-commit) diff_output=$(git diff --cached -- "$modify_md" 2>/dev/null || true) ;;
    post-commit) diff_output=$(git log -1 -p -- "$modify_md" 2>/dev/null || true) ;;
  esac
  if printf '%s' "$diff_output" | grep -qE '^\+## CHG-'; then
    log_check S1 PASS "shared/docs/MODIFY.md entry"
    return 0
  fi
  log_check S1 FAIL "shared/docs/MODIFY.md entry" "shared/ changes require a new CHG- entry in shared/docs/MODIFY.md"
  return 1
}

# -----------------------------------------------------------------------------
# Main dispatch
# -----------------------------------------------------------------------------

main() {
  [ $# -ge 1 ] || usage

  local mode="" feature_id=""

  case "$1" in
    --help|-h) usage ;;
    --pre-commit)
      mode="pre-commit"
      [ $# -ge 2 ] || die "--pre-commit requires <feature-id>"
      feature_id="$2"
      ;;
    --post-commit)
      mode="post-commit"
      [ $# -ge 2 ] || die "--post-commit requires <feature-id>"
      feature_id="$2"
      ;;
    --shared)
      mode="shared-pre-commit"
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac

  require_git_repo

  # META short-circuit: pure-meta changesets skip verify entirely.
  # (Mixed commits — meta + operational — still get full operational gate.)
  local changed_files
  case "$mode" in
    pre-commit|shared-pre-commit) changed_files=$(all_changed_files) ;;
    post-commit) changed_files=$(head_commit_files) ;;
  esac

  if [ -n "$changed_files" ]; then
    # shellcheck disable=SC2086
    if is_pure_meta_changeset $changed_files; then
      printf 'META mode: pure-meta changeset detected. verify-completion skipped.\n' >&2
      exit 0
    fi
  fi

  # Shared mode uses its own minimal check set.
  if [ "$mode" = "shared-pre-commit" ]; then
    local failed=0
    check_shared_modify pre-commit || failed=$((failed + 1))
    check_8_unstaged_residual pre-commit || failed=$((failed + 1))
    exit "$([ "$failed" -eq 0 ] && echo 0 || echo 1)"
  fi

  validate_feature_id "$feature_id"
  local fdir
  fdir=$(feature_dir "$feature_id")

  local failed=0
  local effective_mode
  effective_mode="${mode}"

  check_2_task_md "$fdir" "$effective_mode" || failed=$((failed + 1))
  check_3_modify_md "$fdir" "$effective_mode" || failed=$((failed + 1))
  check_4_function_md "$fdir" "$effective_mode" || failed=$((failed + 1))
  check_6_anchor_1_3 "$fdir" || failed=$((failed + 1))
  check_7_anchor_4 "$fdir" || failed=$((failed + 1))
  check_8_unstaged_residual "$effective_mode" || failed=$((failed + 1))

  if [ "$failed" -eq 0 ]; then
    printf '\nverify-completion: PASS (all 6 pilot checks)\n' >&2
    exit 0
  else
    printf '\nverify-completion: FAIL (%d of 6 pilot checks failed)\n' "$failed" >&2
    exit 1
  fi
}

main "$@"
