#!/usr/bin/env bash
# =============================================================================
# install-metadata-graph-sync-cron.sh — **DEPRECATED (feature-0039)**.
#
# feature-0016 시절 이 스크립트는 호스트 root crontab 에 아래 두 줄을 설치했다:
#   */30 * * * *  cd <repo> && bin/metadata-graph-sync.sh --incremental
#   17 4 * * *    cd <repo> && bin/metadata-graph-sync.sh --full
#
# 원 주석이 "반드시 sudo(root crontab)로 실행" 을 요구했던 근거는 **docker 소켓 접근이
# root 에만 있다** 는 것 하나였다. feature-0039 에서 이 잡을 `ops-scheduler` **서비스
# 내부**로 옮겨 docker exec 자체를 없앴으므로 그 근거가 소멸했다. 스케줄 정본은
# compose 의 `OPS_SCHED_GRAPH_INCREMENTAL` / `OPS_SCHED_GRAPH_FULL` 환경변수다.
#
# §82 동시성 가드(2026-07-14 인시던트)는 유지된다 — 컨테이너의 ops_graph_sync.sh 가
# 호스트 `bin/routine-backfill.sh` 와 **같은 lock 파일**을 bind-mount 로 공유한다.
#
# **install 경로는 더 이상 제공하지 않는다** — 호스트 cron 병행은 lock 경합만 늘린다.
#
# 사용: bin/install-metadata-graph-sync-cron.sh [--remove] [--print]
#   --remove : 과거에 설치된 항목 제거 (이관 시 1회 실행 — 지금도 유효)
#   --print  : 현재 crontab 에 남은 잔재만 출력 (변경 없음, 기본)
# =============================================================================
set -euo pipefail
MARK="# feature-0016 metadata-graph-sync"
MODE="print"

while [ $# -gt 0 ]; do case "$1" in
  --remove) MODE="remove"; shift ;;
  --print) MODE="print"; shift ;;
  --install) MODE="install"; shift ;;
  --help|-h) sed -n '2,21p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "unknown arg: $1" >&2; exit 2 ;;
esac; done

command -v crontab >/dev/null || { echo "[cron] crontab 없음 — 정리할 항목도 없음." >&2; exit 0; }

CUR="$(crontab -l 2>/dev/null || true)"
RESIDUAL="$(printf '%s\n' "$CUR" | grep -F "$MARK" || true)"

case "$MODE" in
  install)
    cat >&2 <<'EOF'
[cron] DEPRECATED — 호스트 cron 설치는 feature-0039 에서 폐지됐습니다.
       정기 그래프 동기화는 ops-scheduler 서비스가 담당합니다:
         docker compose up -d ops-scheduler
       스케줄 변경은 docker-compose.yml 의 ops-scheduler 환경변수
       (OPS_SCHED_GRAPH_INCREMENTAL / OPS_SCHED_GRAPH_FULL) 에서 하세요.
       수동 1회 실행은 여전히 bin/metadata-graph-sync.sh 를 쓰면 됩니다.
EOF
    exit 2
    ;;
  remove)
    printf '%s\n' "$CUR" | grep -vF "$MARK" | grep -vE '^\s*$' | crontab -
    echo "[cron] feature-0016 metadata-graph-sync cron 항목 제거됨 (${MARK})."
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
