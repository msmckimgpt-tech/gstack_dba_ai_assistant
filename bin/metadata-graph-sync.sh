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
#   bin/metadata-graph-sync.sh                     # 전체 scope 동기화(full)
#   bin/metadata-graph-sync.sh --scope <key>       # 특정 datasource scope 만
#   bin/metadata-graph-sync.sh --incremental       # 변경분만(부하 절감, insight-load-spread)
#   bin/metadata-graph-sync.sh --full              # 전량(삭제/파단 반영)
#   (모든 인자는 scripts/metadata_graph_sync.py 로 그대로 전달)
#
# Exit: 0 성공 / 1 부분오류 / 2 워커 컨테이너 부재 / 3 이전 실행 진행 중(overlap skip)
set -euo pipefail

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-repo}"
# insight-load-spread: --scope 뿐 아니라 --incremental/--full/--quiet 등 모든 인자를 pass-through.
PASS_ARGS=("$@")

# 2026-07-14 incident: 동시성 가드 부재로 cron(*/30분) 이 이전 실행(AGE 그래프 lock 경합으로
# 장시간 멈춤) 위에 계속 새 실행을 겹쳐 쌓아, pgbouncer 커넥션 풀이 lock-wait 로 전부 소진되고
# ask-worker/insight-worker 전체가 query_wait_timeout 으로 장애(로그인 후 빈 화면 등)를 일으켰다.
# flock -n 으로 겹침 실행 자체를 차단 — 이전 실행이 살아있으면 즉시 skip(exit 3), 무한 대기 안 함.
# 이 lock 은 bin/routine-backfill.sh 와 **공유**한다 — 둘 다 같은 AGE 그래프(metadata_kb)의
# sync_graph() 를 호출하므로(§18.8 적대 리뷰 지적: cron-self-overlap 만 막으면 수동 backfill
# 과의 동시 실행으로 동일 lock 경합이 재발), 자원(그래프) 단위로 직렬화해야 실제 방지가 된다.
# lock 파일은 world-writable /tmp 대신 root 전용 디렉터리에 둔다(symlink pre-plant TOCTOU 방지
# — 매 실행마다 심볼릭 링크 여부를 확인해 대상이 링크면 fail-loud 로 거부).
LOCK_DIR="/root/.locks/mysql-ai-delegated-dev"
LOCK_FILE="${LOCK_DIR}/age-graph-sync.lock"
mkdir -p -m 700 "$LOCK_DIR"
if [ -L "$LOCK_FILE" ]; then
  echo "ERROR: lock 파일이 심볼릭 링크입니다 — 변조 의심, 중단 (${LOCK_FILE})" >&2
  exit 1
fi
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[metadata-graph-sync] 이전 실행(또는 routine-backfill.sh)이 아직 진행 중 — skip (lock: ${LOCK_FILE})" >&2
  exit 3
fi

for svc in insight-worker ask-worker; do
  c="${COMPOSE_PROJECT_NAME}-${svc}-1"
  if docker ps --format '{{.Names}}' | grep -qx "$c"; then
    echo "[metadata-graph-sync] exec → ${c}" >&2
    docker exec "$c" python /app/scripts/metadata_graph_sync.py "${PASS_ARGS[@]}"
    exit $?
  fi
done

echo "ERROR: 워커 컨테이너(insight-worker/ask-worker)가 실행 중이 아닙니다." >&2
echo "  먼저 'make start' 또는 docker compose up -d insight-worker" >&2
exit 2
