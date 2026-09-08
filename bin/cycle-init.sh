#!/usr/bin/env bash
# bin/cycle-init.sh
#
# Cycle entry helper for AGENTS.md §13.2 (v3.9.0+, inline execution v3.10.0+).
# 신규 ai/* worktree 를 main 최신화 후 자동 생성:
#   1. main worktree 식별
#   2. main 최신화 (git fetch + git pull --ff-only origin main) — stale base 차단
#   3. git worktree add <project_root>/.worktrees/<feat> -b ai/<agent>/<feat>
#   4. 종료 보고 — AI 가 본 세션에서 생성한 worktree 를 작업 경로로 사용해 계속 진행
#
# 자동 진행 정책 (AGENTS.md §13.2 + §16.3 Step 6 정합):
#   normal 경로 (main worktree 식별 + fetch/pull 성공 + worktree 생성 가능) 는
#   사람 명시 요청 없이 자동 진행. abnormal 경로 (non-fast-forward, branch
#   이미 존재 + 충돌, worktree path 이미 존재 + 다른 branch) 는 자동 중단 +
#   사용자 결정.
#
# 호출 호환: CYCLE_INIT_FROM_ENTRY_PERSONA 값과 무관하게 같은 세션에서 계속한다.
#   entry persona 와 직접 호출 모두 AGENTS.md §13.2 의 현재 위임 범위를 따른다.
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

# ── 권한 어댑터 로드 (§13.2.10) ───────────────────────────────────────────
# git 은 **언제나 원 호출자로** 실행한다. 승격은 공유 운영 파일(REGISTRY 등)이 다른 계정
# 소유로 굳어 접근 불가일 때 `priv_ensure_writable` 이 복구하는 데만 쓴다 (정상 상태에서는
# sudo 호출 0회). `${BASH_SOURCE[0]}` + readlink: symlink 경유 호출에서도 lib 경로 유지.
# shellcheck source=lib/privilege.sh
. "$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)/lib/privilege.sh"

[ -n "$FEATURE_ID" ] || usage_die "--feature <feature-id> required."

# ── 인자 검증 — `run_or_dryrun` 의 `eval` 에 도달하므로 화이트리스트 강제 (§13.2.10) ──
# 이전 검증은 '/'·공백·백슬래시만 막아 `;`·`$`·백틱·`|`·`&`·`>` 가 통과했다. feature slug 는
# 사람이 아닌 것(entry persona dispatch, 로드맵 항목 파생)이 만드는 경로가 있어, 문자열
# 한 개가 임의 명령 실행이 될 수 있었다.
case "$FEATURE_ID" in
  ""|-*) usage_die "feature-id 형식 오류 (빈 값 또는 '-' 시작): '$FEATURE_ID'" ;;
esac
[[ "$FEATURE_ID" =~ ^[A-Za-z0-9._-]+$ ]] \
  || usage_die "feature-id 는 영숫자·'.'·'_'·'-' 만 허용: '$FEATURE_ID'"

# AGENT_NAME default: $SUDO_USER → $USER → 'ai'.
# `SUDO_USER` 우선: 누군가 이 스크립트를 sudo 로 감싸 호출해도 브랜치가 `ai/root/…` 로
# 어긋나지 않게 한다 (sudo 는 -E 를 줘도 USER/LOGNAME 을 runas 로 덮어쓴다).
if [ -z "$AGENT_NAME" ]; then
  AGENT_NAME="${SUDO_USER:-${USER:-ai}}"
fi
[[ "$AGENT_NAME" =~ ^[A-Za-z0-9._-]+$ ]] \
  || usage_die "agent 이름은 영숫자·'.'·'_'·'-' 만 허용: '$AGENT_NAME'"
[[ "$BASE_BRANCH" =~ ^[A-Za-z0-9._/-]+$ ]] \
  || usage_die "base branch 이름에 허용되지 않는 문자: '$BASE_BRANCH'"

# ── Pre-flight: git repo + main worktree 식별 ─────────────────────────────
command -v git >/dev/null 2>&1 || die "git not found in PATH."

git rev-parse --git-dir >/dev/null 2>&1 || die "Not inside a git repository (cwd: $(pwd))."

# main worktree = `git worktree list --porcelain` 의 첫 entry.
MAIN_WORKTREE_PATH="$(git worktree list --porcelain | awk '/^worktree /{print substr($0,10); exit}')"
[ -n "$MAIN_WORKTREE_PATH" ] || die "main worktree path resolution failed."
MAIN_BRANCH="$(git -C "$MAIN_WORKTREE_PATH" symbolic-ref --quiet --short HEAD)" \
  || die "main worktree is detached; a named branch is required."

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
log_step "Step 1: main worktree 최신화 (git fetch + pull --ff-only origin $MAIN_BRANCH)"

if [ "$PRINT_ONLY" -eq 1 ]; then
  printf "[print-only] git -C %s fetch origin\n" "$MAIN_WORKTREE_PATH" >&2
  printf "[print-only] git -C %s pull --ff-only origin %s\n" "$MAIN_WORKTREE_PATH" "$MAIN_BRANCH" >&2
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
    printf "[dry-run] git -C %s pull --ff-only origin %s\n" "$MAIN_WORKTREE_PATH" "$MAIN_BRANCH" >&2
  else
    if ! git -C "$MAIN_WORKTREE_PATH" pull --ff-only origin "$MAIN_BRANCH" 2>&1; then
      die "git pull --ff-only origin $MAIN_BRANCH failed (non-fast-forward?). main 에 로컬 commit 이 있는지 확인 + manual resolve. 자동 merge/rebase 는 silent history rewriting 우려로 지원하지 않습니다."
    fi
  fi
fi

# --base selects the new worktree's start point; it must never be pulled into main.
BASE_REF="$BASE_BRANCH"
if ! git -C "$MAIN_WORKTREE_PATH" show-ref --verify --quiet "refs/heads/$BASE_BRANCH" && \
   git -C "$MAIN_WORKTREE_PATH" show-ref --verify --quiet "refs/remotes/origin/$BASE_BRANCH"; then
  BASE_REF="refs/remotes/origin/$BASE_BRANCH"
fi
git -C "$MAIN_WORKTREE_PATH" rev-parse --verify --quiet "${BASE_REF}^{commit}" >/dev/null \
  || die "base branch '$BASE_BRANCH' not found locally or at origin."

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
    # §13.2.10: 신규 생성 직후에만 group 접근을 보장한다 (여러 계정이 번갈아 worktree 를
    # 만드는 배치). 기존 디렉터리의 mode 는 재설정하지 않는다 — metadata lossy 회피.
    if [ "$DRY_RUN" -eq 0 ] && [ "$PRINT_ONLY" -eq 0 ]; then
      priv_share_dir "$WORKTREE_PARENT"
    fi
  fi

  if [ -n "$EXISTING_BRANCH" ]; then
    # branch 가 이미 존재 — -b 없이 checkout.
    log_info "branch $NEW_BRANCH 이미 존재 — -b 생략, 기존 branch 체크아웃."
    run_or_dryrun "git -C $MAIN_WORKTREE_PATH worktree add $NEW_WORKTREE_PATH $NEW_BRANCH"
  else
    # 신규 branch 작성 — -b + base branch.
    run_or_dryrun "git -C $MAIN_WORKTREE_PATH worktree add $NEW_WORKTREE_PATH -b $NEW_BRANCH $BASE_REF"
  fi
fi

# ── agent-board 자율 부트스트랩 (AGENTS.md §22.15, v3.53.1) — best-effort, 종료 보고 앞 ─────
# 게시판은 사람이 아니라 AI 세션이 스스로 켠다: 보드가 없으면 만들고(모드 정책), 새 worktree 를 포함한
# main+linked worktree 의 .claude/settings.local.json 에 hook 을 병합하고, 이 세션을 등록한다 (멱등, 토큰 보존).
# 실패는 cycle-init 을 막지 않는다(WARN + rc) — 세션이 직접 `bash bin/board.sh bootstrap` 을 부르면 된다.
if [ "$DRY_RUN" -eq 0 ] && [ "$PRINT_ONLY" -eq 0 ]; then
  _CI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
  if [ -f "$_CI_DIR/board.sh" ]; then
    log_step "agent-board bootstrap (best-effort, §22.15)"
    if ( cd "$MAIN_WORKTREE_PATH" && bash "$_CI_DIR/board.sh" bootstrap --work "$FEATURE_ID" --worktree "$FEATURE_ID" --activate-in "$NEW_WORKTREE_PATH" ) >&2; then
      # 착수 이정표 (§22.15 이정표 모델 — persona 재량이 아니라 스크립트가 게시한다, v3.54.1). 실패는 stderr 한 줄, rc 0.
      ( cd "$MAIN_WORKTREE_PATH" && bash "$_CI_DIR/board.sh" milestone --kind status --work "$FEATURE_ID" \
          -m "착수 $FEATURE_ID — worktree $(basename "$NEW_WORKTREE_PATH") · branch $NEW_BRANCH · base $BASE_BRANCH" ) >/dev/null || true
    else
      _rc=$?; log_warn "agent-board bootstrap 실패(rc=$_rc) — 세션이 직접 'bash bin/board.sh bootstrap --work $FEATURE_ID' 를 실행하라 (§22.15)"
    fi
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
EOF

if [ "$DRY_RUN" -eq 1 ] || [ "$PRINT_ONLY" -eq 1 ]; then
  log_info "모의 실행 — worktree 생성·검증 완료를 뜻하지 않습니다. 실제 실행 후 해당 경로에서 계속합니다."
else
  cat >&2 <<EOF

다음 단계 (AI — AGENTS.md §13.2):
  본 세션에서 생성한 worktree 를 작업 경로로 사용해 위임된 작업을 계속합니다.

    cd $NEW_WORKTREE_PATH

  각 도구 호출의 cwd/workdir 를 위 경로로 지정합니다. 새 세션 시작이나 동일 범위
  재승인을 요구하지 않습니다. 검증·PR 준비가 끝나면 bin/cycle-finalize.sh 로 정리합니다.
EOF
fi

exit 0
