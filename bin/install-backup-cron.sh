#!/usr/bin/env bash
# =============================================================================
# install-backup-cron.sh — **DEPRECATED (feature-0039)**.
#
# feature-0015 시절 이 스크립트는 호스트 root crontab 에 아래 두 줄을 설치했다:
#   0 3 * * *    cd <repo> && bin/backup.sh
#   30 3 * * 0   cd <repo> && bin/restore-rehearsal.sh
#
# root 여야 했던 유일한 이유는 두 스크립트가 `docker exec` 를 쓰는데 이 호스트의 docker
# 소켓 접근이 root 에만 있었기 때문이다. feature-0039 에서 두 잡을 `ops-scheduler`
# **서비스 내부**로 옮겨 docker 소켓 의존을 없앴고, 스케줄 정본은 compose 의
# `OPS_SCHED_BACKUP` / `OPS_SCHED_RESTORE_REHEARSAL` 환경변수다.
#
# 따라서 **install 경로는 더 이상 제공하지 않는다** — 호스트 cron 과 컨테이너 스케줄러가
# 동시에 돌면 백업이 하루 2회 실행돼 보존 회전(BACKUP_KEEP)이 절반으로 줄어든다.
#
# 사용: bin/install-backup-cron.sh [--remove] [--print]
#   --remove : 과거에 설치된 항목 제거 (이관 시 1회 실행 — 지금도 유효)
#   --print  : 현재 crontab 에 남은 잔재만 출력 (변경 없음, 기본)
# =============================================================================
set -euo pipefail
MARK="# feature-0015 zd-backup"
MODE="print"

while [ $# -gt 0 ]; do case "$1" in
  --remove) MODE="remove"; shift ;;
  --print) MODE="print"; shift ;;
  --install) MODE="install"; shift ;;
  --help|-h) sed -n '2,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "unknown arg: $1" >&2; exit 2 ;;
esac; done

command -v crontab >/dev/null || { echo "[cron] crontab 없음 — 정리할 항목도 없음." >&2; exit 0; }

CUR="$(crontab -l 2>/dev/null || true)"
RESIDUAL="$(printf '%s\n' "$CUR" | grep -F "$MARK" || true)"

case "$MODE" in
  install)
    cat >&2 <<'EOF'
[cron] DEPRECATED — 호스트 cron 설치는 feature-0039 에서 폐지됐습니다.
       정기 백업/복원 리허설은 ops-scheduler 서비스가 담당합니다:
         docker compose up -d ops-scheduler
       스케줄 변경은 docker-compose.yml 의 ops-scheduler 환경변수
       (OPS_SCHED_BACKUP / OPS_SCHED_RESTORE_REHEARSAL) 에서 하세요.
       호스트 cron 을 병행하면 백업이 중복 실행되어 보존 회전이 절반으로 줄어듭니다.
EOF
    exit 2
    ;;
  remove)
    printf '%s\n' "$CUR" | grep -vF "$MARK" | grep -vE '^\s*$' | crontab -
    echo "[cron] feature-0015 백업 cron 항목 제거됨 (${MARK})."
    ;;
  print)
    if [ -n "$RESIDUAL" ]; then
      echo "[cron] 아직 남아 있는 호스트 cron 잔재 (--remove 로 정리):"
      printf '%s\n' "$RESIDUAL" | sed 's/^/  /'
    else
      echo "[cron] 잔재 없음 — 정기 실행은 ops-scheduler 서비스가 담당합니다."
    fi
    ;;
esac
