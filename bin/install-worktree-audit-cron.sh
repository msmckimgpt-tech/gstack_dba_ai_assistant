#!/usr/bin/env bash
# =============================================================================
# install-worktree-audit-cron.sh — worktree/branch stale sweep 정기 감사 cron 설치(멱등).
# (parallel-work-structure ITEM-04, META-0025 — install-backup-cron.sh 패턴 승계)
#
# 설치 항목(marker 멱등):
#   - 평일 08:40 bin/worktree-audit.sh 리포트 (기본: dry-run — SAFE_REMOVE 노출 기록)
#   - --with-apply 설치 시: 평일 08:50 --apply (직전 08:40 리포트 노출분만 제거)
#     ⚠ --apply 활성화는 ROADMAP parallel-work-structure §6.1 사전 승인 + 첫 리포트
#       검증(acceptance b/c) 후에만 — 기본 설치는 리포트 전용.
# 로그: ../artifacts/worktree-audit/cron.log
#
# 사용: bin/install-worktree-audit-cron.sh [--with-apply] [--remove] [--print]
# =============================================================================
set -euo pipefail
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# cron 은 main checkout 에 앵커 — worktree 에서 설치해도 worktree 경로(수명 짧음)를 쓰지 않는다.
REPO_ROOT="$(dirname "$(git -C "$SCRIPT_ROOT" rev-parse --path-format=absolute --git-common-dir)")"
LOG_DIR="$REPO_ROOT/../artifacts/worktree-audit"
LOG_PATH="$LOG_DIR/cron.log"
MARK="# META-0025 worktree-audit"
MODE="install"
WITH_APPLY=0

while [ $# -gt 0 ]; do case "$1" in
  --with-apply) WITH_APPLY=1; shift ;;
  --remove) MODE="remove"; shift ;;
  --print) MODE="print"; shift ;;
  --help|-h) sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "unknown arg: $1" >&2; exit 2 ;;
esac; done

command -v crontab >/dev/null || { echo "[cron] crontab 없음." >&2; exit 1; }
mkdir -p "$LOG_DIR"

CUR="$(crontab -l 2>/dev/null || true)"
STRIPPED="$(printf '%s\n' "$CUR" | grep -vF "$MARK" || true)"

REPORT_LINE="40 8 * * 1-5 cd $REPO_ROOT && bash bin/worktree-audit.sh >> $LOG_PATH 2>&1 $MARK"
APPLY_LINE="50 8 * * 1-5 cd $REPO_ROOT && bash bin/worktree-audit.sh --apply >> $LOG_PATH 2>&1 $MARK"

case "$MODE" in
  remove)
    printf '%s\n' "$STRIPPED" | crontab -
    echo "[cron] worktree-audit cron 제거됨."
    ;;
  print)
    echo "[cron] 설치될 항목:"; echo "  $REPORT_LINE"
    [ "$WITH_APPLY" = "1" ] && echo "  $APPLY_LINE"
    ;;
  install)
    { printf '%s\n' "$STRIPPED"; echo "$REPORT_LINE"; [ "$WITH_APPLY" = "1" ] && echo "$APPLY_LINE"; } | grep -vE '^\s*$' | crontab -
    echo "[cron] 설치 완료 (멱등):"
    echo "  평일 08:40 worktree-audit 리포트"
    [ "$WITH_APPLY" = "1" ] && echo "  평일 08:50 worktree-audit --apply (직전 리포트 노출분만)"
    echo "  로그: $LOG_PATH"
    ;;
esac
