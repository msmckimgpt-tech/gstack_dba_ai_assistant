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

# git 출력 색상 차단 (v3.44.0, AGENTS.md §16.7 G8 — 적용면 전수).
# color.ui=always 면 diff 라인 앞 ANSI 로 `^+` 매칭이 전부 빗나가 diff 를
# 파싱하는 check 들이 조용히 PASS 한다(fail-open). 프로세스 전역으로 끈다.
_gc_n="${GIT_CONFIG_COUNT:-0}"
eval "export GIT_CONFIG_KEY_${_gc_n}=color.ui"
eval "export GIT_CONFIG_VALUE_${_gc_n}=false"
export GIT_CONFIG_COUNT=$((_gc_n + 1))
unset _gc_n

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
    AGENTS.md|AGENTS.override.md|CLAUDE.md|GEMINI.md) return 0 ;;
    bin/*|shared/docs/*|docs/*) return 0 ;;
    unit/_template/*) return 0 ;;
    # v3.13.0 — wiki/ 사람 facing vault (AGENTS.md §21) 는 META path.
    wiki/*) return 0 ;;
    unit/META-*) return 0 ;;
    # v3.6.0 — template maintainer archive (NOT distributed to consumers,
    # but classified as META for verify-completion check #9 attribution).
    _template_maintainer/*) return 0 ;;
    TEMPLATE_CHANGELOG.md|CONTRIBUTING.md|README.md|FIRST_REQUEST.md|TODOS.md|VERSION) return 0 ;;
    # META-0024 — repo 루트 git 설정 파일(merge driver path-scope 등)은 META 계층.
    .gitattributes) return 0 ;;
    # AGENTS.md §18.10 — meta/** and unit/<feature>/meta/** are META paths.
    meta/*) return 0 ;;
    unit/*/meta/*) return 0 ;;
    # .claude/ holds project-scope agents, commands, settings — meta-class.
    .claude/*) return 0 ;;
    # .codex, .agents/plugins, and the template-owned local Codex plugin hold
    # project-scope Codex commands, skills, and marketplace metadata — meta-class.
    .codex/*|.agents/skills/*|.agents/ENVIRONMENT.md|.agents/plugins/*|plugins/ai-delegated-dev-template/*) return 0 ;;
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
# Code file = anything under feature_dir except docs/** , content/** assets, or
# tests/README.md scaffolds. content/ holds non-functional curation (release notes,
# static copy, data manifests) — companion-exempt by placement (AGENTS.md §16.2).
# -----------------------------------------------------------------------------

is_code_file() {
  local path="$1" fdir="$2"
  case "$path" in
    "${fdir}/docs/"*) return 1 ;;    # docs don't count as code
    "${fdir}/"*)
      # content/data assets (release notes, static copy, manifests) under a
      # `content/` segment are non-functional — companion-exempt (placement-based).
      # Match RELATIVE to fdir so a `/content/` segment elsewhere in the repo path
      # (e.g. a feature nested under .../content/) can never exempt real code.
      local rel="${path#"${fdir}/"}"
      case "$rel" in
        content/*|*/content/*) return 1 ;;
      esac
      return 0                        # everything else under feature = code
      ;;
    *) return 1 ;;
  esac
}

# -----------------------------------------------------------------------------
# Web/UI asset detection + FIRST_REQUEST scope reader (for check #13: PB-0008 gate)
# 웹/UI 자산 = 사용자에게 렌더되는 static/template/html (AGENTS.md §15.4.1 · PB-0008).
# -----------------------------------------------------------------------------
is_web_asset() {
  local path="$1"
  # 문서·메타 영역은 제품 UI 아님 — 제외(프레젠테이션 리포트 docs/*.html, wiki, .claude 등).
  # (M2 오탐 방지: docs/presentation/*.html 이 시각검증 게이트를 트리거하지 않도록.)
  case "$path" in
    docs/*|*/docs/*|wiki/*|.claude/*|.codex/*|.agents/*) return 1 ;;
  esac
  # 정적 프론트 자산 경로 — 이 프로젝트의 admin.js/app.js/share.js/styles.css/*.html 이 여기 거주.
  case "$path" in
    */src/static/*|*/static/*) return 0 ;;
  esac
  # static 밖의 UI 확장자 — 렌더 트리(src/web/components/templates/assets) 한정.
  # (M2 미탐 방지: static 밖 styles.css·*.jsx 등도 포착. .mjs 테스트/.py 백엔드는 비대상.)
  case "$path" in
    */src/*|*/web/*|*/components/*|*/templates/*|*/assets/*)
      case "$path" in
        *.html|*.htm|*.css|*.js|*.jsx|*.ts|*.tsx|*.vue|*.svg) return 0 ;;
      esac
      ;;
  esac
  return 1
}

# wrapper `<project_root>/FIRST_REQUEST.md` 의 'key: value' 스코프 선언을 echo (없으면 빈값).
# main worktree 의 부모(=wrapper) 에서 읽는다 — deploy_scope/reachability_scope 와 동일 위치.
read_first_request_scope() {
  local key="$1"
  local repo_root main_wt_path wrapper fr
  repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || return 0
  main_wt_path=$(git worktree list --porcelain 2>/dev/null | awk '/^worktree /{print substr($0,10); exit}')
  [ -n "$main_wt_path" ] || main_wt_path="$repo_root"
  wrapper=$(dirname "$main_wt_path")
  fr="$wrapper/FIRST_REQUEST.md"
  [ -f "$fr" ] || return 0
  # pipefail-safe: grep no-match(rc1) 는 `|| true` 로 흡수, head 로 인한 SIGPIPE 회피
  # (파이프라인 대신 변수 파싱 — verify-completion.sh 내 grep|head|pipefail 취약 패턴 주석 참조).
  local matches first
  matches=$(grep -iE "^[[:space:]]*${key}:" "$fr" 2>/dev/null) || true
  first="${matches%%$'\n'*}"        # 첫 매칭 라인
  first="${first#*:}"                # 'key:' 접두 제거
  first="${first%%#*}"               # 인라인 주석(# ...) 제거 (M4)
  first="${first//\"/}"; first="${first//\'/}"   # 따옴표 제거 (M4)
  # 공백 제거 + 소문자화 — 값 비교를 포맷/대소문자에 견고하게 (M4: silent hard→WARN 격하 방지).
  printf '%s' "$first" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]'
  return 0
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
    pre-commit) diff_output=$(git diff --no-color --no-ext-diff --cached -- "$task_md" 2>/dev/null || true) ;;
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
    pre-commit) diff_output=$(git diff --no-color --no-ext-diff --cached -- "$modify_md" 2>/dev/null || true) ;;
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
# entry, an explicit [SKIPPED] entry for non-policy doc-only cycles, or a
# [CODEX] entry for docs-only policy changes reviewed via codex (§18.8.1), must
# have been added to the relevant REVIEW.md in the current cycle. [REJECTED:*]
# entries are diagnostic traces only; they do not prove review completion.
# NOTE: this is a tag-presence gate — it matches the accepted verdict TAG
# ([SUBAGENT|AGENT-TEAM|SKIPPED|CODEX]), not the entry's embedded Verdict field.
# The PASS invariant (e.g. [CODEX] PASS iff codex P1=0; [SUBAGENT] verdict not
# BLOCK) is enforced by the review author / skill, not by this regex (§18.4).
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

  # REV id: legacy date+serial (REV-YYYYMMDD-NNNN) OR timestamp+branch
  # (REV-YYYYMMDDTHHMMSS-<branch>, ADR-0025/v3.32.0) — both accepted (additive).
  local entry_pattern='^\+## REV-([0-9]{8}-[0-9]{4}|[0-9]{8}T[0-9]{6}-[A-Za-z0-9._-]+) \[(SUBAGENT|AGENT-TEAM|SKIPPED|CODEX):'
  local found=0
  local rmd
  while IFS= read -r rmd; do
    [ -n "$rmd" ] || continue
    [ -f "$rmd" ] || continue
    local diff_output=""
    case "$mode" in
      pre-commit|shared-pre-commit)
        diff_output=$( { git diff --no-color --no-ext-diff --cached -- "$rmd" 2>/dev/null; git diff --no-color --no-ext-diff -- "$rmd" 2>/dev/null; } || true )
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

  local hint="no accepted [SUBAGENT|AGENT-TEAM|SKIPPED|CODEX]:* entry added to REVIEW.md in this cycle"
  hint="${hint}. Run the verification panel protocol (/review-panel entrypoint or AGENTS.md §18.8 flow) and stage the resulting REVIEW.md change"
  log_check 9 FAIL "REVIEW.md cycle entry" "$hint"
  return 1
}

# Check #8: unstaged residual — everything intended must be staged (pre-commit).
# Post-commit mode: check that working tree is clean after HEAD commit.
# -----------------------------------------------------------------------------
# Check #14 (META-0024, parallel-work-structure ITEM-03): conflict-marker 잔존 검사.
# 병렬 머지 해소 중 marker(`<<<<<<<`/`>>>>>>>`) 가 커밋에 섞여 들어간 사고(a77180ca)
# 재발 방지 — 추가된(+) 라인만 검사(기존 문서에 이미 있는 marker 인용은 무관).
# `=======` 단독은 마크다운 구분선 등 정상 용례가 많아 대상에서 제외(오탐 방지).
# 무조건 실행(META/shared 모드 포함) — marker 잔존은 changeset 종류와 무관한 결함.
# -----------------------------------------------------------------------------
check_14_conflict_markers() {
  local mode="$1" diff_added
  case "$mode" in
    # merge commit(부모 2)에서 git show 는 combined diff(++ prefix)라 marker 를 못 본다(패널 M-1)
    # — 1st-parent diff 로 검사(root commit 은 git show 폴백).
    post-commit) diff_added=$( (git diff --unified=0 HEAD^ HEAD 2>/dev/null || git show --format= --unified=0 HEAD 2>/dev/null) | grep -E '^\+' | grep -vE '^\+\+\+' || true) ;;
    *)           diff_added=$(git diff --cached --unified=0 2>/dev/null | grep -E '^\+' | grep -vE '^\+\+\+' || true) ;;
  esac
  local hits
  hits=$(printf '%s\n' "$diff_added" | grep -cE '^\+(<<<<<<<|>>>>>>>)( |$)' || true)
  if [ "${hits:-0}" -eq 0 ]; then
    log_check 14 PASS "conflict markers"
    return 0
  fi
  log_check 14 FAIL "conflict markers" "staged/HEAD diff 에 conflict marker 잔존 ${hits}건 (<<<<<<< / >>>>>>>) — 머지 해소 미완 커밋(a77180ca 클래스). 정당한 인용이면 들여쓰기/코드펜스 내 들여쓰기로 column-0 을 피할 것"
  return 1
}

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
    pre-commit) diff_output=$(git diff --no-color --no-ext-diff --cached -- "$modify_md" 2>/dev/null || true) ;;
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
    # silent re-disable 방어 (v3.18.0): 졸업 신호가 모두 없는데 이 repo 가 "신규
    # 부트스트랩 중" 이 아니라 "이미 운영 중" 으로 보이면, 졸업 신호가 삭제/유실된
    # tamper/drift 의심 상황이다 (F0 가 silent 하게 무력화될 수 있음 — v3.8.0 버그와
    # 같은 실패 양상). carve-out 으로 PASS 시키되 WARN 으로 표면화한다.
    #   운영 중 판정 지표 (모두 만족 시 = 신규 init 아님):
    #     - git commit 이 2개 이상 (신규 init 직후는 1 commit)
    #     - example feature(unit/feature-0001-example-*) 가 이미 정리됨 (init cleanup 흔적)
    #   휴리스틱 완전성 한계: commit<2 이면서 example 정리된 운영 repo 는 놓칠 수 있음
    #   (false negative). 단 WARN-only 라 F0 차단엔 영향 없고, 표면화만 누락 — 보수적.
    local looks_operational=false
    local commit_count
    commit_count=$(git rev-list --count HEAD 2>/dev/null || echo 0)
    if [ "${commit_count:-0}" -ge 2 ] && \
       ! ls -d "$repo_root"/unit/feature-0001-example-* >/dev/null 2>&1; then
      looks_operational=true
    fi
    if [ "$looks_operational" = true ]; then
      log_check 11 WARN "repo immutability" \
        "init 졸업 신호(.template-init-marker / initialized_at / bootstrap=false)가 모두 없으나 운영 중인 repo 로 보입니다 (commit ${commit_count}개, example 정리됨). 졸업 신호 유실/삭제로 F0 가 silent 하게 비활성됐을 수 있습니다 — \`bash bin/template-upgrade.sh --apply\` 로 bootstrap latch 재기록 또는 \`.template-init-marker\` 복원 권장. (carve-out 으로 통과하되 점검 필요.)"
      return 0
    fi
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

# Check #13 (v3.42.0): TASK.md §9 Requested Scope — §16.7 G1 요청 범위 자기-열거.
# WARN-only. "요청된 범위가 전부 완결됐는가" 는 기계적으로 판정할 수 없으므로 본 check 는
# 열거 자체의 누락만 nudge 한다 (실효 게이트는 AGENTS.md §16.7 G1~G6 + §16.2 체크리스트).
# FAIL 로 만들면 §9 섹션이 없는 기존 TASK.md 를 가진 소비자가 즉시 breaking 이 된다.
check_13_requested_scope() {
  # 표시 번호는 #18 — 본 프로젝트는 #13 을 시각검증(PB-0008)으로 이미 점유했다.
  # 함수명은 template hop 의 marker 앵커라 바꾸지 않는다(바꾸면 다음 hop 이 중복 삽입).
  local fdir="$1"
  local task_md="${fdir}/docs/TASK.md"

  if [ ! -f "$task_md" ]; then
    # check #2 가 이미 FAIL 로 보고한 상태 — 중복 노이즈 방지.
    log_check 18 WARN "requested scope" "SKIP (TASK.md not found)"
    return 0
  fi

  # 헤딩 번호는 소비자가 재배치할 수 있으므로 제목 토큰으로 찾는다 (영/한 병기 허용).
  # 단일 awk 로 (a) 코드펜스 추적 (b) 섹션 탐색 (c) 항목 계수를 한 번에 한다:
  #   - **코드펜스(```) 내부는 무시** — 문서의 예시 블록에 `## Requested Scope` + `- [ ] …`
  #     가 있으면 실제 섹션이 없어도 거짓 PASS 가 된다.
  #   - **미치환 placeholder 행은 세지 않는다** — skeleton 을 그대로 복사한 상태
  #     (`<요청 항목 1>`, `<TBD: …>`)의 PASS 는 G1 충족을 거짓 신호한다. 판정 규칙: `<…>`
  #     span 을 포함한 행 = 미치환 템플릿 행. (실 항목이 `<div>` 같은 꺾쇠를 담으면 함께
  #     제외되지만, WARN-only nudge 에서는 거짓 PASS 보다 거짓 WARN 이 안전하다.)
  # `|| true` 필수 — awk/grep 의 비-0 rc 가 `set -o pipefail` + `set -e` 와 만나면 **WARN
  # 분기 전에** 스크립트가 죽어 WARN-only 계약이 깨진다 (legacy TASK.md 소비자 hard fail).
  # 호출부의 `|| true` 가 errexit 를 가려주는 것에 의존하지 않는다 — 호출 방식이 바뀌면 사라진다.
  local counts found_section filled_count placeholder_count
  counts=$(awk '
    /^[[:space:]]*(```|~~~)/ { fence = !fence; next }
    fence { next }
    /^#{2,3} / {
      if (insec) { insec = 0 }
      if ($0 ~ /(Requested Scope|요청 범위)/) { insec = 1; found = 1 }
      next
    }
    # **체크박스 행만** G1 항목으로 센다 — 섹션의 G3(주장 affordance)·G4(경계 검증) 블록은
    # 평문 `- ` bullet(`- 해당 없음` 등)이므로, 모든 bullet 을 세면 G1 요청항목이 비었는데도
    # G3·G4 만 채워 PASS 가 난다(게이트의 핵심 신호가 무력화).
    insec && /^[[:space:]]*-[[:space:]]+\[[ xX]\][[:space:]]*[^[:space:]]/ {
      if ($0 ~ /<[^>]*>/) ph++; else filled++
    }
    END { printf "%d %d %d", found + 0, filled + 0, ph + 0 }
  ' "$task_md" || true)
  found_section=$(printf '%s' "$counts" | awk '{print $1}')
  filled_count=$(printf '%s' "$counts" | awk '{print $2}')
  placeholder_count=$(printf '%s' "$counts" | awk '{print $3}')

  if [ "${found_section:-0}" -eq 0 ]; then
    log_check 18 WARN "requested scope" \
      "AGENTS.md §16.7 G1: TASK.md 에 'Requested Scope (요청 범위)' 섹션이 없습니다 (코드펜스 안의 예시는 인정하지 않습니다). 완료 선언 전 요청 항목/범위를 항목당 1행으로 열거하세요. baseline: unit/_template/docs/TASK.md §9."
    return 0
  fi

  if [ "${filled_count:-0}" -eq 0 ]; then
    if [ "${placeholder_count:-0}" -gt 0 ]; then
      log_check 18 WARN "requested scope" \
        "AGENTS.md §16.7 G1: Requested Scope 섹션에 미치환 placeholder 만 ${placeholder_count}행 있습니다 (<…> 유지). skeleton 문구를 실제 요청 항목으로 교체해야 G2·G3 의 대조 기준이 생깁니다."
    else
      log_check 18 WARN "requested scope" \
        "AGENTS.md §16.7 G1: Requested Scope 섹션에 요청 항목이 없습니다. 항목은 체크박스 행(\`- [ ] <요청 항목> — 산출물: …\`)으로 적습니다 — G3·G4 블록의 평문 bullet 은 요청 항목으로 세지 않습니다."
    fi
    return 0
  fi

  local hint="(${filled_count} item(s) enumerated — §16.7 G1)"
  [ "${placeholder_count:-0}" -gt 0 ] && hint="${hint} · placeholder ${placeholder_count}행 잔존"
  log_check 18 PASS "requested scope" "$hint"
  return 0
}
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

# Check #13: 웹/UI 변경 시 실제 Windows 브라우저 시각검증(PB-0008) 완료 게이트.
# 정책 근거: AGENTS.md §15.4.1 / §16.2 — 웹/UI(화면·상호작용) 변경의 완료 검증은 실제
# Windows 브라우저(`bin/win-browser.py`)에서 수행하고 feature `docs/TEST.md §3` 에
# 'Environment: Windows-browser' Run 을 기록한다.
# 강제 수준(wrapper FIRST_REQUEST.md `visual_verification_scope`):
#   always → 미기록 시 FAIL(hard gate — 본 프로젝트 정책, 2026-07-01 사용자 지시).
#   그 외/미선언 → WARN(backward-compat — 기존 소비자 비파괴).
# escape: 브리지 setup 불가(공용 CI 등)로 미수행 시 TEST.md 에 'Windows-browser' 맥락으로
#   사유(미수행/skip/BLOCKED/불가)를 기록하면 통과(카고컬트 방지 — 사유 명시 요구).
#   긴급 우회: env GSTACK_SKIP_VISUAL_VERIFICATION=1 또는 --skip-visual-verification.
# Check #15: ROUTEMAP freshness (AGENTS.md §21.11.4, WARN-only) — 구조 리팩터 시 code-map 갱신 의무.
check_15_routemap_freshness() {
  local mode="${1:-pre-commit}"
  git rev-parse --git-dir >/dev/null 2>&1 || { log_check 15 WARN "routemap freshness" "SKIP (not a git work tree)"; return 0; }
  local repo_root; repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || { log_check 15 WARN "routemap freshness" "SKIP (no repo root)"; return 0; }
  [ -f "$repo_root/bin/gen-routemap.py" ] || { log_check 15 PASS "routemap freshness" "(gen-routemap.py 미도입 — skip)"; return 0; }
  local routers_re='unit/feature-0003-agent-web-ui/src/routers/.*\.py$'
  local src_re='unit/feature-0003-agent-web-ui/src/[^/]+\.py$'
  local struct new_src touched
  case "$mode" in
    pre-commit|shared-pre-commit)
      struct=$(git diff --cached --diff-filter=ADR --name-only 2>/dev/null | grep -E "$routers_re" || true)
      new_src=$(git diff --cached --diff-filter=A  --name-only 2>/dev/null | grep -E "$src_re" || true)
      touched=$(git diff --cached --name-only        2>/dev/null | grep -E "$routers_re" || true) ;;
    post-commit)
      struct=$(git diff HEAD~1 HEAD --diff-filter=ADR --name-only 2>/dev/null | grep -E "$routers_re" || true)
      new_src=$(git diff HEAD~1 HEAD --diff-filter=A  --name-only 2>/dev/null | grep -E "$src_re" || true)
      touched=$(git diff HEAD~1 HEAD --name-only        2>/dev/null | grep -E "$routers_re" || true) ;;
    *) log_check 15 WARN "routemap freshness" "SKIP (unknown mode: $mode)"; return 0 ;;
  esac
  if [ -z "$struct" ] && [ -z "$new_src" ] && [ -z "$touched" ]; then
    log_check 15 PASS "routemap freshness" "(no router/src structural change in diff)"; return 0
  fi
  # companion 게이트(§21.11.4): struct(routers 추가/삭제/rename) 또는 new_src 인데 code-map 3종
  # (CODEBASE_MAP·CODE_NAVIGATION·CODE_TASKS)이 같은 diff 에 동반 stage 되지 않으면 WARN.
  # (check #12 feature-card companion 패턴 이식 — 신규 라우터가 ROUTEMAP 만 갱신하고 3문서를
  #  손대지 않아도 통과하던 gap 을 표면화.)
  if [ -n "$struct" ] || [ -n "$new_src" ]; then
    local staged_all companion_missing=""
    case "$mode" in
      pre-commit|shared-pre-commit) staged_all=$(git diff --cached --name-only 2>/dev/null) ;;
      post-commit) staged_all=$(git diff HEAD~1 HEAD --name-only 2>/dev/null) ;;
    esac
    local cm
    for cm in docs/CODEBASE_MAP.md docs/CODE_NAVIGATION.md docs/CODE_TASKS.md; do
      printf '%s\n' "$staged_all" | grep -qxF "$cm" || companion_missing="$companion_missing $cm"
    done
    [ -n "$companion_missing" ] && log_check 15 WARN "routemap companion" "AGENTS.md §21.11.4: routers 구조 변경(struct/new_src)인데 code-map 미동반 stage:$companion_missing — 재정합 후 stage 권장(WARN-only)."
  fi
  if python3 "$repo_root/bin/gen-routemap.py" --check >/dev/null 2>&1; then
    log_check 15 PASS "routemap freshness" "(ROUTEMAP.md up-to-date)"; return 0
  fi
  log_check 15 WARN "routemap freshness" "AGENTS.md §21.11.4: routers/ 또는 src/*.py 구조 변경인데 docs/ROUTEMAP.md 미갱신(gen-routemap --check STALE). 재생성: python3 bin/gen-routemap.py 후 stage. WARN-only(PR block 아님)."
  return 0
}

# Check #16: codenav-lint anchor resolvability (AGENTS.md §21.11.4·§21.11.7, WARN-only)
# — CODE_NAVIGATION/CODE_TASKS 의 file:symbol·모듈·DI seam 앵커가 소스에서 resolve 되는지.
#   핸들러 rename/이동처럼 ROUTEMAP 정합을 유지하며 앵커만 무효화하는 변경을 잡는 유일한 자동 수단.
check_16_codenav_lint() {
  local mode="${1:-pre-commit}"
  git rev-parse --git-dir >/dev/null 2>&1 || { log_check 16 WARN "codenav anchors" "SKIP (not a git work tree)"; return 0; }
  local repo_root; repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || { log_check 16 WARN "codenav anchors" "SKIP (no repo root)"; return 0; }
  [ -x "$repo_root/bin/codenav-lint.sh" ] || { log_check 16 PASS "codenav anchors" "(codenav-lint.sh 미도입 — skip)"; return 0; }
  local navdocs_re='docs/CODE_(NAVIGATION|TASKS)\.md$'
  local code_re='unit/feature-0003-agent-web-ui/src/.*\.py$'
  local touched
  case "$mode" in
    pre-commit|shared-pre-commit) touched=$(git diff --cached --name-only 2>/dev/null) ;;
    post-commit)                  touched=$(git diff HEAD~1 HEAD --name-only 2>/dev/null) ;;
    *) log_check 16 WARN "codenav anchors" "SKIP (unknown mode: $mode)"; return 0 ;;
  esac
  if ! printf '%s\n' "$touched" | grep -qE "$navdocs_re|$code_re"; then
    log_check 16 PASS "codenav anchors" "(no code/nav-doc change in diff)"; return 0
  fi
  if bash "$repo_root/bin/codenav-lint.sh" >/dev/null 2>&1; then
    log_check 16 PASS "codenav anchors" "(CODE_NAVIGATION/CODE_TASKS 앵커 resolve)"; return 0
  fi
  log_check 16 WARN "codenav anchors" "AGENTS.md §21.11.4: CODE_NAVIGATION/CODE_TASKS 앵커 미해결(codenav-lint STALE). 'bash bin/codenav-lint.sh' 로 목록 확인 후 문서 재정합. WARN-only(PR block 아님)."
  return 0
}

check_13_visual_verification() {
  local mode="${1:-pre-commit}" fdir="${2:-}"

  if [[ "${GSTACK_SKIP_VISUAL_VERIFICATION:-}" == "1" ]]; then
    log_check 13 WARN "visual verification" "SKIP (escape hatch: GSTACK_SKIP_VISUAL_VERIFICATION=1)"
    return 0
  fi

  # pre-commit 계열에서만 게이트(post-commit 은 이미 커밋됨 — 참고). check #10/#11 처럼
  # META short-circuit 앞에서 무조건 실행되므로(M3), 여기서 모드 가드.
  case "$mode" in
    pre-commit|shared-pre-commit) : ;;
    *) return 0 ;;
  esac

  local changed_files
  changed_files=$(staged_files)

  # 웹 자산 수집(M2 개선 is_web_asset — docs/wiki/.claude 제외, static 밖 UI 확장자 포함).
  local web_assets=() f
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    if is_web_asset "$f"; then web_assets+=("$f"); fi
  done <<<"$changed_files"

  if [ ${#web_assets[@]} -eq 0 ]; then
    log_check 13 PASS "visual verification" "(no web/UI asset change — skip)"
    return 0
  fi

  # 강제 수준 — wrapper FIRST_REQUEST.md 선언(M4: 정규화된 값).
  local scope
  scope=$(read_first_request_scope "visual_verification_scope")

  # 웹 자산이 '속한 feature' 의 TEST.md 로 귀속(m1: CLI fdir 아닌 자산 경로 기반 —
  # 교차-feature vouch 차단). unit/<id>/... → unit/<id>/docs/TEST.md. unit 밖(shared/ 등)
  # 은 CLI fdir 폴백, 없으면 unattributed.
  local targets="" unattributed="" fid
  for f in "${web_assets[@]}"; do
    case "$f" in
      unit/*/*)
        fid="${f#unit/}"; fid="${fid%%/*}"
        targets+="unit/${fid}/docs/TEST.md"$'\n' ;;
      *)
        if [ -n "$fdir" ]; then targets+="${fdir}/docs/TEST.md"$'\n'
        else unattributed+="${f} "; fi ;;
    esac
  done
  targets=$(printf '%s' "$targets" | sort -u | sed '/^$/d')

  # 각 대상 TEST.md 가 '이번 staged diff 에 추가된' Windows-browser Run(또는 미수행 사유)
  # 라인을 담는가(M1: whole-file substring 아닌 추가 라인만 — stale/재-stage/주석 우회 차단).
  local missing="" tmd added frag_dir frag_added
  while IFS= read -r tmd; do
    [ -z "$tmd" ] && continue
    added=$(git diff --cached -- "$tmd" 2>/dev/null | grep -E '^\+' | grep -iE 'windows-browser' || true)
    # META-0026 (ITEM-06): TEST.md 추가 라인 **또는** test-runs.d/ fragment 신규 파일 인정
    # (하위호환 OR — 병렬 Run 기록 append 충돌 제거, §5.3 fragment 규약).
    if [ -z "$added" ]; then
      frag_dir="${tmd%/TEST.md}/test-runs.d"
      frag_added=$(git diff --cached -- "$frag_dir" 2>/dev/null | grep -E '^\+' | grep -iE 'windows-browser' || true)
      [ -z "$frag_added" ] && missing+="${tmd} "
    fi
  done <<<"$targets"
  [ -n "$unattributed" ] && missing+="(unattributed: ${unattributed})"

  if [ -z "$missing" ]; then
    log_check 13 PASS "visual verification" "(대상 TEST.md 에 이번 cycle Windows-browser Run 추가 — PB-0008)"
    return 0
  fi

  if [ "$scope" = "always" ]; then
    log_check 13 FAIL "visual verification" \
      "웹/UI 자산 변경인데 이번 cycle 'Windows-browser' Run(PB-0008) 추가가 없는 대상: ${missing}. bin/win-browser.py 로 시각검증 후 해당 feature docs/test-runs.d/<TASK-또는-REV-id>.md fragment(권장, §5.3) 또는 docs/TEST.md §3 에 'Environment: Windows-browser' Run 을 추가·stage(브리지 불가 시 그 라인에 미수행 사유 명시)하세요 (AGENTS.md §15.4.1 · PB-0008 · visual_verification_scope=always). 긴급: GSTACK_SKIP_VISUAL_VERIFICATION=1"
    return 1
  fi

  log_check 13 WARN "visual verification" \
    "웹/UI 자산 변경에 이번 cycle 'Windows-browser' Run(PB-0008) 추가 없음 — 대상: ${missing}. visual_verification_scope 미선언 → WARN(§15.4.1 권장). always 로 선언하면 hard gate."
  return 0
}

# -----------------------------------------------------------------------------
# Main dispatch
# -----------------------------------------------------------------------------

check_17_ui_copy_budget() {
  # $1 = mode (pre-commit|post-commit|shared-pre-commit). post-commit 은 staged 가 비어
  # 있으므로 HEAD 커밋의 추가 라인을 본다 — staged 고정이면 커밋 후 항상 PASS 가 된다(codex P1).
  local mode="${1:-pre-commit}"
  local scope_flag="--staged"
  [ "$mode" = "post-commit" ] && scope_flag="--commit"
  local conf=".template/ui-copy-budget.conf"
  local helper="${REPO_ROOT:-.}/bin/ui-copy-budget.py"

  if [ "${GSTACK_SKIP_UI_COPY_BUDGET:-0}" = "1" ]; then
    log_check 17 WARN "ui copy budget" "SKIP (escape hatch: GSTACK_SKIP_UI_COPY_BUDGET=1)"
    return 0
  fi
  if [ ! -f "$conf" ]; then
    log_check 17 PASS "ui copy budget" "(opt-in — ${conf} 없음, skip)"
    return 0
  fi
  if [ ! -f "$helper" ]; then
    log_check 17 WARN "ui copy budget" "SKIP (bin/ui-copy-budget.py 없음 — template hop 미적용?)"
    return 0
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    log_check 17 WARN "ui copy budget" "SKIP (python3 미설치)"
    return 0
  fi

  local out rc
  out=$(python3 "$helper" --conf "$conf" "$scope_flag" 2>&1) || rc=$?
  rc=${rc:-0}
  case "$rc" in
    0)
      log_check 17 PASS "ui copy budget" "$(printf '%s' "$out" | tail -1)"
      return 0
      ;;
    2)
      log_check 17 WARN "ui copy budget" "검사 불능(미검증) — $(printf '%s' "$out" | head -1)"
      return 0
      ;;
    *)
      log_check 17 FAIL "ui copy budget" \
        "사용자 대면 텍스트가 예산을 초과했습니다 (AGENTS.md §16.8). $(printf '%s' "$out" | sed -n '2,6p' | tr '\n' ' ') 긴급: GSTACK_SKIP_UI_COPY_BUDGET=1"
      return 1
      ;;
  esac
}

check_18_secret_scan() {
  # $1 = mode (pre-commit|post-commit|shared-pre-commit).
  # 완료 게이트의 시크릿 축 (§16.6 인접, inbox: T3-20260817T0735-001).
  # 근거 (실측 2026-08-14, mysql_conf_tuner 세션 75ec83f1): "완료 게이트 PASS" 59초 뒤
  # 실인증토큰 2개(.gstack/browse.json, terminal-internal-token)가 커밋·push 됐다.
  # .gitignore 보완(#43)은 알려진 경로만 막는다 — 게이트가 없으면 다음번엔 다른 도구의
  # 다른 경로가 같은 방식으로 통과한다.
  #
  # 판정 축 2개 — 둘 다 «이 커밋에 새로 들어오는 것»만 본다 (기존 코드베이스 전수 스캔 아님):
  #   축1 파일명: 알려진 시크릿 부산물 경로가 changeset 에 존재 (내용 무관)
  #   축2 내용: 추가된 라인의 알려진 토큰 prefix / 개인키 헤더 / JWT / 장문 대입값
  # fail-closed (§16.7 G9-c: 검사 불능도 FAIL) — 탈출구 3계층:
  #   (a) 라인 마커 `verify-secret-allow` (정당한 예시 1줄 단위)
  #   (b) `*.example` / `*.sample` / `*.template` 파일은 스캔 제외 (예시 파일 관례)
  #   (c) 긴급 GSTACK_SKIP_SECRET_SCAN=1 → WARN 강등
  local mode="${1:-pre-commit}"

  if [ "${GSTACK_SKIP_SECRET_SCAN:-0}" = "1" ]; then
    # 영속 선언 감지 — 긴급 1회용 hatch 를 settings 로 영구 비활성화하면 게이트가 죽은
    # 채 WARN 만 반복된다 (security P2: 감시 주체 = 우회 주체인 무인 환경의 자기승인 경로).
    local _persist=""
    if grep -q 'GSTACK_SKIP_SECRET_SCAN' .claude/settings.json .claude/settings.local.json 2>/dev/null; then
      _persist=" — ⚠️ settings 에 영속 선언 감지: 1회용 hatch 를 영구 비활성화로 쓰지 말 것"
    fi
    log_check 18 WARN "secret scan" "SKIP (escape hatch: GSTACK_SKIP_SECRET_SCAN=1)${_persist}"
    return 0
  fi

  # diff 플래그 근거는 check #14 와 동일 (--no-color: ANSI 로 `^+` 빗나감 방지 /
  # --no-ext-diff: 외부 diff 의 빈 결과 fail-open 방지 / post-commit 은 1st-parent,
  # root commit 만 git show 폴백). 추가로 `-c core.quotepath=off` — 비ASCII 경로가
  # 8진 이스케이프+따옴표로 감싸이면 파일명 축 정규식과 `+++` 헤더 파싱이 전부 빗나가
  # 한글 디렉토리 아래 .env 가 조용히 PASS 한다 (qa P1 실측 재현, fail-open).
  _c18_diff() {
    case "$mode" in
      post-commit)
        git -c core.quotepath=off diff --no-color --no-ext-diff --unified=0 HEAD^ HEAD 2>/dev/null \
          || git -c core.quotepath=off show --no-color --no-ext-diff --format= --unified=0 HEAD 2>/dev/null
        ;;
      *)
        git -c core.quotepath=off diff --no-color --no-ext-diff --cached --unified=0 2>/dev/null
        ;;
    esac
  }
  _c18_files() {
    case "$mode" in
      post-commit)
        git -c core.quotepath=off diff --no-color --no-ext-diff --name-only HEAD^ HEAD 2>/dev/null \
          || git -c core.quotepath=off show --no-color --no-ext-diff --format= --name-only HEAD 2>/dev/null
        ;;
      *) git -c core.quotepath=off diff --no-color --no-ext-diff --cached --name-only 2>/dev/null ;;
    esac
  }

  local diff_body files
  if ! diff_body=$(_c18_diff); then
    log_check 18 FAIL "secret scan" \
      "git diff 실행 실패 — 시크릿을 검사하지 못했다(미검증, fail-closed). git 설정을 확인할 것"
    return 1
  fi
  if ! files=$(_c18_files); then
    log_check 18 FAIL "secret scan" \
      "git 파일 목록 실패 — 파일명 축을 검사하지 못했다(미검증, fail-closed). git 설정을 확인할 것"
    return 1
  fi

  # 축1 — 파일명 (allowlist 접미사 제외). 게이트의 파일명 집합은 .gitignore 의 gstack
  # 토큰 5패턴과 같은 면을 덮는다 — .gitignore 는 `git add -f`/부재 시 무력하므로
  # 이 축이 그 fallback 이다 (security P2: 두 집합의 불일치는 armed 상태를 남긴다).
  # `.gstack/browse*`·`terminal-*` 는 하위 디렉토리 파일까지 매치한다 (`(/|$)` —
  # security R2: `.gstack/terminal-<id>/token` 형태가 `$` 앵커를 관통했다).
  local name_hits
  name_hits=$(printf '%s\n' "$files" \
    | grep -E '(^|/)\.gstack/(browse[^/]*|terminal-[^/]*)(/|$)|(^|/)\.gstack/claude-available\.json$|(^|/)terminal-internal-token$|(^|/)\.env(\.[A-Za-z0-9_.-]+)?$|(^|/)id_(rsa|ed25519|ecdsa|dsa)$|\.(pem|p12|pfx)$|(^|/)\.netrc$' \
    | grep -vE '\.(example|sample|template)$' || true)

  # 축2 — 추가 라인을 «경로:행:내용» 으로 수집. 경로·행은 FAIL 위치 보고용 — 내용은
  # 에코하지 않는다 (전사·로그에 시크릿 재기록 금지).
  # ⚠️ 헤더 인식은 상태기계로 게이트한다 — `+++` 를 무조건 헤더로 읽으면 소스에 `++ …`
  # 로 시작하는 추가 라인 1줄(diff 렌더 `+++ …`)로 그 파일의 스캔이 무음 비활성화된다
  # (qa R2 P1 실측). 진짜 헤더는 `diff --git` 직후에만 온다 — 콘텐츠 라인은 열 0 에서
  # `diff --git` 를 스푸핑할 수 없다 (`+` 접두로 렌더되므로).
  # ⚠️ example/sample/template 면제는 축1(파일명)에만 있다 — 축2(내용)는 example 파일도
  # 스캔한다 (ux R2 P1: 파일 단위 무료 면제가 라인 단위 사유-강제 마커보다 넓은 역전
  # 구조라, «*.example 로 개명» 이 실토큰 커밋의 승인 경로가 됐다. 정당한 예시 값은
  # placeholder 어휘로 어차피 통과하고, 실토큰 모양 값은 마커로 사유를 남겨야 통과한다).
  local added
  added=$(printf '%s\n' "$diff_body" | awk '
    BEGIN { f = ""; ln = 0; hdr = 0 }
    /^diff --git / { hdr = 1; next }
    hdr && /^\+\+\+ / { f = $0; sub(/^\+\+\+ /, "", f); sub(/\t$/, "", f)
                        gsub(/^"|"$/, "", f); sub(/^b\//, "", f)
                        hdr = 0; next }
    hdr { next }
    /^@@ /     { split($0, a, "+"); split(a[2], b, /[ ,]/); ln = b[1] - 1; next }
    /^\+/      { ln++; printf "%s:%d:%s\n", f, ln, $0; next }
    { next }')

  # allowlist 라인 마커 — 사유 필수 (`verify-secret-allow: <사유>`). bare 마커는 자기승인
  # 남용 경로라 인정하지 않는다 (security P2).
  local marker_re='verify-secret-allow:[[:space:]]*[^[:space:]]'
  local token_hits assign_hits
  token_hits=$(printf '%s\n' "$added" \
    | grep -vE "$marker_re" \
    | grep -E 'ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|gh[ousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{40,}|sk_live_[A-Za-z0-9]{20,}|glpat-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{30,}|npm_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}' \
    || true)
  # 대입형 — 값 ≥ 20자 + placeholder 어휘 제외. 키가 따옴표로 감싸인 JSON/quoted-key
  # (`"token": "…"`) 도 매치해야 한다 (security P1: 동기 사건 파일이 JSON 이었다).
  # known-limitation (security R2 실측, 의도적 미탐 — 오탐율과의 절충): ① 무따옴표 값
  # (`export API_TOKEN=<opaque>` — 벤더 prefix 축이 부분 백스톱) ② escaped-JSON 내장
  # 문자열 (`\"token\": \"…\"`) ③ bracket 표기 (`cfg["secret"] = "…"`).
  local assign_re='(api[_-]?key|secret|token|passwd|password)["'\'']?[[:space:]]*[:=][[:space:]]*["'\''][A-Za-z0-9_/+=.-]{20,}["'\'']'
  # placeholder 제외는 **내용 부분에만** 적용한다 — «경로:행:내용» 전체에 걸면 경로의
  # "example"(.env.example, examples/ 디렉토리)이 내용 스캔을 무음 면제한다 (ux R3 P1
  # 실측: 개명 우회가 대입형 값에 대해 잔존했다).
  assign_hits=$(printf '%s\n' "$added" \
    | grep -vE "$marker_re" \
    | grep -iE "$assign_re" \
    | awk '{ c = $0; sub(/^[^:]*:[0-9]+:/, "", c)
             if (tolower(c) !~ /example|placeholder|changeme|dummy|your[_-]|<[a-z_%-]+>|[$][{]|[{][{]|xxxx/) print }' \
    || true)

  # 내용 축은 라인(경로:행) 단위로 dedupe 한다 — 한 라인이 토큰패턴·대입형에 동시
  # 매치되면 이중 계수 + 샘플 슬롯 중복 점유가 된다 (ux R2 P2).
  local content_locs n_name n_content total
  content_locs=$(printf '%s\n%s\n' "$token_hits" "$assign_hits" | grep . | cut -d: -f1,2 | sort -u || true)
  n_name=$(printf '%s' "$name_hits" | grep -c . || true)
  n_content=$(printf '%s' "$content_locs" | grep -c . || true)
  total=$((n_name + n_content))

  if [ "$total" -eq 0 ]; then
    log_check 18 PASS "secret scan"
    return 0
  fi

  # FAIL 안내는 축별 + 모드별로 분기한다 (ux R1/R2):
  # - 파일명 축의 첫 안내는 unstage·회전이다 — «*.example 개명» 을 첫 remedy 로 주면
  #   동기 사건 동형(내용이 실토큰인 크리덴셜 파일)이 개명만으로 통과한다 (축2 가
  #   example 도 스캔하도록 바뀌었으나, opaque 토큰은 축2 패턴 밖일 수 있다).
  # - post-commit 은 unstage 가 실행 불능 시점이다 — reset/amend + push 금지 안내.
  # - 내용 축은 경로:행만 출력한다 (값 에코 금지 — 게이트가 유출을 재생산하지 않는다).
  local name_sample loc_sample hint="" fix_name fix_content
  if [ "$mode" = "post-commit" ]; then
    fix_name="push 금지 — git reset --soft HEAD^ (또는 amend) 로 커밋에서 제거하고, 실크리덴셜이면 즉시 회전(rotate)"
    fix_content="push 금지 — reset/amend 후 실토큰이면 즉시 회전, 정당한 예시면 그 라인에 'verify-secret-allow: <사유>' 마커를 달아 재커밋"
  else
    fix_name="unstage(+.gitignore 등재)하고 실크리덴셜이면 즉시 회전(rotate) — 내용을 placeholder 로 스크럽한 예시일 때만 *.example 개명"
    fix_content="실토큰이면 커밋 중단 후 즉시 회전(rotate), 정당한 예시면 그 라인에 'verify-secret-allow: <사유>' 마커"
  fi
  if [ "$n_name" -gt 0 ]; then
    name_sample=$(printf '%s\n' "$name_hits" | head -3 | tr '\n' ' ')
    name_sample="${name_sample% }"
    hint="파일명 축 ${n_name}건 (${name_sample}) → ${fix_name}. "
  fi
  if [ "$n_content" -gt 0 ]; then
    loc_sample=$(printf '%s\n' "$content_locs" | head -3 | tr '\n' ' ')
    loc_sample="${loc_sample% }"
    hint="${hint}내용 축 ${n_content}건 @ ${loc_sample} → ${fix_content}. "
  fi
  log_check 18 FAIL "secret scan" \
    "시크릿 의심 ${total}건 — ${hint}placeholder 값(example/changeme/<...>/\${...})은 자동 통과한다. 긴급 1회: GSTACK_SKIP_SECRET_SCAN=1"
  return 1
}

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

  # Check #17 (§16.8, v3.43.0) — unconditional, opt-in(conf 부재 시 즉시 PASS).
  local check17_status=0
  if ! check_17_ui_copy_budget "$mode"; then
    check17_status=1
  fi

  # Check #18 (§16.6 인접, v3.48.0) — unconditional. 시크릿 유출은 changeset
  # 종류와 무관한 staged-diff fact 다 (inbox: T3-20260817T0735-001).
  local check18_status=0
  if ! check_18_secret_scan "$mode"; then
    check18_status=1
  fi

  # Check #13 (PB-0008 visual verification) — unconditional, META/shared 모드보다 먼저 실행 (M3).
  # 웹/UI 자산 변경은 changeset 이 pure-meta(예: unit/_template/** scaffold)여도 시각검증 게이트
  # 대상이므로 META short-circuit 앞에서 판정한다. 자산 경로에서 feature TEST.md 를 도출하므로
  # feature_id 미해결(META/shared)에서도 동작(비-unit 자산만 CLI fdir 폴백 — 여기선 미해결이라 "").
  local check13_status=0
  if ! check_13_visual_verification "$mode" ""; then
    check13_status=1
  fi

  # Check #14 (META-0024) — unconditional: conflict-marker 잔존은 changeset 종류 무관.
  local check14_status=0
  if ! check_14_conflict_markers "$mode"; then
    check14_status=1
  fi

  # META-0027 (ITEM-07): main 대비 behind 조기 신호 — 비차단 WARN (fetch 없이 로컬
  # origin/main ref 기준: 약간 stale 할 수 있으나 경고 목적으론 충분, 매 verify 마다
  # 네트워크 왕복을 만들지 않는다. hard gate 는 cycle-finalize 신선도 게이트가 담당).
  if [ "$mode" = "pre-commit" ]; then
    local _behind_main
    _behind_main=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)
    if [ "${_behind_main:-0}" -ge 10 ]; then
      printf 'WARN: 현재 브랜치가 origin/main 대비 %s commit behind — 머지 전 rebase/update 권장 (cycle-finalize 가 behind>=%s 이면 자동 update-branch 후 CLEAN 재검증, META-0027)\n' \
        "$_behind_main" "${MERGE_BEHIND_GATE:-20}" >&2
    fi
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
    printf 'META mode: pure-meta changeset detected. checks #1-#8 skipped (§18.4). checks #10, #11, #13, #14 always run.\n' >&2
    local failed=$((check10_status + check11_status + check13_status + check14_status + check17_status + check18_status))
    case "$mode" in
      post-commit) check_9_review_entry post-commit "" || failed=$((failed + 1)) ;;
      *) check_9_review_entry pre-commit "" || failed=$((failed + 1)) ;;
    esac
    if [ "$failed" -eq 0 ]; then
      printf '\nverify-completion: PASS (META mode: checks #9, #10, #11, #13, #14 ran)\n' >&2
      exit 0
    else
      printf '\nverify-completion: FAIL (META mode: %d of #9, #10, #11, #13, #14 failed)\n' "$failed" >&2
      exit 1
    fi
  fi

  # Shared mode uses its own minimal check set + check #9 + check #10 + check #11 + check #13.
  if [ "$mode" = "shared-pre-commit" ]; then
    local failed=$((check10_status + check11_status + check13_status + check14_status + check17_status + check18_status))
    check_shared_modify pre-commit || failed=$((failed + 1))
    check_8_unstaged_residual pre-commit || failed=$((failed + 1))
    check_9_review_entry shared-pre-commit "" || failed=$((failed + 1))
    exit "$([ "$failed" -eq 0 ] && echo 0 || echo 1)"
  fi

  validate_feature_id "$feature_id"
  local fdir
  fdir=$(feature_dir "$feature_id")

  # check13/14_status: #13(visual)·#14(conflict-marker) 는 META short-circuit 앞에서 이미 실행됨.
  local failed=$((check10_status + check11_status + check13_status + check14_status + check17_status + check18_status))
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
  # Check #13 (v3.42.0): §16.7 G1 요청 범위 자기-열거 — WARN-only, failed 영향 X.
  check_13_requested_scope "$fdir" || true
  check_15_routemap_freshness "$effective_mode" || true
  check_16_codenav_lint "$effective_mode" || true

  if [ "$failed" -eq 0 ]; then
    printf '\nverify-completion: PASS (gate checks + worktree binding + repo immutability + visual-verification #13; #12 wiki WARN-only)\n' >&2
    exit 0
  else
    printf '\nverify-completion: FAIL (%d gate checks failed)\n' "$failed" >&2
    exit 1
  fi
}

main "$@"
