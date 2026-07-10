#!/usr/bin/env bash
# =============================================================================
# setup-git-parallel.sh — 병렬 AI 작업용 git 장치 설정 (멱등).
# (parallel-work-structure ITEM-03, META-0024 — AGENTS.md §13.1 2026-07-11 개정)
#
# 설정 항목:
#   1. rerere — 작업자 계정(root·claude·claude-corp + 현재 계정) git 전역:
#      rerere.enabled=true + rerere.autoUpdate=true (동일 충돌 재발 시 자동 재해소)
#   2. append-doc merge driver — 이 repo(clone-로컬, 전 worktree 공유 common config):
#      merge.append-doc.driver = bin/merge-append-doc.sh %O %A %B %L %P
#      (.gitattributes 의 path-scoped merge=append-doc 3종이 사용. driver 등록은
#       clone 마다 필요 — 세션/클론 시작 시 본 스크립트 1회 실행, AGENTS.md §13.1)
#
# 사용: bin/setup-git-parallel.sh [--accounts "a b c"] (기본: root claude claude-corp)
# 재실행 안전(멱등). 타 계정 설정은 sudo -H -u <계정> 가능할 때만(불가 시 경고 후 skip).
# =============================================================================
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

log() { printf '[setup-git-parallel] %s\n' "$*" >&2; }

ACCOUNTS="root claude claude-corp"
if [ $# -gt 0 ]; then
  case "$1" in
    --accounts) ACCOUNTS="${2:?--accounts 인자 필요}" ;;
    *) printf '[setup-git-parallel] ERROR: 알 수 없는 인자: %s\n' "$1" >&2; exit 2 ;;
  esac
fi
OK_COUNT=0; SKIP_COUNT=0

ME="$(id -un)"

set_rerere() {  # $1=계정
  local acct="$1"
  if [ "$acct" = "$ME" ]; then
    git config --global rerere.enabled true
    git config --global rerere.autoUpdate true
    log "rerere 활성화: $acct (현재 계정)"; OK_COUNT=$((OK_COUNT+1))
  elif sudo -n -H -u "$acct" true 2>/dev/null; then
    sudo -n -H -u "$acct" git config --global rerere.enabled true
    sudo -n -H -u "$acct" git config --global rerere.autoUpdate true
    log "rerere 활성화: $acct (sudo)"; OK_COUNT=$((OK_COUNT+1))
  else
    log "경고: $acct 계정 설정 불가(sudo 불가) — 해당 계정에서 본 스크립트 재실행 필요"
    SKIP_COUNT=$((SKIP_COUNT+1))
  fi
}

for a in $ACCOUNTS; do
  if id -u "$a" >/dev/null 2>&1; then set_rerere "$a"; else log "경고: 계정 없음 skip: $a"; SKIP_COUNT=$((SKIP_COUNT+1)); fi
done

# merge driver 등록 — clone-로컬(common config: 전 worktree 공유)
git -C "$REPO_ROOT" config merge.append-doc.name "append-only 문서 말미 블록 병합 (META-0024)"
git -C "$REPO_ROOT" config merge.append-doc.driver 'bin/merge-append-doc.sh %O %A %B %L %P'
log "merge driver 등록: merge.append-doc → bin/merge-append-doc.sh (clone-로컬)"
log "완료 (멱등 — 재실행 안전): rerere 적용 ${OK_COUNT} 계정 · skip ${SKIP_COUNT} 계정"
