#!/usr/bin/env bash
# bin/cycle-finalize.sh
#
# Cycle cleanup helper for AGENTS.md §16.3 Step 6 (v3.9.0+).
# PR 머지 후 cleanup 6 sub-step 을 idempotent 하게 진행:
#   1. PR 상태 검증 + gh pr merge (옵션 — 이미 머지면 skip)
#   2. main worktree 식별 + git fetch + git pull --ff-only (main 항상 최신화)
#   3. 자기 worktree working tree clean 검증
#   4. cwd 이동 (자기 worktree 내부일 때만 — 자기 working dir remove 불가)
#   5. worktree remove + local branch delete + 원격 브랜치 best-effort 정리
#   6. §13.2.4 채택 consumer REGISTRY entry 이동 (옵션 — 부재 시 silent skip)
#
# 자동 진행 정책 (AGENTS.md §16.3 Step 6, v3.9.0+):
#   cycle 종료 시점 (verify-completion PASS + PR 생성 완료 + BLOCKED 신호 없음)
#   에서는 사람 명시 요청 없이 자동 진행. abnormal 경로 (PR not mergeable, dirty
#   working tree, non-fast-forward pull, branch -d unmerged) 는 자동 중단 +
#   사용자 결정 (silent -D / silent merge/rebase 금지). 외부 영향 행동:
#   gh pr merge / git pull / git worktree remove / git branch -d /
#   git push origin --delete (원격 브랜치 정리, best-effort).
#
# Usage:
#   bash bin/cycle-finalize.sh --pr <PR-NUMBER>
#     [--merge-strategy merge|squash|rebase]   (default: merge)
#     [--keep-worktree]                        (cleanup step 5 skip)
#     [--keep-branch]                          (local branch 보존)
#     [--target-worktree <path>]               (main 에서 named worktree 정리 — cwd 파생 SELF override)
#     [--branch <name>]                        (--target-worktree 대안: branch 로 worktree 지정)
#     [--dry-run]                              (mutation 명령 출력만)
#     [--help]
#
# Exit codes:
#   0 — all steps PASS or idempotent skip
#   1 — runtime failure (PR not mergeable, dirty working tree, etc.)
#   2 — usage error
#
# Requires: bash >= 4, git >= 2.20, gh (GitHub CLI). awk/grep/sed (POSIX).

set -euo pipefail

# ── Globals ───────────────────────────────────────────────────────────────
PR_NUMBER=""
MERGE_STRATEGY="merge"
KEEP_WORKTREE=0
KEEP_BRANCH=0
DRY_RUN=0
TARGET_WORKTREE=""   # v3.35.0 — main 에서 정리할 named worktree (cwd 파생 SELF override)
TARGET_BRANCH=""     # v3.35.0 — --target-worktree 대안: branch 로 worktree 지정

# ── Helpers ───────────────────────────────────────────────────────────────
log_info()  { printf "[cycle-finalize] %s\n"           "$*" >&2; }
log_step()  { printf "\n[cycle-finalize] === %s ===\n" "$*" >&2; }
log_warn()  { printf "[cycle-finalize] WARN: %s\n"     "$*" >&2; }
log_error() { printf "[cycle-finalize] ERROR: %s\n"    "$*" >&2; }
die()       { log_error "$@"; exit 1; }
usage_die() { log_error "$@"; printf "Run with --help for usage.\n" >&2; exit 2; }

run_or_dryrun() {
  # Execute or echo (dry-run) a shell command.
  if [ "$DRY_RUN" -eq 1 ]; then
    printf "[dry-run] %s\n" "$*" >&2
  else
    log_info "exec: $*"
    eval "$@"
  fi
}

show_help() {
  sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

# ── Argument parsing ──────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
  case "$1" in
    --pr)              PR_NUMBER="${2:-}"; shift 2 ;;
    --pr=*)            PR_NUMBER="${1#--pr=}"; shift ;;
    --merge-strategy)  MERGE_STRATEGY="${2:-}"; shift 2 ;;
    --merge-strategy=*) MERGE_STRATEGY="${1#--merge-strategy=}"; shift ;;
    --keep-worktree)   KEEP_WORKTREE=1; shift ;;
    --keep-branch)     KEEP_BRANCH=1; shift ;;
    --target-worktree) TARGET_WORKTREE="${2:-}"; shift 2 ;;
    --target-worktree=*) TARGET_WORKTREE="${1#--target-worktree=}"; shift ;;
    --branch)          TARGET_BRANCH="${2:-}"; shift 2 ;;
    --branch=*)        TARGET_BRANCH="${1#--branch=}"; shift ;;
    --dry-run)         DRY_RUN=1; shift ;;
    --help|-h)         show_help; exit 0 ;;
    *)                 usage_die "Unknown arg: $1" ;;
  esac
done

[ -n "$PR_NUMBER" ] || usage_die "--pr <N> required."

case "$MERGE_STRATEGY" in
  merge|squash|rebase) ;;
  *) usage_die "--merge-strategy must be one of: merge | squash | rebase (got: $MERGE_STRATEGY)" ;;
esac

# ── Pre-flight: git repo + tools ──────────────────────────────────────────
command -v git >/dev/null 2>&1 || die "git not found in PATH."
command -v gh  >/dev/null 2>&1 || die "gh (GitHub CLI) not found in PATH."

git rev-parse --git-dir >/dev/null 2>&1 || die "Not inside a git repository (cwd: $(pwd))."

SELF_WORKTREE_PATH="$(git rev-parse --show-toplevel)"
SELF_BRANCH="$(git -C "$SELF_WORKTREE_PATH" branch --show-current)"
[ -n "$SELF_BRANCH" ] || die "Detached HEAD detected in $SELF_WORKTREE_PATH. Cycle-finalize requires a named branch."

# main worktree 식별 — `git worktree list --porcelain` 의 첫 entry.
# 자기 자신이 main worktree 일 수도 있다 (그 경우 cleanup step 5 의 cwd 이동 불요).
MAIN_WORKTREE_PATH="$(git -C "$SELF_WORKTREE_PATH" worktree list --porcelain \
  | awk '/^worktree /{print substr($0,10); exit}')"
[ -n "$MAIN_WORKTREE_PATH" ] || die "main worktree path resolution failed (git worktree list returned empty)."

# ── target worktree override (v3.35.0) ────────────────────────────────────
# --target-worktree/--branch 지정 시 cwd 파생 SELF 대신 그 worktree 를 정리 대상으로 삼는다.
# main 에서 머지된 named worktree 를 정리할 때 사용 (self==main silent-skip 회피).
if [ -n "$TARGET_BRANCH" ] && [ -z "$TARGET_WORKTREE" ]; then
  # branch → worktree path 해석. prunable(디렉토리 소실 stale 엔트리)·locked 엔트리는
  # 제외하고, 같은 branch 가 복수 worktree 에 checkout 됐으면 모호하므로 거부한다
  # (잘못된 대상 정리 방지 — review META-CYCLE-043 backend HIGH).
  # porcelain record 단위 buffer 후 record 경계(빈 줄/EOF)에서 판정 —
  # prunable/locked 속성 줄은 branch 줄 *뒤*에 오므로 branch 줄 즉시 print 는 skip 을 놓친다.
  _tw_matches="$(git -C "$MAIN_WORKTREE_PATH" worktree list --porcelain \
    | awk -v b="refs/heads/$TARGET_BRANCH" '
        /^worktree /{wt=substr($0,10); br=""; skip=0}
        /^branch /{br=$2}
        /^prunable/{skip=1}
        /^locked/{skip=1}
        /^$/{if(br==b && skip==0 && wt!="") print wt; wt=""; br=""; skip=0}
        END{if(br==b && skip==0 && wt!="") print wt}')"
  _tw_count=$(printf '%s\n' "$_tw_matches" | grep -c . || true)
  if [ "$_tw_count" -eq 0 ]; then
    die "--branch '$TARGET_BRANCH' 에 해당하는 live worktree 를 찾지 못함 (prunable/locked 제외 — git worktree list 확인)."
  elif [ "$_tw_count" -gt 1 ]; then
    die "--branch '$TARGET_BRANCH' 가 복수 worktree 에 매칭됨 — --target-worktree <path> 로 대상을 명시하세요: $(printf '%s' "$_tw_matches" | tr '\n' ' ')"
  fi
  TARGET_WORKTREE="$_tw_matches"
fi
if [ -n "$TARGET_WORKTREE" ]; then
  TARGET_REAL="$(cd "$TARGET_WORKTREE" 2>/dev/null && pwd -P || true)"
  [ -n "$TARGET_REAL" ] || die "--target-worktree '$TARGET_WORKTREE' 디렉토리 부재."
  # 등록된 worktree 인지 검증 (임의 디렉토리 정리 방지)
  git -C "$MAIN_WORKTREE_PATH" worktree list --porcelain \
    | awk '/^worktree /{print substr($0,10)}' | grep -qxF "$TARGET_REAL" \
    || die "--target-worktree '$TARGET_REAL' 는 등록된 worktree 가 아님 (git worktree list 확인)."
  # main 정리 거부 (main 은 절대 삭제 대상 아님)
  if [ "$TARGET_REAL" = "$(cd "$MAIN_WORKTREE_PATH" && pwd -P)" ]; then
    die "--target-worktree 가 main worktree 를 가리킴 — main 은 정리 대상이 아닙니다."
  fi
  SELF_WORKTREE_PATH="$TARGET_REAL"
  SELF_BRANCH="$(git -C "$SELF_WORKTREE_PATH" branch --show-current)"
  [ -n "$SELF_BRANCH" ] || die "target worktree '$SELF_WORKTREE_PATH' 가 detached HEAD — named branch 필요."
  log_info "target-worktree 지정 — 정리 대상을 cwd 대신 $SELF_WORKTREE_PATH (branch: $SELF_BRANCH) 로 설정."
fi

log_info "self worktree:  $SELF_WORKTREE_PATH (branch: $SELF_BRANCH)"
log_info "main worktree:  $MAIN_WORKTREE_PATH"
log_info "PR:             #$PR_NUMBER"
log_info "merge strategy: $MERGE_STRATEGY"
log_info "dry-run:        $([ "$DRY_RUN" -eq 1 ] && echo yes || echo no)"

# Capture pre-cleanup HEAD for end-report.
MAIN_HEAD_BEFORE="$(git -C "$MAIN_WORKTREE_PATH" rev-parse --short HEAD 2>/dev/null || echo "unknown")"

# ── Step 1: PR 상태 검증 + gh pr merge (idempotent) ───────────────────────
log_step "Step 1: PR 상태 검증"

PR_STATE_JSON="$(gh pr view "$PR_NUMBER" --json state,mergeable,mergeStateStatus,headRefName,title 2>/dev/null || true)"
[ -n "$PR_STATE_JSON" ] || die "gh pr view #$PR_NUMBER failed (PR not found or auth issue)."

PR_STATE=$(printf "%s" "$PR_STATE_JSON" | sed -n 's/.*"state":"\([^"]*\)".*/\1/p')
PR_MERGEABLE=$(printf "%s" "$PR_STATE_JSON" | sed -n 's/.*"mergeable":"\([^"]*\)".*/\1/p')
PR_HEAD_REF=$(printf "%s" "$PR_STATE_JSON" | sed -n 's/.*"headRefName":"\([^"]*\)".*/\1/p')

log_info "PR state: $PR_STATE, mergeable: $PR_MERGEABLE, headRef: $PR_HEAD_REF"

case "$PR_STATE" in
  MERGED)
    log_info "PR #$PR_NUMBER already MERGED — skip merge step (idempotent)."
    ;;
  OPEN)
    if [ "$PR_MERGEABLE" != "MERGEABLE" ]; then
      die "PR #$PR_NUMBER not MERGEABLE (state=$PR_STATE, mergeable=$PR_MERGEABLE). Resolve conflicts first."
    fi
    # --delete-branch 미사용 (worktree-first 호환): gh 는 --delete-branch 시 기본
    # 브랜치로 로컬 체크아웃 전환 + 로컬/원격 브랜치 삭제를 시도하는데, 머지 대상
    # 브랜치가 worktree 에 checkout 된 상태(§13.2 worktree-first)면 전환/삭제가
    # 거부돼 매 cycle 실패한다. 로컬 브랜치는 Step 5b(git branch -d), 원격 브랜치는
    # Step 5c(best-effort push --delete)가 분리 처리한다.
    log_step "Step 1a: gh pr merge --$MERGE_STRATEGY (no --delete-branch — worktree-first 호환)"
    run_or_dryrun "gh pr merge $PR_NUMBER --$MERGE_STRATEGY"
    ;;
  CLOSED)
    die "PR #$PR_NUMBER is CLOSED (not merged). Cycle-finalize aborted."
    ;;
  *)
    die "Unknown PR state: $PR_STATE"
    ;;
esac

# ── Step 2: main 최신화 (필수 — 사용자 추가 요구 사항) ────────────────────
log_step "Step 2: main worktree 최신화 (git fetch + pull --ff-only)"

# fetch — 실패는 WARN, 사용자가 offline 일 수 있음.
if [ "$DRY_RUN" -eq 1 ]; then
  printf "[dry-run] git -C %s fetch origin\n" "$MAIN_WORKTREE_PATH" >&2
else
  if ! git -C "$MAIN_WORKTREE_PATH" fetch origin 2>&1; then
    log_warn "git fetch origin failed (network/auth?). 계속 진행하지만 main 이 stale 일 수 있습니다."
  fi
fi

# pull --ff-only — non-fast-forward 는 fail-loud.
if [ "$DRY_RUN" -eq 1 ]; then
  printf "[dry-run] git -C %s pull --ff-only origin main\n" "$MAIN_WORKTREE_PATH" >&2
else
  if ! git -C "$MAIN_WORKTREE_PATH" pull --ff-only origin main 2>&1; then
    die "git pull --ff-only origin main failed (non-fast-forward?). main 에 로컬 commit 이 있는지 확인 + manual resolve. 자동 merge/rebase 는 silent history rewriting 우려로 지원하지 않습니다."
  fi
fi

MAIN_HEAD_AFTER="$(git -C "$MAIN_WORKTREE_PATH" rev-parse --short HEAD 2>/dev/null || echo "unknown")"
log_info "main HEAD: $MAIN_HEAD_BEFORE → $MAIN_HEAD_AFTER"

# ── Step 3: 자기 worktree clean 검증 ─────────────────────────────────────
log_step "Step 3: 자기 worktree working tree clean 검증"

if [ "$KEEP_WORKTREE" -eq 1 ]; then
  log_info "--keep-worktree 지정 — Step 3~5 skip."
else
  if [ "$SELF_WORKTREE_PATH" = "$MAIN_WORKTREE_PATH" ]; then
    log_warn "self worktree == main worktree — worktree/branch 정리(Step 5)를 건너뜁니다."
    log_warn "  main 에서 cycle-finalize 를 실행하면 제거 대상 worktree 가 cwd 가 아니라, 머지된"
    log_warn "  feature worktree 가 정리되지 않고 stale 로 남습니다 (leftover 누적)."
    log_warn "  정리하려면 둘 중 하나로 재실행하세요:"
    log_warn "    (a) 그 worktree 안에서:  cd <worktree> && bash bin/cycle-finalize.sh --pr $PR_NUMBER …"
    log_warn "    (b) main 에서 대상 명시:  bash bin/cycle-finalize.sh --pr $PR_NUMBER --target-worktree <path>"
    KEEP_WORKTREE=1
    KEEP_BRANCH=1  # main branch 도 보존
  else
    DIRTY_COUNT=$(git -C "$SELF_WORKTREE_PATH" status --porcelain | wc -l | tr -d ' ')
    if [ "$DIRTY_COUNT" -gt 0 ]; then
      log_error "self worktree dirty ($DIRTY_COUNT changes). cleanup 중단."
      log_error "복구 옵션:"
      log_error "  - stash:        git -C $SELF_WORKTREE_PATH stash"
      log_error "  - discard:      git -C $SELF_WORKTREE_PATH restore . (사용자 명시, 데이터 손실)"
      log_error "  - commit:       git -C $SELF_WORKTREE_PATH commit -am '<msg>' (cycle 재진행 필요)"
      exit 1
    fi
    log_info "self worktree clean."
  fi
fi

# ── Step 4: cwd 이동 (자기 worktree 내부일 때만) ─────────────────────────
log_step "Step 4: cwd 이동 검증"

CURRENT_PWD="$(pwd -P)"
SELF_REAL="$(cd "$SELF_WORKTREE_PATH" && pwd -P)"
MAIN_REAL="$(cd "$MAIN_WORKTREE_PATH" && pwd -P)"

if [ "$KEEP_WORKTREE" -eq 0 ] && [ "${CURRENT_PWD#"$SELF_REAL"}" != "$CURRENT_PWD" ]; then
  log_info "cwd ($CURRENT_PWD) is inside self worktree — moving to main worktree before remove."
  # 본 script 의 후속 git 호출은 -C <path> 로 명시되어 있으므로 cd 자체는 cosmetic.
  # 단, worktree remove 가 cwd 를 deleted dir 로 두는 것을 방지하기 위해 명시 cd.
  cd "$MAIN_REAL"
fi

# ── Step 5: worktree remove + branch delete ──────────────────────────────
if [ "$KEEP_WORKTREE" -eq 0 ]; then
  log_step "Step 5a: git worktree remove $SELF_REAL"
  run_or_dryrun "git -C $MAIN_REAL worktree remove $SELF_REAL"
else
  log_info "Step 5a (worktree remove): skip (--keep-worktree)"
fi

if [ "$KEEP_BRANCH" -eq 0 ]; then
  log_step "Step 5b: git branch -d $SELF_BRANCH"
  # merged 검증 — branch -d 는 unmerged 시 실패. squash/rebase merge 인 경우 fail.
  if [ "$DRY_RUN" -eq 1 ]; then
    printf "[dry-run] git -C %s branch -d %s\n" "$MAIN_REAL" "$SELF_BRANCH" >&2
  else
    if ! git -C "$MAIN_REAL" branch -d "$SELF_BRANCH" 2>&1; then
      log_warn "git branch -d failed (unmerged?). squash/rebase merge 의 경우 정상 — force-delete 필요."
      log_warn "다음 명령을 사용자 확인 후 직접 실행 (silent force-delete 차단):"
      log_warn "  git -C $MAIN_REAL branch -D $SELF_BRANCH"
      log_warn "본 script 는 silent -D 를 진행하지 않습니다. cleanup 의 다른 step 은 완료된 상태."
    fi
  fi
else
  log_info "Step 5b (branch delete): skip (--keep-branch)"
fi

# ── Step 5c: 원격 브랜치 정리 (best-effort — --delete-branch decouple) ─────
# Step 1a 에서 --delete-branch 를 제거(worktree-first 호환)했으므로 원격 브랜치는
# 여기서 best-effort 로 정리한다. 파괴적 원격 op 라 가드를 좁힌다:
#   (a) KEEP_BRANCH=0,
#   (b) PR head ref == 방금 finalize 한 로컬 브랜치(SELF_BRANCH) — PR 재타깃/오인자
#       시 무관 원격 브랜치 오삭제 방지 (Step 5b 와 동일 대상만 삭제),
#   (c) leading-dash ref 거부 — git 옵션 오해석 방지,
#   (d) main/master backstop.
# 삭제 결과는 3분기로 관측: 성공 / 이미 없음(정상) / 실재 실패(네트워크·auth, WARN).
# 어느 경우도 cycle 을 중단하지 않는다 (로컬 정리는 Step 5b 가 이미 완료).
if [ "$KEEP_BRANCH" -eq 0 ] \
   && [ -n "$PR_HEAD_REF" ] \
   && [ "$PR_HEAD_REF" = "$SELF_BRANCH" ] \
   && [ "${PR_HEAD_REF#-}" = "$PR_HEAD_REF" ] \
   && [ "$PR_HEAD_REF" != "main" ] && [ "$PR_HEAD_REF" != "master" ]; then
  log_step "Step 5c: git push origin --delete $PR_HEAD_REF (원격 브랜치 정리, best-effort)"
  if [ "$DRY_RUN" -eq 1 ]; then
    printf "[dry-run] git -C %s push origin --delete %s\n" "$MAIN_REAL" "$PR_HEAD_REF" >&2
  else
    if push_err="$(git -C "$MAIN_REAL" push origin --delete "$PR_HEAD_REF" 2>&1)"; then
      log_info "원격 브랜치 '$PR_HEAD_REF' 삭제 완료."
    elif printf '%s' "$push_err" | grep -qiE 'remote ref does not exist|does not exist'; then
      log_info "원격 브랜치 '$PR_HEAD_REF' 이미 없음 (GitHub auto-delete 등) — 정상."
    else
      log_warn "원격 브랜치 '$PR_HEAD_REF' 삭제 실패 (네트워크/auth?): $push_err. 무시하고 계속 — 다른 cleanup step 은 완료."
    fi
  fi
else
  log_info "Step 5c (원격 브랜치 정리): skip (--keep-branch / head ref 미상 / SELF_BRANCH 불일치 / main)"
fi

# ── Step 6: REGISTRY entry 이동 (옵션) ───────────────────────────────────
log_step "Step 6: §13.2.4 REGISTRY entry 이동 (옵션)"

# project_root = wrapper of policy_root (= MAIN_REAL).
# ai_delegated_dev_template standard layout: <wrapper>/repo = policy_root.
PROJECT_ROOT="$(dirname "$MAIN_REAL")"
REGISTRY_PATH="$PROJECT_ROOT/worktrees/REGISTRY.md"
SESSIONS_LOG_PATH="$MAIN_REAL/meta/SESSIONS_LOG.md"

if [ ! -f "$REGISTRY_PATH" ]; then
  log_info "REGISTRY.md 부재 (consumer §13.2.4 미채택) — skip."
else
  log_info "REGISTRY.md 발견: $REGISTRY_PATH"
  log_info "본 script 는 REGISTRY entry 의 자동 이동을 수행하지 않습니다 (각 consumer 의 entry format 차이로 인한 수정 위험)."
  log_info "다음을 수동으로 진행하세요:"
  log_info "  1. $REGISTRY_PATH 에서 '## 활성 세션' 의 자기 entry (worktree_path=$SELF_REAL) 를 '## 종료 세션' 으로 이동"
  if [ -f "$SESSIONS_LOG_PATH" ]; then
    log_info "  2. $SESSIONS_LOG_PATH 에 종료 timestamp + PR #$PR_NUMBER append"
  fi
fi

# ── 종료 보고 ─────────────────────────────────────────────────────────────
log_step "cycle-finalize 완료"
cat >&2 <<EOF

종료 보고:
  PR:                 #$PR_NUMBER ($MERGE_STRATEGY)
  main HEAD:          $MAIN_HEAD_BEFORE → $MAIN_HEAD_AFTER
  removed worktree:   $([ "$KEEP_WORKTREE" -eq 0 ] && echo "$SELF_REAL" || echo "(kept)")
  deleted branch:     $([ "$KEEP_BRANCH" -eq 0 ] && echo "$SELF_BRANCH" || echo "(kept)")
  REGISTRY hint:      $([ -f "$REGISTRY_PATH" ] && echo "manual entry move required" || echo "(not adopted)")
  dry-run:            $([ "$DRY_RUN" -eq 1 ] && echo yes || echo no)

다음 단계:
  - REGISTRY entry 가 있다면 수동 이동 (위 안내 참조)
  - 신규 cycle 진입: bash bin/cycle-init.sh --feature <next-feature-id>
EOF

exit 0
