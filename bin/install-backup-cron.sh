#!/usr/bin/env bash
# =============================================================================
# install-backup-cron.sh — feature-0015 (⑤): 정기 백업 + 주간 복원 리허설 cron 설치(멱등).
#
# 설치 항목(marker 로 멱등 — 재실행해도 중복 추가 안 함):
#   - 매일 03:00  bin/backup.sh
#   - 매주 일 03:30 bin/restore-rehearsal.sh
# 로그: ../artifacts/backups/cron.log
#
# 사용: bin/install-backup-cron.sh [--remove] [--print]
#   --print  : 설치될/현재 crontab 만 출력(변경 없음)
#   --remove : 본 스크립트가 설치한 항목 제거
# =============================================================================
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_PATH="$REPO_ROOT/../artifacts/backups/cron.log"
MARK="# feature-0015 zd-backup"
MODE="install"

while [ $# -gt 0 ]; do case "$1" in
  --remove) MODE="remove"; shift ;;
  --print) MODE="print"; shift ;;
  --help|-h) sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "unknown arg: $1" >&2; exit 2 ;;
esac; done

command -v crontab >/dev/null || { echo "[cron] crontab 없음 — 호스트에 cron 설치 필요." >&2; exit 1; }

CUR="$(crontab -l 2>/dev/null || true)"
# 기존 marker 라인 제거(멱등 재설치 / remove 공통)
STRIPPED="$(printf '%s\n' "$CUR" | grep -vF "$MARK" || true)"

BACKUP_LINE="0 3 * * * cd $REPO_ROOT && bin/backup.sh >> $LOG_PATH 2>&1 $MARK"
REHEARSE_LINE="30 3 * * 0 cd $REPO_ROOT && bin/restore-rehearsal.sh >> $LOG_PATH 2>&1 $MARK"

case "$MODE" in
  remove)
    printf '%s\n' "$STRIPPED" | crontab -
    echo "[cron] feature-0015 백업 cron 제거됨."
    ;;
  print)
    echo "[cron] 설치될 항목:"; echo "  $BACKUP_LINE"; echo "  $REHEARSE_LINE"
    echo "[cron] 현재 crontab:"; printf '%s\n' "$CUR" | sed 's/^/  /'
    ;;
  install)
    { printf '%s\n' "$STRIPPED"; echo "$BACKUP_LINE"; echo "$REHEARSE_LINE"; } | grep -vE '^\s*$' | crontab -
    echo "[cron] 설치 완료 (멱등):"
    echo "  매일 03:00     bin/backup.sh"
    echo "  매주 일 03:30  bin/restore-rehearsal.sh"
    echo "  로그: $LOG_PATH"
    ;;
esac
