#!/usr/bin/env bash
#
# verify-completion.sh — AI가 작업 완료를 선언하기 전에 의무적으로 호출하는 검증 도구.
#
# 설계 근거: AGENTS.md §16.3 (Git 동기화 절차 — 이 스크립트가 흡수)
#           AGENTS.md §18 (외부 앵커 정책)
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
    AGENTS.md|CLAUDE.md|GEMINI.md) return 0 ;;
    bin/*|shared/docs/*|docs/*) return 0 ;;
    unit/_template/*) return 0 ;;
    # v3.13.0 — wiki/ 사람 facing vault (AGENTS.md §21) 는 META path.
    wiki/*) return 0 ;;
    unit/META-*) return 0 ;;
    # v3.6.0 — template maintainer archive (NOT distributed to consumers,
    # but classified as META for verify-completion check #9 attribution).
    _template_maintainer/*) return 0 ;;
    TEMPLATE_CHANGELOG.md|CONTRIBUTING.md|README.md|FIRST_REQUEST.md|TODOS.md|VERSION) return 0 ;;
    # AGENTS.md §18.10 — meta/** and unit/<feature>/meta/** are META paths.
    meta/*) return 0 ;;
    unit/*/meta/*) return 0 ;;
    # .claude/ holds project-scope agents, commands, settings — meta-class.
    .claude/*) return 0 ;;
    # .codex, .agents/plugins, and the template-owned local Codex plugin hold
    # project-scope Codex commands, skills, and marketplace metadata — meta-class.
    .codex/*|.agents/plugins/*|plugins/ai-delegated-dev-template/*) return 0 ;;
    *) return 1 ;;
  esac
}

# Return 0 if ALL files in the provided list are META paths (pure-meta commit).
# The AGENTS.md §18.4 rule: pure-meta commits skip checks #1-#8 (check #9 still runs).
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
  # NOTE: `printf | grep -q` triggers SIGPIPE+pipefail false-negative on >64KB
  # diff. Use grep -c with count comparison to avoid early-exit SIGPIPE.
  local checkbox_count
  checkbox_count=$(printf '%s' "$diff_output" | grep -cE '^\+.*\[[ x]\]' || true)
  if [ "${checkbox_count:-0}" -gt 0 ]; then
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
  # NOTE: SIGPIPE+pipefail fix — grep -c with count comparison.
  local chg_count
  chg_count=$(printf '%s' "$diff_output" | grep -cE '^\+## CHG-' || true)
  if [ "${chg_count:-0}" -gt 0 ]; then
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

# Check #7: ANCHOR.md §4 optional quality gate.
# Normal TASK cycles do not require human §4 entries. If a human entry exists,
# it must be well-formed so the log does not drift into cargo-cult approval.
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

  if [ "${#REJECT_REASONS[@]}" -eq 1 ] && [ "${REJECT_REASONS[0]}" = "§4 has no entries at all" ]; then
    log_check 7 PASS "ANCHOR §4 optional (no human entries)"
    return 0
  fi

  local reasons
  reasons=$(printf '%s; ' "${REJECT_REASONS[@]}" | sed 's/; $//')
  log_check 7 FAIL "ANCHOR §4 quality" "$reasons"
  return 1
}

# Check #9: REVIEW.md cycle entry — at least one accepted [SUBAGENT|AGENT-TEAM]
# entry, or an explicit [SKIPPED] entry for non-policy doc-only cycles, must
# have been added to the relevant REVIEW.md in the current cycle. [REJECTED:*]
# entries are diagnostic traces only; they do not prove review completion.
# AGENTS.md §18.4 + §18.10.1: META mode skips checks #1-#8 but check #9 still runs.
# v0.1 cycle scope approximation: staged/unstaged diff (pre-commit) or HEAD diff
# (post-commit) of the candidate REVIEW.md must contain at least one added entry
# matching the 4 entry types. Precise cycle-window scope is a v0.2 candidate.
check_9_review_entry() {
  local mode="$1"
  local fid="${2:-}"
  local changed=""
  case "$mode" in
    pre-commit|shared-pre-commit) changed=$(all_changed_files) ;;
    post-commit) changed=$(head_commit_files) ;;
  esac

  local review_paths=()
  if [ -n "$fid" ] && [ -d "unit/${fid}" ]; then
    review_paths+=("unit/${fid}/docs/REVIEW.md")
    if printf '%s\n' "$changed" | grep -Eq "^unit/${fid}/meta/"; then
      review_paths+=("unit/${fid}/meta/REVIEW.md")
    fi
  fi

  if printf '%s\n' "$changed" | grep -Eq '^meta/'; then
    review_paths+=("meta/REVIEW.md")
  fi

  # v3.6.0 — Template maintainer cycle: changes touching _template_maintainer/**
  # are accepted via _template_maintainer/REVIEW_INDEX.md as the cycle entry source.
  # This keeps template-self review evidence out of the consumer-area meta/REVIEW.md.
  if printf '%s\n' "$changed" | grep -Eq '^_template_maintainer/'; then
    review_paths+=("_template_maintainer/REVIEW_INDEX.md")
  fi

  # feature-bound META paths from any feature in the changeset
  local feature_metas
  feature_metas=$(printf '%s\n' "$changed" \
    | grep -Eo '^unit/[^/]+/meta/' \
    | sed -E 's|^unit/([^/]+)/meta/$|\1|' \
    | sort -u || true)
  if [ -n "$feature_metas" ]; then
    local fm
    while IFS= read -r fm; do
      [ -n "$fm" ] && review_paths+=("unit/${fm}/meta/REVIEW.md")
    done <<<"$feature_metas"
  fi

  # Fallback: any META-class change at repo root (AGENTS.md, _template/, bin/, etc.)
  # → both meta/REVIEW.md (consumer area) and _template_maintainer/REVIEW_INDEX.md
  # (template-self area) are accepted. Either-or satisfies check #9 — author chooses
  # the right area based on whether the change is template-self or consumer-area.
  if [ "${#review_paths[@]}" -eq 0 ]; then
    review_paths+=("meta/REVIEW.md")
    review_paths+=("_template_maintainer/REVIEW_INDEX.md")
  fi

  # dedupe
  local unique_paths
  unique_paths=$(printf '%s\n' "${review_paths[@]}" | sort -u)

  local entry_pattern='^\+## REV-[0-9]{8}-[0-9]{4} \[(SUBAGENT|AGENT-TEAM|SKIPPED):'
  local found=0
  local rmd
  while IFS= read -r rmd; do
    [ -n "$rmd" ] || continue
    [ -f "$rmd" ] || continue
    local diff_output=""
    case "$mode" in
      pre-commit|shared-pre-commit)
        diff_output=$( { git diff --cached -- "$rmd" 2>/dev/null; git diff -- "$rmd" 2>/dev/null; } || true )
        ;;
      post-commit)
        diff_output=$(git log -1 -p -- "$rmd" 2>/dev/null || true)
        ;;
    esac
    # NOTE: SIGPIPE+pipefail fix — grep -c with count comparison.
    local entry_count
    entry_count=$(printf '%s' "$diff_output" | grep -cE "$entry_pattern" || true)
    if [ "${entry_count:-0}" -gt 0 ]; then
      found=1
      break
    fi
  done <<<"$unique_paths"

  if [ "$found" = "1" ]; then
    log_check 9 PASS "REVIEW.md cycle entry"
    return 0
  fi

  local hint="no accepted [SUBAGENT|AGENT-TEAM|SKIPPED]:* entry added to REVIEW.md in this cycle"
  hint="${hint}. Run the verification panel protocol (/review-panel entrypoint or AGENTS.md §18.8 flow) and stage the resulting REVIEW.md change"
  log_check 9 FAIL "REVIEW.md cycle entry" "$hint"
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
  # NOTE: SIGPIPE+pipefail fix — grep -c with count comparison.
  local shared_chg_count
  shared_chg_count=$(printf '%s' "$diff_output" | grep -cE '^\+## CHG-' || true)
  if [ "${shared_chg_count:-0}" -gt 0 ]; then
    log_check S1 PASS "shared/docs/MODIFY.md entry"
    return 0
  fi
  log_check S1 FAIL "shared/docs/MODIFY.md entry" "shared/ changes require a new CHG- entry in shared/docs/MODIFY.md"
  return 1
}

# -----------------------------------------------------------------------------
# Check #10: worktree binding (AGENTS.md §13.2.2 F1)
# -----------------------------------------------------------------------------
#
# 단일 worktree = 단일 branch 영구 binding 을 강제한다.
# FAIL 분기:
#   - detached HEAD 상태에서 mutation 시도 (F1 회피 경로 차단)
#   - HEAD branch != worktree binding branch (branch-switch silent 오염)
#
# SKIP+WARN 분기 (정책 외 환경 / 일시적 git 상태):
#   - env GSTACK_SKIP_WORKTREE_CHECK=1 또는 cli flag --skip-worktree-check
#   - git work tree 가 아닌 디렉토리
#   - rebase / cherry-pick / merge in progress (mid-state)
#   - 현재 cwd 가 worktree entry path 와 매칭되지 않음 (bare/linked edge — TODO T1)
#
# 호출 위치: main() 의 require_git_repo 직후, case "$mode" (META detection) 앞.
# META 모드 우회 필수 — branch-binding 은 changeset 종류와 무관한 git 상태 fact.
check_10_worktree_binding() {
  local args_str=" $* "

  if [ "${GSTACK_SKIP_WORKTREE_CHECK:-0}" = "1" ] || \
     [[ "$args_str" == *" --skip-worktree-check "* ]]; then
    log_check 10 WARN "worktree binding" "SKIP (escape hatch)"
    return 0
  fi

  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    log_check 10 WARN "worktree binding" "SKIP (not a git work tree)"
    return 0
  fi

  local git_dir
  git_dir=$(git rev-parse --git-dir 2>/dev/null || true)
  if [ -n "$git_dir" ]; then
    if [ -e "$git_dir/REBASE_HEAD" ] || \
       [ -d "$git_dir/rebase-merge" ] || \
       [ -d "$git_dir/rebase-apply" ] || \
       [ -e "$git_dir/CHERRY_PICK_HEAD" ] || \
       [ -e "$git_dir/MERGE_HEAD" ]; then
      log_check 10 WARN "worktree binding" "SKIP (mid-state: rebase/cherry-pick/merge in progress)"
      return 0
    fi
  fi

  local current_branch
  if ! current_branch=$(git symbolic-ref --quiet --short HEAD 2>/dev/null); then
    log_check 10 FAIL "worktree binding" \
      "detached HEAD 에서 mutation 금지 (§13.2.2 F1). branch 로 복귀하거나 새 worktree add."
    return 1
  fi

  local repo_root pwd_real
  repo_root=$(git rev-parse --show-toplevel 2>/dev/null || true)
  if [ -z "$repo_root" ]; then
    log_check 10 WARN "worktree binding" "SKIP (could not resolve repo root)"
    return 0
  fi
  pwd_real=$(cd "$repo_root" && pwd -P 2>/dev/null || printf '%s' "$repo_root")

  # v3.11.0: nested worktree 감지 — repo/.worktrees/ 내부는 §13.2.3 lifecycle 위반 (§13.2.3).
  case "$pwd_real" in
    */repo/.worktrees/*)
      log_check 10 FAIL "worktree binding" \
        "nested worktree 감지 — worktree 가 repo/ 내부에 있습니다: '$pwd_real'. <wrapper>/.worktrees/<feat> 위치를 사용하세요 (§13.2.3 lifecycle). escape hatch: GSTACK_SKIP_WORKTREE_CHECK=1"
      return 1 ;;
  esac

  local wt_branch="" wt_path="" wt_detached=0 found=0
  local porcelain
  porcelain=$(git worktree list --porcelain 2>/dev/null || true)
  if [ -z "$porcelain" ]; then
    log_check 10 WARN "worktree binding" "SKIP (git worktree list returned empty)"
    return 0
  fi

  while IFS= read -r line; do
    case "$line" in
      "worktree "*)
        wt_path="${line#worktree }"
        if [ -d "$wt_path" ]; then
          wt_path=$(cd "$wt_path" && pwd -P 2>/dev/null || printf '%s' "$wt_path")
        fi
        wt_branch=""
        wt_detached=0
        ;;
      "branch "*)
        wt_branch="${line#branch }"
        wt_branch="${wt_branch#refs/heads/}"
        ;;
      "detached")
        wt_detached=1
        ;;
      "")
        if [ "$wt_path" = "$pwd_real" ]; then
          found=1
          break
        fi
        wt_path=""
        ;;
    esac
  done <<< "$porcelain"

  if [ "$found" = "0" ] && [ "$wt_path" = "$pwd_real" ]; then
    found=1
  fi

  if [ "$found" = "0" ]; then
    log_check 10 WARN "worktree binding" "SKIP (cwd '$pwd_real' not in any worktree entry — bare/linked edge, TODO T1)"
    return 0
  fi

  if [ "$wt_detached" = "1" ]; then
    log_check 10 FAIL "worktree binding" \
      "worktree entry binding = detached, HEAD = $current_branch — F1 위반 (§13.2.2). 한 worktree = 한 branch."
    return 1
  fi

  if [ "$current_branch" != "$wt_branch" ]; then
    log_check 10 FAIL "worktree binding" \
      "HEAD = $current_branch != worktree binding = $wt_branch (§13.2.2 F1). 한 worktree = 한 branch. 다른 branch 작업은 새 worktree add."
    return 1
  fi

  log_check 10 PASS "worktree binding"
  return 0
}

# -----------------------------------------------------------------------------
# Check #11: Consumer repo Immutability (AGENTS.md §13.2.7 F0, v3.8.0+)
# -----------------------------------------------------------------------------
# 소비자 프로젝트의 main checkout 에서 `repo/` 직접 mutation 을 차단.
# Sentinel: `_template_maintainer/HISTORY.md` 부재 = consumer.
# Skip 조건 (우선순위):
#   - escape hatch (env GSTACK_SKIP_REPO_IMMUTABILITY=1 또는 --skip-repo-immutability)
#   - non-git working tree
#   - template base (sentinel `_template_maintainer/HISTORY.md` 존재)
#   - ai/* worktree (linked worktree, main 아님)
#   - `/_template:init` 부트스트랩 (init 졸업 신호 .template-init-marker /
#     initialized_at / bootstrap=false 모두 부재 — init 작업 중 일시 면제)
#   - working tree clean (mutation 없음)
# FAIL: 위 6 조건 모두 부정 → main checkout 의 mutation = F0 위반.

check_11_repo_immutability() {
  local args_str=" $* "
  if [[ "${GSTACK_SKIP_REPO_IMMUTABILITY:-}" == "1" ]] ||
     [[ "$args_str" == *" --skip-repo-immutability "* ]]; then
    log_check 11 WARN "repo immutability" "SKIP (escape hatch)"
    return 0
  fi

  if ! git rev-parse --git-dir >/dev/null 2>&1; then
    log_check 11 WARN "repo immutability" "SKIP (not a git work tree)"
    return 0
  fi

  local repo_root
  repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || {
    log_check 11 WARN "repo immutability" "SKIP (could not resolve repo root)"
    return 0
  }

  # Template base sentinel — maintainer 영역은 정책 비적용.
  if [ -f "$repo_root/_template_maintainer/HISTORY.md" ]; then
    log_check 11 PASS "repo immutability" "(template base — carve-out)"
    return 0
  fi

  # ai/* worktree carve-out: main worktree 가 아닌 linked worktree 면 PASS.
  # check #10 가 F1 (branch binding) 을 별도 검증하므로 본 check 는 mutation
  # 위치만 확인.
  local porcelain main_wt_path=""
  porcelain=$(git worktree list --porcelain 2>/dev/null || true)
  if [ -n "$porcelain" ]; then
    # 첫 번째 worktree entry = main worktree.
    local in_first=1 line
    while IFS= read -r line; do
      case "$line" in
        "worktree "*)
          if [ "$in_first" = "1" ]; then
            main_wt_path="${line#worktree }"
            break
          fi
          ;;
      esac
    done <<<"$porcelain"
  fi

  local pwd_real repo_root_real main_wt_real
  pwd_real=$(realpath -m "$repo_root" 2>/dev/null || echo "$repo_root")
  if [ -n "$main_wt_path" ]; then
    main_wt_real=$(realpath -m "$main_wt_path" 2>/dev/null || echo "$main_wt_path")
    if [ "$pwd_real" != "$main_wt_real" ]; then
      log_check 11 PASS "repo immutability" "(ai/* worktree — F0 외)"
      return 0
    fi
  fi

  # `/_template:init` 부트스트랩 carve-out: init 졸업 신호가 "모두 부재" 일 때만
  # 일시 면제 (init 작업 중 example 정리로 main 이 dirty 해지는 구간 보호).
  # 졸업 신호 (이중 — init 경로 / upgrade 경로 모두 커버):
  #   (a) .template-init-marker 파일 — /_template:init 이 생성하는 sentinel
  #   (b) AGENTS.md frontmatter 의 initialized_at: — init 의 이중 마커
  #   (c) .template-state 의 bootstrap=false — template-upgrade.sh --apply 졸업 latch
  # 하나라도 있으면 init 졸업 = carve-out 안 함 (F0 정상 발동).
  # (구버전은 .template/init-completed 를 봤으나 어느 경로도 그 파일을 생성하지
  #  않아 carve-out 영구 발동 버그 — v3.16.0 에서 실제 신호로 교체.)
  local init_graduated=false
  [ -f "$repo_root/.template-init-marker" ] && init_graduated=true
  # initialized_at: frontmatter — 선행 공백 허용 (들여쓰기 변형 내성). prose 오매칭은
  # 'initialized_at:' 가 라인 시작(±공백)이어야 하므로 backtick 내 인용·문중 언급과 구분됨.
  grep -qE "^[[:space:]]*initialized_at:" "$repo_root/AGENTS.md" 2>/dev/null && init_graduated=true
  if [ -f "$repo_root/.template-state" ]; then
    grep -q "^bootstrap=false" "$repo_root/.template-state" 2>/dev/null && init_graduated=true
  fi
  if [ "$init_graduated" = false ]; then
    log_check 11 PASS "repo immutability" "(init bootstrap — carve-out)"
    return 0
  fi

  # Mutation 여부: working tree clean 이면 PASS.
  if [ -z "$(git status --porcelain 2>/dev/null)" ]; then
    log_check 11 PASS "repo immutability" "(working tree clean)"
    return 0
  fi

  # 위 모든 carve-out 부정 → FAIL.
  log_check 11 FAIL "repo immutability" \
    "main checkout 의 repo/ 직접 mutation 금지 (§13.2.7 F0). Update 는 'cd repo && git pull --ff-only', customization 은 'git -C repo worktree add ../.worktrees/<feat> -b ai/<agent>/<feat>'. Escape: GSTACK_SKIP_REPO_IMMUTABILITY=1 또는 --skip-repo-immutability."
  return 1
}

# -----------------------------------------------------------------------------
# Check #12: Wiki feature card companion (AGENTS.md §21.2 #1, v3.12.0+ WARN-only)
# -----------------------------------------------------------------------------
# Diff 에서 unit/feature-* 신규 추가 감지 시 wiki/Features/<slug>.md 동반 검사.
# v3.12.0: WARN-only (PR block 아님 — §21.4 staged rollout).
# v3.13.0+: strict 모드 격상 예정 (--strict flag 또는 default 변경).
# Skip 조건:
#   - wiki/ 디렉토리 부재 (v3.11.0 이전 buildup)
#   - non-git working tree
#   - META mode (별도 호출 안 함, 본 check 는 feature mode 전용)

check_12_wiki_feature_card() {
  local mode="${1:-pre-commit}"
  if ! git rev-parse --git-dir >/dev/null 2>&1; then
    log_check 12 WARN "wiki feature card" "SKIP (not a git work tree)"
    return 0
  fi

  local repo_root
  repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || {
    log_check 12 WARN "wiki feature card" "SKIP (could not resolve repo root)"
    return 0
  }

  # v3.11.0 이전 buildup 은 본 check skip.
  if [ ! -d "$repo_root/wiki" ]; then
    log_check 12 PASS "wiki feature card" "(wiki/ 미도입 — v3.11.0 이전 buildup skip)"
    return 0
  fi

  # 신규 feature 디렉토리 찾기 (Added 한정).
  local new_feature_files=""
  case "$mode" in
    pre-commit|shared-pre-commit)
      new_feature_files=$(git diff --cached --diff-filter=A --name-only 2>/dev/null | grep -E '^unit/feature-[^/]+/' || true)
      ;;
    post-commit)
      new_feature_files=$(git diff HEAD~1 HEAD --diff-filter=A --name-only 2>/dev/null | grep -E '^unit/feature-[^/]+/' || true)
      ;;
    *)
      log_check 12 WARN "wiki feature card" "SKIP (unknown mode: $mode)"
      return 0
      ;;
  esac

  if [ -z "$new_feature_files" ]; then
    log_check 12 PASS "wiki feature card" "(no new feature dir in diff)"
    return 0
  fi

  local feature_slugs
  feature_slugs=$(echo "$new_feature_files" | awk -F/ '{print $2}' | sort -u)

  local missing_cards=()
  local fslug card
  while IFS= read -r fslug; do
    [ -z "$fslug" ] && continue
    card="$repo_root/wiki/Features/$fslug.md"
    if [ ! -f "$card" ]; then
      missing_cards+=("$fslug")
    fi
  done <<< "$feature_slugs"

  if [ ${#missing_cards[@]} -eq 0 ]; then
    log_check 12 PASS "wiki feature card" "(all new features have wiki/Features cards)"
    return 0
  fi

  log_check 12 WARN "wiki feature card" \
    "AGENTS.md §21.2 #1 (SHOULD): wiki/Features/<slug>.md 동반 누락 — ${missing_cards[*]}. v3.12.0 WARN-only (PR block 아님). baseline: wiki/Features/_template-card.md. v3.13.0+ strict 격상 예정."
  # WARN: exit 0 유지, failed counter 영향 X. 본 check 는 항상 0 return.
  return 0
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

  # Check #10 (§13.2.2 F1) — unconditional, META/shared 모드보다 먼저 실행.
  # branch-binding 은 changeset 종류와 무관한 git 상태 fact 이므로 META 우회.
  local check10_status=0
  if ! check_10_worktree_binding "$@"; then
    check10_status=1
  fi

  # Check #11 (§13.2.7 F0) — unconditional, META/shared 모드보다 먼저 실행.
  # consumer repo immutability 는 mutation location 사실이므로 META 우회.
  local check11_status=0
  if ! check_11_repo_immutability "$@"; then
    check11_status=1
  fi

  # META short-circuit: pure-meta changesets skip verify entirely.
  # (Mixed commits — meta + operational — still get full operational gate.)
  local changed_files
  case "$mode" in
    pre-commit|shared-pre-commit) changed_files=$(all_changed_files) ;;
    post-commit) changed_files=$(head_commit_files) ;;
  esac

  # META mode (pure-meta changeset): per AGENTS.md §18.4, checks #1-#8 are
  # skipped but check #9 (REVIEW.md cycle entry) still runs as the single
  # exception. SPOF recovery still works because [SKIPPED:non-policy-doc]
  # entries can explicitly mark non-policy doc-only cycles, while rejected
  # panel attempts remain diagnostic-only and must be repaired/rerun.
  local meta_mode=0
  if [ -n "$changed_files" ]; then
    # shellcheck disable=SC2086
    if is_pure_meta_changeset $changed_files; then
      meta_mode=1
    fi
  fi

  if [ "$meta_mode" = "1" ]; then
    printf 'META mode: pure-meta changeset detected. checks #1-#8 skipped (§18.4). checks #10, #11 always run.\n' >&2
    local failed=$((check10_status + check11_status))
    case "$mode" in
      post-commit) check_9_review_entry post-commit "" || failed=$((failed + 1)) ;;
      *) check_9_review_entry pre-commit "" || failed=$((failed + 1)) ;;
    esac
    if [ "$failed" -eq 0 ]; then
      printf '\nverify-completion: PASS (META mode: checks #9, #10, #11 ran)\n' >&2
      exit 0
    else
      printf '\nverify-completion: FAIL (META mode: %d of #9, #10, #11 failed)\n' "$failed" >&2
      exit 1
    fi
  fi

  # Shared mode uses its own minimal check set + check #9 + check #10 + check #11.
  if [ "$mode" = "shared-pre-commit" ]; then
    local failed=$((check10_status + check11_status))
    check_shared_modify pre-commit || failed=$((failed + 1))
    check_8_unstaged_residual pre-commit || failed=$((failed + 1))
    check_9_review_entry shared-pre-commit "" || failed=$((failed + 1))
    exit "$([ "$failed" -eq 0 ] && echo 0 || echo 1)"
  fi

  validate_feature_id "$feature_id"
  local fdir
  fdir=$(feature_dir "$feature_id")

  local failed=$((check10_status + check11_status))
  local effective_mode
  effective_mode="${mode}"

  check_2_task_md "$fdir" "$effective_mode" || failed=$((failed + 1))
  check_3_modify_md "$fdir" "$effective_mode" || failed=$((failed + 1))
  check_4_function_md "$fdir" "$effective_mode" || failed=$((failed + 1))
  check_6_anchor_1_3 "$fdir" || failed=$((failed + 1))
  check_7_anchor_4 "$fdir" || failed=$((failed + 1))
  check_8_unstaged_residual "$effective_mode" || failed=$((failed + 1))
  check_9_review_entry "$effective_mode" "$feature_id" || failed=$((failed + 1))
  # Check #12 (v3.12.0+): wiki feature card companion — WARN-only, failed 영향 X.
  check_12_wiki_feature_card "$effective_mode" || true

  if [ "$failed" -eq 0 ]; then
    printf '\nverify-completion: PASS (9 checks: 7 pilot + worktree binding + repo immutability) + check #12 informational (wiki feature card, WARN-only)\n' >&2
    exit 0
  else
    printf '\nverify-completion: FAIL (%d of 9 checks failed)\n' "$failed" >&2
    exit 1
  fi
}

main "$@"
