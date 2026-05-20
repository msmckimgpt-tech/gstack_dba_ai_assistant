#!/usr/bin/env bash
# bin/cycle-init.sh
#
# Cycle entry helper for AGENTS.md §13.2 (v3.9.0+).
# 신규 ai/* worktree 를 main 최신화 후 자동 생성:
#   1. main worktree 식별
#   2. main 최신화 (git fetch + git pull --ff-only origin main) — stale base 차단
#   3. git worktree add <project_root>/.worktrees/<feat> -b ai/<agent>/<feat>
#   4. 다음 세션 진입 명령 출력 (AI 의 cwd 자율 변경 금지 P1 유지 — 사용자가
#      새 Claude Code 세션을 worktree path 에서 시작)
#
# 자동 진행 정책 (AGENTS.md §13.2 + §16.3 Step 6 정합):
#   normal 경로 (main worktree 식별 + fetch/pull 성공 + worktree 생성 가능) 는
#   사람 명시 요청 없이 자동 진행. abnormal 경로 (non-fast-forward, branch
#   이미 존재 + 충돌, worktree path 이미 존재 + 다른 branch) 는 자동 중단 +
#   사용자 결정.
#
# Usage:
#   bash bin/cycle-init.sh --feature <feature-id>
#     [--agent <agent-name>]      (default: $USER 또는 'ai')
#     [--base <branch>]           (default: main)
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
  sed -n '2,29p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
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

다음 단계 (사용자):
  새 Claude Code 세션을 worktree path 에서 시작하세요 — AI 는 cwd 를 자율로
  변경하지 않습니다 (AGENTS.md §13.2 P1 trigger).

    cd $NEW_WORKTREE_PATH
    claude   # 또는 사용하는 Claude Code 진입 명령

  또는 진입 직후 다음 명령으로 entry persona 호출:
    /_template:entry <작업 의도>
EOF

exit 0
