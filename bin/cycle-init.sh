#!/usr/bin/env bash
# bin/cycle-init.sh
#
# Cycle entry helper for AGENTS.md §13.2 (v3.9.0+, inline execution v3.10.0+).
# 신규 ai/* worktree 를 main 최신화 후 자동 생성:
#   1. main worktree 식별
#   2. main 최신화 (git fetch + git pull --ff-only origin main) — stale base 차단
#   3. git worktree add <project_root>/.worktrees/<feat> -b ai/<agent>/<feat>
#   4. 종료 보고 — 호출 모드 분기:
#      - inline mode (env CYCLE_INIT_FROM_ENTRY_PERSONA=1): AI 가 본 세션에서
#        cd 후 Phase 6 진입 (AGENTS.md §13.2.1 P1 carve-out, v3.10.0+)
#      - 직접 호출 (env 없음): 사용자가 새 Claude Code 세션을 worktree path 에서 시작
#
# 자동 진행 정책 (AGENTS.md §13.2 + §16.3 Step 6 정합):
#   normal 경로 (main worktree 식별 + fetch/pull 성공 + worktree 생성 가능) 는
#   사람 명시 요청 없이 자동 진행. abnormal 경로 (non-fast-forward, branch
#   이미 존재 + 충돌, worktree path 이미 존재 + 다른 branch) 는 자동 중단 +
#   사용자 결정.
#
# Inline execution mode (v3.10.0+, AGENTS.md §13.2.1 P1 carve-out):
#   env CYCLE_INIT_FROM_ENTRY_PERSONA=1 로 호출 시 종료 보고에 "AI 가 cd 후 본
#   세션에서 Phase 6 진입" 안내 출력. entry persona arg-given dispatch 가 본 모드로
#   호출한다. 직접 호출 (env var 없음) 은 기존 안내 (사용자가 새 세션 시작).
#
# Usage:
#   bash bin/cycle-init.sh --feature <feature-id>
#     [--agent <agent-name>]      (default: $USER 또는 'ai')
#     [--base <branch>]           (default: main)
#     [--hot-paths <p1,p2,...>]   (선택 — 주요 편집 예정 경로 1~5개. META-0029 WIP 규약:
#                                  REGISTRY 활성 세션과 겹침 >= 2 면 경고(차단 아님))
#     [--dry-run]                 (모든 mutation 명령 출력만)
#     [--print-only]              (main 최신화도 안 함, 명령만 출력 — 기존 수동 패턴 호환)
#     [--help]
#
# Exit codes:
#   0 — worktree 생성 PASS or idempotent skip (이미 존재)
#   1 — runtime failure (NFF pull, branch 충돌 등)
#   2 — usage error
#
# Requires: bash >= 4, git >= 2.20.

set -euo pipefail

# ── Globals ───────────────────────────────────────────────────────────────
FEATURE_ID=""
AGENT_NAME=""
BASE_BRANCH="main"
DRY_RUN=0
PRINT_ONLY=0
HOT_PATHS=""   # META-0029: 주요 편집 예정 경로(콤마 구분, 선택) — WIP 핫스팟 soft 게이트

# ── Helpers ───────────────────────────────────────────────────────────────
log_info()  { printf "[cycle-init] %s\n"           "$*" >&2; }
log_step()  { printf "\n[cycle-init] === %s ===\n" "$*" >&2; }
log_warn()  { printf "[cycle-init] WARN: %s\n"     "$*" >&2; }
log_error() { printf "[cycle-init] ERROR: %s\n"    "$*" >&2; }
die()       { log_error "$@"; exit 1; }
usage_die() { log_error "$@"; printf "Run with --help for usage.\n" >&2; exit 2; }

run_or_dryrun() {
  if [ "$DRY_RUN" -eq 1 ] || [ "$PRINT_ONLY" -eq 1 ]; then
    printf "[%s] %s\n" "$([ "$PRINT_ONLY" -eq 1 ] && echo "print-only" || echo "dry-run")" "$*" >&2
  else
    log_info "exec: $*"
    eval "$@"
  fi
}

show_help() {
  sed -n '2,31p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

# ── Argument parsing ──────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
  case "$1" in
    --feature)      FEATURE_ID="${2:-}"; shift 2 ;;
    --feature=*)    FEATURE_ID="${1#--feature=}"; shift ;;
    --agent)        AGENT_NAME="${2:-}"; shift 2 ;;
    --agent=*)      AGENT_NAME="${1#--agent=}"; shift ;;
    --base)         BASE_BRANCH="${2:-}"; shift 2 ;;
    --base=*)       BASE_BRANCH="${1#--base=}"; shift ;;
    --hot-paths)    HOT_PATHS="${2:-}"; shift 2 ;;
    --hot-paths=*)  HOT_PATHS="${1#--hot-paths=}"; shift ;;
    --dry-run)      DRY_RUN=1; shift ;;
    --print-only)   PRINT_ONLY=1; shift ;;
    --help|-h)      show_help; exit 0 ;;
    *)              usage_die "Unknown arg: $1" ;;
  esac
done

[ -n "$FEATURE_ID" ] || usage_die "--feature <feature-id> required."

# feature-id 검증 — slug 형태 (alnum, '-', '_' 만 허용, '/' 금지).
case "$FEATURE_ID" in
  *[/\ \\]*) usage_die "feature-id 에 '/' / 공백 / 백슬래시 사용 불가: '$FEATURE_ID'" ;;
  *) ;;
esac

# AGENT_NAME default: $USER 또는 'ai'.
if [ -z "$AGENT_NAME" ]; then
  AGENT_NAME="${USER:-ai}"
fi

# ── Pre-flight: git repo + main worktree 식별 ─────────────────────────────
command -v git >/dev/null 2>&1 || die "git not found in PATH."

git rev-parse --git-dir >/dev/null 2>&1 || die "Not inside a git repository (cwd: $(pwd))."

# main worktree = `git worktree list --porcelain` 의 첫 entry.
MAIN_WORKTREE_PATH="$(git worktree list --porcelain | awk '/^worktree /{print substr($0,10); exit}')"
[ -n "$MAIN_WORKTREE_PATH" ] || die "main worktree path resolution failed."

# project_root = wrapper of MAIN_WORKTREE_PATH (= policy_root).
# standard layout: <wrapper>/repo = policy_root, <wrapper>/.worktrees = sibling.
PROJECT_ROOT="$(dirname "$MAIN_WORKTREE_PATH")"
WORKTREE_PARENT="$PROJECT_ROOT/.worktrees"
NEW_WORKTREE_PATH="$WORKTREE_PARENT/$FEATURE_ID"
NEW_BRANCH="ai/$AGENT_NAME/$FEATURE_ID"

# v3.11.0: nested worktree 거부 — <wrapper>/.worktrees/<feat> 외 위치 금지 (§13.2.3).
case "$NEW_WORKTREE_PATH" in
  */repo/.worktrees/*)
    die "nested worktree 거부 — worktree path 가 repo/ 내부에 있습니다: '$NEW_WORKTREE_PATH'. <wrapper>/.worktrees/<feat> 위치를 사용하세요 (§13.2.3 lifecycle)." ;;
esac

log_info "main worktree:   $MAIN_WORKTREE_PATH"
log_info "project root:    $PROJECT_ROOT"
log_info "new worktree:    $NEW_WORKTREE_PATH"
log_info "new branch:      $NEW_BRANCH"
log_info "base branch:     $BASE_BRANCH"
log_info "mode:            $([ "$PRINT_ONLY" -eq 1 ] && echo "print-only" || ([ "$DRY_RUN" -eq 1 ] && echo "dry-run" || echo "execute"))"

# ── Step 1: main 최신화 (필수 — 사용자 추가 요구) ────────────────────────
log_step "Step 1: main worktree 최신화 (git fetch + pull --ff-only origin $BASE_BRANCH)"

if [ "$PRINT_ONLY" -eq 1 ]; then
  printf "[print-only] git -C %s fetch origin\n" "$MAIN_WORKTREE_PATH" >&2
  printf "[print-only] git -C %s pull --ff-only origin %s\n" "$MAIN_WORKTREE_PATH" "$BASE_BRANCH" >&2
else
  # fetch — 실패는 WARN (offline 환경 대비).
  if [ "$DRY_RUN" -eq 1 ]; then
    printf "[dry-run] git -C %s fetch origin\n" "$MAIN_WORKTREE_PATH" >&2
  else
    if ! git -C "$MAIN_WORKTREE_PATH" fetch origin 2>&1; then
      log_warn "git fetch origin failed (network/auth?). 계속 진행하지만 base branch 가 stale 일 수 있습니다."
    fi
  fi

  # pull --ff-only — non-fast-forward 는 fail-loud.
  if [ "$DRY_RUN" -eq 1 ]; then
    printf "[dry-run] git -C %s pull --ff-only origin %s\n" "$MAIN_WORKTREE_PATH" "$BASE_BRANCH" >&2
  else
    if ! git -C "$MAIN_WORKTREE_PATH" pull --ff-only origin "$BASE_BRANCH" 2>&1; then
      die "git pull --ff-only origin $BASE_BRANCH failed (non-fast-forward?). main 에 로컬 commit 이 있는지 확인 + manual resolve. 자동 merge/rebase 는 silent history rewriting 우려로 지원하지 않습니다."
    fi
  fi
fi

# ── Step 2: pre-check (이미 존재 시 idempotent skip) ──────────────────────
log_step "Step 2: worktree / branch 존재 검사 (idempotent)"

EXISTING_WORKTREE_BRANCH=""
if git worktree list --porcelain | awk -v p="$NEW_WORKTREE_PATH" '
  $1=="worktree" && $2==p { found=1 }
  found && $1=="branch" { sub("refs/heads/","",$2); print $2; exit }
' | grep -q .; then
  EXISTING_WORKTREE_BRANCH="$(git worktree list --porcelain | awk -v p="$NEW_WORKTREE_PATH" '
    $1=="worktree" && $2==p { found=1 }
    found && $1=="branch" { sub("refs/heads/","",$2); print $2; exit }
  ')"
fi

EXISTING_BRANCH=""
if git -C "$MAIN_WORKTREE_PATH" rev-parse --verify --quiet "$NEW_BRANCH" >/dev/null 2>&1; then
  EXISTING_BRANCH="$NEW_BRANCH"
fi

if [ -n "$EXISTING_WORKTREE_BRANCH" ]; then
  if [ "$EXISTING_WORKTREE_BRANCH" = "$NEW_BRANCH" ]; then
    log_info "worktree $NEW_WORKTREE_PATH 이미 존재 + branch $NEW_BRANCH 매칭 — idempotent skip."
    EXISTING_OK=1
  else
    die "worktree $NEW_WORKTREE_PATH 이미 존재하지만 branch 가 다름 ($EXISTING_WORKTREE_BRANCH != $NEW_BRANCH). 수동 정리 필요: git worktree remove $NEW_WORKTREE_PATH"
  fi
else
  EXISTING_OK=0
fi

# ── Step 3: worktree 생성 ────────────────────────────────────────────────
if [ "$EXISTING_OK" -eq 1 ]; then
  log_step "Step 3: worktree 생성 (skip — 이미 존재)"
else
  log_step "Step 3: worktree 생성"

  # parent dir 준비.
  if [ ! -d "$WORKTREE_PARENT" ]; then
    run_or_dryrun "mkdir -p $WORKTREE_PARENT"
  fi

  if [ -n "$EXISTING_BRANCH" ]; then
    # branch 가 이미 존재 — -b 없이 checkout.
    log_info "branch $NEW_BRANCH 이미 존재 — -b 생략, 기존 branch 체크아웃."
    run_or_dryrun "git -C $MAIN_WORKTREE_PATH worktree add $NEW_WORKTREE_PATH $NEW_BRANCH"
  else
    # 신규 branch 작성 — -b + base branch.
    run_or_dryrun "git -C $MAIN_WORKTREE_PATH worktree add $NEW_WORKTREE_PATH -b $NEW_BRANCH $BASE_BRANCH"
  fi
fi

# ── §13.2.8/META-0029: worktree 세션 REGISTRY 기록 + 핫스팟 soft 게이트 ─────
# REGISTRY 는 <project_root>/worktrees/REGISTRY.md — repo working tree 밖 운영 파일
# (§13.2.8 정본 경로). 부재 시 스키마와 함께 부트스트랩. entry 는 자기 블록만 추가
# (공유 문서가 새 충돌원이 되지 않게 — §13.2 규약). 실패는 경고만(cycle 진행 비차단).
# §18.8 패널(REV-20260711T051835) 반영: flock 직렬화(MAJOR-4) · 제거+삽입 단일-패스
# 원자 rewrite + 삽입 검증 후 mv(MAJOR-2) · 명시 rc 캡처로 거짓 성공 로그 제거(MAJOR-1)
# · 자기 블록 제거는 Active 구간 한정 — Closed 이력 보존(MINOR-8) · 겹침은 브랜치(entry)
# distinct 집계(MINOR-5) · session_id fallback = claude-session-<PID>(MINOR-7, §13.2.8).
REGISTRY_FILE="$PROJECT_ROOT/worktrees/REGISTRY.md"

registry_record() {
  mkdir -p "$PROJECT_ROOT/worktrees" || return 1
  # N-12: project_root 가 git working tree 인 배치만 .gitignore 등록(본 배치 wrapper 는 git 밖 — 비적용)
  if git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    grep -qxF 'worktrees/' "$PROJECT_ROOT/.gitignore" 2>/dev/null \
      || printf 'worktrees/\n' >>"$PROJECT_ROOT/.gitignore" || return 1
  fi
  # 병렬 cycle-init 직렬화 — REGISTRY 가 다중 세션 조정 파일인 만큼 lost-update 차단
  exec 9>"$REGISTRY_FILE.lock" || return 1
  flock -w 10 9 || { log_warn "REGISTRY lock 획득 실패(10s) — 기록 생략"; return 1; }

  if [ ! -f "$REGISTRY_FILE" ]; then
    cat >"$REGISTRY_FILE" <<'REG' || return 1
# Worktree Session REGISTRY (AGENTS.md §13.2.8 / §13.2.5-A WIP 규약 — META-0029)

> cycle-init 이 활성 세션 entry 를 자동 기록한다. 각 세션은 **자기 블록만** 수정.
> 같은 핫스팟의 복수 브랜치는 `merge_order:` 로 머지 순서를 사전 선언(순차 머지 원칙).
> cycle-finalize Step 6 이 종료 entry 를 `## Closed` 로 자동 이동(수동 보조 허용).

## Active

## Closed
REG
  fi

  # 핫스팟 겹침 soft 게이트 — 지표 = 내 hot_paths 와 겹치는 **활성 브랜치(entry) distinct 수**
  # (경로쌍 수 아님 — 정책 준수 상태 오탐 방지). 나 외 ≥2 = 동일 핫스팟 in-flight 3개째부터 경고.
  if [ -n "$HOT_PATHS" ]; then
    local entry_paths overlap_n overlap_list ebr epaths m a hit
    entry_paths="$(awk '
      /^## Active$/ {act=1; next}
      /^## Closed$/ {act=0}
      !act {next}
      /^### / {cur=substr($0,5); next}
      /^- hot_paths:/ && cur != "" {
        line=$0; sub(/^- hot_paths:[ ]*/,"",line); print cur "\t" line
      }
    ' "$REGISTRY_FILE")"
    overlap_n=0; overlap_list=""
    while IFS=$'\t' read -r ebr epaths; do
      [ -n "$ebr" ] || continue
      [ "$ebr" = "$NEW_BRANCH" ] && continue
      hit=""
      IFS=',' read -ra _mine <<<"$HOT_PATHS"
      for m in "${_mine[@]}"; do
        m="$(printf '%s' "$m" | sed 's/^[ \t]*//; s/[ \t]*$//')"; [ -n "$m" ] || continue
        [ -n "$hit" ] && break
        IFS=',' read -ra _theirs <<<"$epaths"
        for a in "${_theirs[@]}"; do
          a="$(printf '%s' "$a" | sed 's/^[ \t]*//; s/[ \t]*$//')"; [ -n "$a" ] || continue
          case "$a" in '<'*) continue ;; esac   # <미선언> placeholder 제외
          case "$m" in "$a"|"$a"/*) hit="$m~$a"; break ;; esac
          case "$a" in "$m"/*) hit="$m~$a"; break ;; esac
        done
      done
      if [ -n "$hit" ]; then overlap_n=$((overlap_n+1)); overlap_list="$overlap_list ${ebr}(${hit})"; fi
    done <<<"$entry_paths"
    if [ "$overlap_n" -ge 2 ]; then
      log_warn "핫스팟 WIP 경고 (차단 아님, META-0029): 같은 핫스팟을 편집 중인 활성 브랜치 ${overlap_n}개 —${overlap_list} (나 포함 $((overlap_n+1))개 → 동시 ≤ 2 권고 초과)"
      log_warn "  §13.2.5-A: 머지 순서를 REGISTRY merge_order 에 사전 선언(순차 머지) · 당일 랜딩 분할 검토"
    fi
  fi

  # 제거(Active 구간의 자기 블록만 — 재실행 멱등) + 삽입을 **단일 awk 패스**로 원자 rewrite.
  # 동일 디렉터리 mktemp → 삽입 성공 검증 → mv (중간 실패 시 원본 무손상 — MAJOR-2).
  local tmp
  tmp="$(mktemp "$REGISTRY_FILE.XXXXXX")" || return 1
  awk -v br="### $NEW_BRANCH" \
      -v sid="${CLAUDE_SESSION_ID:-claude-session-$PPID}" \
      -v ts="$(date +%Y-%m-%dT%H:%M:%S%z)" \
      -v wt="$NEW_WORKTREE_PATH" \
      -v hp="${HOT_PATHS:-<미선언>}" '
    /^## Active$/ {
      print; print ""
      print br
      print "- session_id: " sid
      print "- opened_at: " ts
      print "- worktree: " wt
      print "- hot_paths: " hp
      print "- merge_order: <미선언>"
      act=1; next
    }
    skip && (/^### / || /^## /) {skip=0}
    /^## Closed$/ {act=0}
    act && $0 == br {skip=1; next}
    skip {next}
    {print}
  ' "$REGISTRY_FILE" >"$tmp" || { rm -f "$tmp"; return 1; }
  grep -qxF "### $NEW_BRANCH" "$tmp" || { rm -f "$tmp"; return 1; }
  mv "$tmp" "$REGISTRY_FILE" || { rm -f "$tmp"; return 1; }
  return 0
}

if [ "$DRY_RUN" -eq 0 ] && [ "$PRINT_ONLY" -eq 0 ]; then
  if registry_record; then
    log_info "REGISTRY entry 기록: $NEW_BRANCH ($REGISTRY_FILE)"
  else
    log_warn "REGISTRY 기록 실패 — cycle 진행에는 영향 없음 (수동 기록 가능: $REGISTRY_FILE)"
  fi
  exec 9>&- 2>/dev/null || true
fi

# ── 종료 보고 ─────────────────────────────────────────────────────────────
log_step "cycle-init 완료"

# 새 worktree 의 base commit hash (참고용).
if [ "$DRY_RUN" -eq 0 ] && [ "$PRINT_ONLY" -eq 0 ] && [ -d "$NEW_WORKTREE_PATH" ]; then
  BASE_COMMIT="$(git -C "$NEW_WORKTREE_PATH" rev-parse --short HEAD 2>/dev/null || echo "unknown")"
else
  BASE_COMMIT="(not created)"
fi

cat >&2 <<EOF

종료 보고:
  worktree path:   $NEW_WORKTREE_PATH
  branch:          $NEW_BRANCH
  base commit:     $BASE_COMMIT
  mode:            $([ "$PRINT_ONLY" -eq 1 ] && echo "print-only" || ([ "$DRY_RUN" -eq 1 ] && echo "dry-run" || echo "executed"))
EOF

if [ "${CYCLE_INIT_FROM_ENTRY_PERSONA:-0}" = "1" ]; then
  cat >&2 <<EOF

Inline execution mode (entry persona dispatch — AGENTS.md §13.2.1 P1 carve-out):
  AI 가 본 세션에서 다음 명령을 자동 진행합니다 — 사용자 추가 조치 불필요.

    cd $NEW_WORKTREE_PATH

  이후 entry persona Phase 6 (작업 실행) 으로 진입. cycle 종료 시
  bin/cycle-finalize.sh 가 PR 머지 후 cleanup 자동 진행.
EOF
else
  cat >&2 <<EOF

다음 단계 (사용자):
  새 Claude Code 세션을 worktree path 에서 시작하세요 — AI 는 cwd 를 자율로
  변경하지 않습니다 (AGENTS.md §13.2 P1 trigger).

    cd $NEW_WORKTREE_PATH
    claude   # 또는 사용하는 Claude Code 진입 명령

  또는 진입 직후 다음 명령으로 entry persona 호출:
    /_template:entry <작업 의도>

  자동 inline execution 을 원하면 entry persona arg-given dispatch 로 호출하세요:
    /_template:entry <작업 의도>  # mutation 신호 감지 시 본 흐름 자동 진행
EOF
fi

exit 0
