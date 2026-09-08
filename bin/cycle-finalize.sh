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
#     [--keep-worktree]                        (worktree + local/remote branch 보존; step 5 skip)
#     [--keep-branch]                          (worktree 제거, local/remote branch 보존)
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

# ── 권한 어댑터 로드 (§13.2.10) ───────────────────────────────────────────
# git·gh 는 **언제나 원 호출자로** 실행한다 (승격하면 PATH 교체로 사용자 로컬 설치 gh 를
# 잃고, main worktree 산출물이 root 소유로 남는다). 승격은 Step 6 의 공유 운영 파일
# 접근권 진단·복구에만 쓴다.
# shellcheck source=lib/privilege.sh
. "$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)/lib/privilege.sh"

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

# ── Step 0b: host-local merge mutex (META-0027, parallel-work-structure ITEM-07) ──
# 전 worktree 가 공유하는 git 공용 디렉터리(.git) 안의 락으로 머지 구간(Step 1~2)을
# 직렬화한다 — 두 세션이 동시에 finalize 해도 순차 머지되고, 두 번째는 락 대기 후
# 최신 main 기준으로 재검증(신선도 게이트+CLEAN 재폴링)한다. 락 파일이 working tree
# 밖(공용 .git)이라 clean 검증·gitignore 와 무간섭·전 worktree 공유. host-local 이므로
# 원격/CI 발 머지는 보호하지 못한다(문서화된 한계 — 본 호스트는 전 작업자 동일 호스트).
# gh 구버전(<2.57)엔 `gh pr update-branch` 미존재(2026-07-11 라이브 실증) — REST API 폴백.
gh_update_branch() {  # $1=PR번호. 성공 0 / 실패 비0(호출부가 중단)
  gh pr update-branch "$1" 2>/dev/null \
    || gh api --method PUT "repos/{owner}/{repo}/pulls/$1/update-branch" >/dev/null 2>&1
}

MERGE_LOCK_TIMEOUT_SEC="${MERGE_LOCK_TIMEOUT_SEC:-900}"
MERGE_LOCK_FILE="$(git rev-parse --path-format=absolute --git-common-dir)/.merge.lock"
log_step "Step 0b: merge mutex 획득 (flock, 최대 ${MERGE_LOCK_TIMEOUT_SEC}s)"
exec 9>"$MERGE_LOCK_FILE" || die "merge lock 파일 열기 실패: $MERGE_LOCK_FILE"
if ! flock -n 9 2>/dev/null; then
  log_info "다른 세션이 머지 진행 중 — 락 대기 (최대 ${MERGE_LOCK_TIMEOUT_SEC}s)…"
  flock -w "$MERGE_LOCK_TIMEOUT_SEC" 9 \
    || die "merge mutex 획득 실패 (${MERGE_LOCK_TIMEOUT_SEC}s 초과) — 다른 finalize 가 장기 점유 중. 그 세션 종료/이상 여부 확인 후 재시도 (락: $MERGE_LOCK_FILE)"
fi
log_info "merge mutex 획득 — 머지 구간(Step 1~2) 직렬화"
# 모든 die/exit 경로에서 락 확정 해제 — detached auto-gc 가 fd 9 OFD 사본을 물고
# 장수해도 flock -u 는 OFD 락을 즉시 푼다 (패널 MINOR-1).
trap 'flock -u 9 2>/dev/null || true' EXIT

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
    # ── Step 1a-0: 신선도 hard gate + mergeStateStatus CLEAN 재폴링 (META-0027) ──
    # 락 안에서 최신 main 기준 재검증: behind >= MERGE_BEHIND_GATE(기본 20) 이면 자동
    # update-branch 후 CI 재확인을 강제(§13.2.5 의 '권유'를 게이트로 격상). 어떤 경우든
    # CLEAN 확인 후에만 머지(낡은 base 로 통과한 테스트로 머지하는 semantic drift 차단
    # — Not Rocket Science Rule, RESEARCH W-002). abnormal(BLOCKED/DIRTY)은 §16.3
    # Step 6 대로 자동 중단. textual clean != semantic safe — 기존 diff/테스트 게이트는
    # 그대로 유지되며 본 게이트는 그 위의 추가 방어선이다(W-008).
    MERGE_BEHIND_GATE="${MERGE_BEHIND_GATE:-20}"
    MERGE_CLEAN_TIMEOUT_SEC="${MERGE_CLEAN_TIMEOUT_SEC:-600}"
    _verified_head=""
    if [ "$DRY_RUN" -eq 1 ]; then
      printf "[dry-run] 신선도 게이트: behind>=%s 이면 gh pr update-branch %s → base 포함/CLEAN 확인 후 merge\n" \
        "$MERGE_BEHIND_GATE" "$PR_NUMBER" >&2
    else
      git fetch origin >/dev/null 2>&1 || die "git fetch 실패 — 최신 base를 검증할 수 없어 머지 중단."
      _base_commit=$(git rev-parse --verify refs/remotes/origin/main) \
        || die "origin/main 부재 — 머지 base를 검증할 수 없음."
      _behind=$(git rev-list --count "refs/remotes/origin/${PR_HEAD_REF}..origin/main") \
        || die "PR head ref 부재 — 신선도를 검증할 수 없어 머지 중단."
      _refresh_base=""
      if [ "$_behind" -ge "$MERGE_BEHIND_GATE" ]; then
        log_info "신선도 게이트: behind=${_behind} (>= ${MERGE_BEHIND_GATE}) — update-branch 강제"
        _refresh_base="$_base_commit"
        gh_update_branch "$PR_NUMBER" || die "update-branch 실패 — 최신 base 반영을 확인할 수 없어 머지 중단."
      fi
      _deadline=$(( $(date +%s) + MERGE_CLEAN_TIMEOUT_SEC ))
      while :; do
        _poll=$(gh pr view "$PR_NUMBER" --json state,mergeStateStatus,headRefOid \
          --jq '"\(.state):\(.mergeStateStatus):\(.headRefOid)"' 2>/dev/null || echo "VIEWFAIL:UNKNOWN:")
        IFS=: read -r _polled_state _merge_state _polled_head <<< "$_poll"
        _mss="${_polled_state}:${_merge_state}"
        case "$_mss" in
          MERGED:*) log_info "폴링 중 PR 이 외부에서 머지됨 — idempotent 합류"; break ;;
          OPEN:CLEAN|OPEN:HAS_HOOKS)
            [[ "$_polled_head" =~ ^[0-9a-f]{40,64}$ ]] || die "PR head SHA 미확인 — 머지 중단."
            if [ -n "$_refresh_base" ]; then
              git fetch origin >/dev/null 2>&1 || die "update 후 git fetch 실패 — 머지 중단."
              if ! git merge-base --is-ancestor "$_refresh_base" "$_polled_head" 2>/dev/null; then
                log_info "update 요청의 base가 PR head에 아직 없음 — 반영 대기"
              else
                _verified_head="$_polled_head"
                log_info "요청 base 포함 + mergeStateStatus=${_merge_state} — 머지 진행"
                break
              fi
            else
              _verified_head="$_polled_head"
              log_info "mergeStateStatus=${_merge_state} — 머지 진행"
              break
            fi ;;
          OPEN:BEHIND)
            if [ -z "$_refresh_base" ]; then
              git fetch origin >/dev/null 2>&1 || die "BEHIND base 갱신 실패 — 머지 중단."
              _refresh_base=$(git rev-parse --verify refs/remotes/origin/main) || die "origin/main 부재."
              gh_update_branch "$PR_NUMBER" || die "update-branch 실패 — 머지 중단."
            fi ;;
          *:BLOCKED|*:DIRTY|CLOSED:*)
            die "PR #$PR_NUMBER mergeStateStatus=${_merge_state}, state=${_polled_state} — 원인 해소 후 재시도." ;;
          VIEWFAIL:*) log_warn "gh pr view 실패 — 재폴링" ;;
          *) : ;;
        esac
        [ "$(date +%s)" -lt "$_deadline" ] || die "PR #$PR_NUMBER base/CLEAN 대기 timeout(${MERGE_CLEAN_TIMEOUT_SEC}s, 마지막 상태=$_mss)."
        sleep 15
      done
    fi
    # --delete-branch 미사용 (worktree-first 호환): gh 는 --delete-branch 시 기본
    # 브랜치로 로컬 체크아웃 전환 + 로컬/원격 브랜치 삭제를 시도하는데, 머지 대상
    # 브랜치가 worktree 에 checkout 된 상태(§13.2 worktree-first)면 전환/삭제가
    # 거부돼 매 cycle 실패한다. 로컬 브랜치는 Step 5b(git branch -d), 원격 브랜치는
    # Step 5c(best-effort push --delete)가 분리 처리한다.
    # 폴링 중 외부 머지 합류 케이스 — merge 호출 전 최종 재확인 (idempotent)
    _final_state=$(gh pr view "$PR_NUMBER" --json state --jq .state 2>/dev/null || echo OPEN)
    if [ "$_final_state" = "MERGED" ]; then
      log_info "PR #$PR_NUMBER 이미 MERGED — merge 호출 skip (idempotent)."
    else
      log_step "Step 1a: gh pr merge --$MERGE_STRATEGY (no --delete-branch — worktree-first 호환)"
      run_or_dryrun "gh pr merge $PR_NUMBER --$MERGE_STRATEGY${_verified_head:+ --match-head-commit $_verified_head}"
    fi
    ;;
  CLOSED)
    die "PR #$PR_NUMBER is CLOSED (not merged). Cycle-finalize aborted."
    ;;
  *)
    die "Unknown PR state: $PR_STATE"
    ;;
esac

# ── agent-board 완료 이정표 (§22.15, v3.54.1) — best-effort, 절대 막지 않음 ──────────
# 머지가 확정된 시점에 «완료» status 를 게시한다. Codex/Claude native id 로 자기 sid 를 유추(board.sh milestone).
_CF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
_CF_SID=""
_CF_LEGACY_BINDING=0
if [ -n "${CODEX_THREAD_ID:-}" ]; then
  _CF_SID="codex:$(id -un):$CODEX_THREAD_ID"
elif [ -n "${CLAUDE_CODE_SESSION_ID:-}" ]; then
  _CF_SID="claude:$(id -un):$CLAUDE_CODE_SESSION_ID"
elif [ -n "${AGENT_BOARD_SID:-}" ] && [ -n "${AGENT_BOARD_TOKEN:-}" ] && [ -f "$_CF_DIR/lib/board_fs.py" ]; then
  # Legacy Claude hooks export only SID/token. Verify that existing binding.
  if _CF_SID=$(python3 -B - "$_CF_DIR/lib/board_fs.py" "$MAIN_WORKTREE_PATH" 2>/dev/null <<'PY'
import importlib.util
import os
import sys

root = None
try:
    spec = importlib.util.spec_from_file_location("cycle_board", sys.argv[1])
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    sid = os.environ["AGENT_BOARD_SID"]
    _, root, _, log = core.open_board(sys.argv[2], sid)
    if root is None:
        raise ValueError("no board")
    core.authz_session(root, sid, os.environ["AGENT_BOARD_TOKEN"], log,
                       ("active", "muted", "done", "suspended", "ended"))
    print(sid)
except Exception:
    sys.exit(1)
finally:
    if root is not None:
        root.close()
PY
  ); then
    _CF_LEGACY_BINDING=1
  else
    _CF_SID=""
  fi
fi
if [ "$DRY_RUN" -eq 0 ] && [ -f "$_CF_DIR/board.sh" ]; then
  if [ -z "$_CF_SID" ]; then
    log_warn "agent-board 자동 완료 생략 — native session id 미확인, 검증된 SID/token 바인딩 없음; 다른 세션 SID를 사용하지 않습니다."
  else
    _pr_title="$(printf "%s" "$PR_STATE_JSON" | python3 -c 'import json,sys
try: print((json.load(sys.stdin).get("title") or "")[:120])
except Exception: print("")' 2>/dev/null)"
    ( export AGENT_BOARD_SID="$_CF_SID"; unset AGENT_BOARD_TOKEN
      cd "$MAIN_WORKTREE_PATH" && bash "$_CF_DIR/board.sh" milestone --kind status \
      -m "완료 PR #$PR_NUMBER ($SELF_BRANCH) merged${_pr_title:+ — $_pr_title}" ) >/dev/null || true
  fi
fi

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

# merge mutex 해제 — 머지 구간(Step 1~2)만 직렬화, worktree 정리(Step 3~)는 병렬 허용 (META-0027)
flock -u 9 2>/dev/null || true
log_info "merge mutex 해제 — 이후 단계는 락 밖"

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
WORKTREE_RESULT="kept: $SELF_REAL"
if [ "$KEEP_WORKTREE" -eq 0 ]; then
  log_step "Step 5a: git worktree remove $SELF_REAL"
  run_or_dryrun "git -C $MAIN_REAL worktree remove $SELF_REAL"
  if [ "$DRY_RUN" -eq 1 ]; then
    WORKTREE_RESULT="dry-run: would remove $SELF_REAL"
  else
    WORKTREE_RESULT="removed: $SELF_REAL"
  fi
else
  log_info "Step 5a (worktree remove): skip (--keep-worktree)"
fi

BRANCH_KEEP_REASON=""
if [ "$KEEP_WORKTREE" -eq 1 ]; then
  BRANCH_KEEP_REASON="--keep-worktree"
elif [ "$KEEP_BRANCH" -eq 1 ]; then
  BRANCH_KEEP_REASON="--keep-branch"
fi

LOCAL_BRANCH_RESULT="kept ($BRANCH_KEEP_REASON): $SELF_BRANCH"
if [ -z "$BRANCH_KEEP_REASON" ]; then
  log_step "Step 5b: git branch -d $SELF_BRANCH"
  # merged 검증 — branch -d 는 unmerged 시 실패. squash/rebase merge 인 경우 fail.
  if [ "$DRY_RUN" -eq 1 ]; then
    printf "[dry-run] git -C %s branch -d %s\n" "$MAIN_REAL" "$SELF_BRANCH" >&2
    LOCAL_BRANCH_RESULT="dry-run: would delete $SELF_BRANCH"
  else
    if ! git -C "$MAIN_REAL" branch -d "$SELF_BRANCH" 2>&1; then
      LOCAL_BRANCH_RESULT="retained (delete failed): $SELF_BRANCH"
      log_warn "git branch -d failed (unmerged?). squash/rebase merge 의 경우 정상 — force-delete 필요."
      log_warn "다음 명령을 사용자 확인 후 직접 실행 (silent force-delete 차단):"
      log_warn "  git -C $MAIN_REAL branch -D $SELF_BRANCH"
      log_warn "본 script 는 silent -D 를 진행하지 않습니다. cleanup 의 다른 step 은 완료된 상태."
    else
      LOCAL_BRANCH_RESULT="deleted: $SELF_BRANCH"
    fi
  fi
else
  log_info "Step 5b (branch delete): skip ($BRANCH_KEEP_REASON)"
fi

# ── Step 5c: 원격 브랜치 정리 (best-effort — --delete-branch decouple) ─────
# Step 1a 에서 --delete-branch 를 제거(worktree-first 호환)했으므로 원격 브랜치는
# 여기서 best-effort 로 정리한다. 파괴적 원격 op 라 가드를 좁힌다:
#   (a) KEEP_WORKTREE=0 이고 KEEP_BRANCH=0,
#   (b) PR head ref == 방금 finalize 한 로컬 브랜치(SELF_BRANCH) — PR 재타깃/오인자
#       시 무관 원격 브랜치 오삭제 방지 (Step 5b 와 동일 대상만 삭제),
#   (c) leading-dash ref 거부 — git 옵션 오해석 방지,
#   (d) main/master backstop.
# 삭제 결과는 3분기로 관측: 성공 / 이미 없음(정상) / 실재 실패(네트워크·auth, WARN).
# 어느 경우도 cycle 을 중단하지 않는다 (로컬 정리는 Step 5b 가 이미 완료).
REMOTE_BRANCH_RESULT="skipped (head ref unknown, mismatched or protected): ${PR_HEAD_REF:-unknown}"
if [ -z "$BRANCH_KEEP_REASON" ] \
   && [ -n "$PR_HEAD_REF" ] \
   && [ "$PR_HEAD_REF" = "$SELF_BRANCH" ] \
   && [ "${PR_HEAD_REF#-}" = "$PR_HEAD_REF" ] \
   && [ "$PR_HEAD_REF" != "main" ] && [ "$PR_HEAD_REF" != "master" ]; then
  log_step "Step 5c: git push origin --delete $PR_HEAD_REF (원격 브랜치 정리, best-effort)"
  if [ "$DRY_RUN" -eq 1 ]; then
    printf "[dry-run] git -C %s push origin --delete %s\n" "$MAIN_REAL" "$PR_HEAD_REF" >&2
    REMOTE_BRANCH_RESULT="dry-run: would delete $PR_HEAD_REF"
  else
    if push_err="$(git -C "$MAIN_REAL" push origin --delete "$PR_HEAD_REF" 2>&1)"; then
      REMOTE_BRANCH_RESULT="deleted: $PR_HEAD_REF"
      log_info "원격 브랜치 '$PR_HEAD_REF' 삭제 완료."
    elif printf '%s' "$push_err" | grep -qiE 'remote ref does not exist|does not exist'; then
      REMOTE_BRANCH_RESULT="already absent: $PR_HEAD_REF"
      log_info "원격 브랜치 '$PR_HEAD_REF' 이미 없음 (GitHub auto-delete 등) — 정상."
    else
      REMOTE_BRANCH_RESULT="delete failed (state unconfirmed): $PR_HEAD_REF"
      log_warn "원격 브랜치 '$PR_HEAD_REF' 삭제 실패 (네트워크/auth?): $push_err. 무시하고 계속 — 다른 cleanup step 은 완료."
    fi
  fi
else
  if [ -n "$BRANCH_KEEP_REASON" ]; then
    REMOTE_BRANCH_RESULT="skipped ($BRANCH_KEEP_REASON): ${PR_HEAD_REF:-unknown}"
  fi
  log_info "Step 5c (원격 브랜치 정리): $REMOTE_BRANCH_RESULT"
fi

# ── Step 6: REGISTRY entry 이동 (옵션) ───────────────────────────────────
log_step "Step 6: §13.2.4 REGISTRY entry 이동 (옵션)"

# project_root = wrapper of policy_root (= MAIN_REAL).
# ai_delegated_dev_template standard layout: <wrapper>/repo = policy_root.
PROJECT_ROOT="$(dirname "$MAIN_REAL")"
REGISTRY_PATH="$PROJECT_ROOT/worktrees/REGISTRY.md"
SESSIONS_LOG_PATH="$MAIN_REAL/meta/SESSIONS_LOG.md"

REGISTRY_RESULT="(not adopted)"
[ ! -f "$REGISTRY_PATH" ] || REGISTRY_RESULT="manual entry move required"
if [ "$DRY_RUN" -eq 1 ]; then
  REGISTRY_RESULT="dry-run: unchanged"
  log_info "[dry-run] REGISTRY entry 이동 및 권한 변경 생략"
else
# §13.2.10: REGISTRY 가 다른 계정 소유 0600 으로 굳어 있으면 접근권을 먼저 복구한다
# (정상 상태면 sudo 호출 0회). 복구 후에도 접근 불가면 아래에서 정직하게 갈라 보고한다.
if [ -e "$REGISTRY_PATH" ]; then
  priv_ensure_writable "$REGISTRY_PATH" || true
  priv_ensure_writable "$REGISTRY_PATH.lock" || true
fi

REG_REASON="$(priv_access_reason "$REGISTRY_PATH")"
if [ -e "$REGISTRY_PATH" ] && [ "$REG_REASON" != "ok" ]; then
  # 권한 실패를 스키마 불일치로 오진하지 않는다. 아래 grep 은 읽지 못하면 조용히 false 를
  # 내므로, 그대로 두면 "비-META-0029 형식" 안내로 새어나가 사용자가 있지도 않은 포맷
  # 차이를 뒤지게 된다 (2026-07-27 라이브 오진 실증). 읽기·쓰기를 모두 본다 — 0664
  # 정규화 이후 남는 실패는 대개 rewrite 용 **쓰기** 거부다.
  log_warn "REGISTRY.md 접근 불가($REG_REASON) — entry 이동 skip: $REGISTRY_PATH (실행자: $(id -un))"
  log_warn "  passwordless sudo 가용성을 확인하세요 (PRIV_NO_SUDO 미설정 여부 포함). 승격되면 자동 복구됩니다 (§13.2.10)."
  log_warn "  수동 이동: '## Active' 의 '### $SELF_BRANCH' 블록을 '## Closed' 로"
elif [ ! -f "$REGISTRY_PATH" ]; then
  log_info "REGISTRY.md 부재 (consumer §13.2.4 미채택) — skip."
elif grep -qxF '## Active' "$REGISTRY_PATH" && grep -qxF '## Closed' "$REGISTRY_PATH"; then
  # META-0029 스키마(## Active/## Closed + `### <branch>` 블록) — 자기 entry 자동 이동.
  # cycle-init 과 동일 lock 공유(병렬 직렬화) · mktemp→검증→mv 원자 rewrite · 실패는 경고만
  # (§18.8 패널 REV-20260711T051835 MAJOR-3 반영 — 닫는 쪽 없는 라이프사이클/안내문 스키마 불일치 해소).
  log_info "REGISTRY.md 발견 (META-0029 스키마): $REGISTRY_PATH — entry 자동 이동 (Active → Closed)"
  REG_TMP=""
  if exec 8>"$REGISTRY_PATH.lock" && flock -w 10 8 \
     && REG_TMP="$(mktemp "$REGISTRY_PATH.XXXXXX")" \
     && awk -v br="### $SELF_BRANCH" \
            -v closed="- closed_at: $(date +%Y-%m-%dT%H:%M:%S%z) (PR #${PR_NUMBER:-?})" '
          /^## Active$/ {act=1; print; next}
          /^## Closed$/ {
            act=0; print
            if (n > 0) { print ""; for (i=1;i<=n;i++) print buf[i]; print closed }
            next
          }
          act && $0 == br {cap=1; n=1; buf[1]=$0; next}
          cap && (/^### / || /^## /) {cap=0}
          cap {n++; buf[n]=$0; next}
          {print}
        ' "$REGISTRY_PATH" >"$REG_TMP" \
     && ! awk '/^## Active$/{a=1;next} /^## Closed$/{a=0} a' "$REG_TMP" | grep -qxF "### $SELF_BRANCH" \
     && priv_replace_preserving_mode "$REG_TMP" "$REGISTRY_PATH"; then
    # §13.2.10: `mv` 대신 원본 inode 유지 write-through — mode·uid/gid·ACL 보존
    # (cycle-init 과 동일 축. `chmod` 되감기는 ACL named entry 를 복원하지 못한다).
    REGISTRY_RESULT="automatic entry close completed"
    log_info "REGISTRY entry 이동 완료: $SELF_BRANCH → ## Closed"
  else
    rm -f "${REG_TMP:-/nonexistent}" 2>/dev/null || true
    # write-through 는 원본 mode 를 건드리지 않으므로 실패 분기에서 되감을 것이 없다
    # (mv 방식일 때 필요했던 보정 — write-through 전환으로 소멸).
    _reg_reason_post="$(priv_access_reason "$REGISTRY_PATH")"
    if [ "$_reg_reason_post" != "ok" ]; then
      log_warn "REGISTRY entry 자동 이동 실패: 권한($_reg_reason_post) — $REGISTRY_PATH (실행자: $(id -un))"
    else
      log_warn "REGISTRY entry 자동 이동 실패(또는 entry 부재) — 수동 이동 가능: '## Active' 의 '### $SELF_BRANCH' 블록을 '## Closed' 로"
    fi
  fi
  { exec 8>&-; } 2>/dev/null || true
else
  log_info "REGISTRY.md 발견 (비-META-0029 형식): $REGISTRY_PATH"
  log_info "본 script 는 이 format 의 자동 이동을 수행하지 않습니다 (consumer entry format 차이로 인한 수정 위험)."
  log_info "다음을 수동으로 진행하세요:"
  log_info "  1. $REGISTRY_PATH 에서 활성 구간의 자기 entry (branch=$SELF_BRANCH, worktree=$SELF_REAL) 를 종료 구간으로 이동"
  if [ -f "$SESSIONS_LOG_PATH" ]; then
    log_info "  2. $SESSIONS_LOG_PATH 에 종료 timestamp + PR #$PR_NUMBER append"
  fi
fi

fi

# ── 종료 보고 ─────────────────────────────────────────────────────────────
# ── agent-board done (§22.15 «완료 세션은 board.sh done», v3.54.1) — best-effort ────────────
# 정리까지 끝난 세션은 게시판 주입을 더 받지 않는다. 같은 세션에 새 일이 오면 `board.sh reactivate` 로 되살린다.
_CF_DONE_BOARD="$MAIN_REAL/bin/board.sh"
# Prefer main after cleanup; an externally installed helper may also survive.
if [ ! -f "$_CF_DONE_BOARD" ] && [ -f "$_CF_DIR/board.sh" ]; then
  _CF_DONE_BOARD="$_CF_DIR/board.sh"
fi
if [ "$DRY_RUN" -eq 0 ] && [ -f "$_CF_DONE_BOARD" ] && [ -n "$_CF_SID" ]; then
  ( [ "$_CF_LEGACY_BINDING" -eq 1 ] || unset AGENT_BOARD_TOKEN
    cd "$MAIN_REAL" && bash "$_CF_DONE_BOARD" done --sid "$_CF_SID" ) >/dev/null 2>&1 \
    || log_warn "agent-board done 실패 — 세션이 직접 'bash bin/board.sh done --sid $_CF_SID' (§22.15)"
fi

log_step "cycle-finalize 완료"
cat >&2 <<EOF

종료 보고:
  PR:                 #$PR_NUMBER ($MERGE_STRATEGY)
  main HEAD:          $MAIN_HEAD_BEFORE → $MAIN_HEAD_AFTER
  worktree cleanup:   $WORKTREE_RESULT
  local branch:       $LOCAL_BRANCH_RESULT
  remote branch:      $REMOTE_BRANCH_RESULT
  REGISTRY hint:      $REGISTRY_RESULT
  dry-run:            $([ "$DRY_RUN" -eq 1 ] && echo yes || echo no)

다음 단계:
  - REGISTRY: $REGISTRY_RESULT (위 실행 결과 참조)
  - 신규 cycle 진입: bash bin/cycle-init.sh --feature <next-feature-id>
EOF

exit 0
