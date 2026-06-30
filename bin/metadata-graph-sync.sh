#!/usr/bin/env bash
# feature-0016 Phase 1c: 관계형 메타데이터 → Apache AGE `metadata_kb` 그래프 동기화 wrapper.
#
# 워커 컨테이너(insight-worker 우선, 없으면 ask-worker) 안의
# scripts/metadata_graph_sync.py 를 docker exec 으로 실행. 관계형 SSOT 를 AGE 그래프로 멱등 투영.
#
# AGE cutover(postgres 커스텀 이미지 + shared_preload_libraries='age') 이후에만 실효.
# cutover 전엔 sync_graph 가 graceful no-op(비차단). Phase 5 에서 cron 으로 주기 호출 예정.
#
# Usage:
#   bin/metadata-graph-sync.sh                 # 전체 scope 동기화
#   bin/metadata-graph-sync.sh --scope <key>   # 특정 datasource scope 만
#
# Exit: 0 성공 / 1 부분오류 / 2 워커 컨테이너 부재
set -euo pipefail

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-repo}"
PASS_ARGS=()
if [ "${1:-}" = "--scope" ] && [ -n "${2:-}" ]; then
  PASS_ARGS=(--scope "$2")
fi

for svc in insight-worker ask-worker; do
  c="${COMPOSE_PROJECT_NAME}-${svc}-1"
  if docker ps --format '{{.Names}}' | grep -qx "$c"; then
    echo "[metadata-graph-sync] exec → ${c}" >&2
    exec docker exec "$c" python /app/scripts/metadata_graph_sync.py "${PASS_ARGS[@]}"
  fi
done

echo "ERROR: 워커 컨테이너(insight-worker/ask-worker)가 실행 중이 아닙니다." >&2
echo "  먼저 'make start' 또는 docker compose up -d insight-worker" >&2
exit 2
