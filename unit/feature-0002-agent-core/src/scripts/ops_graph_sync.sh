#!/usr/bin/env bash
# feature-0039: 관계형 메타데이터 → AGE `metadata_kb` 그래프 동기화 — **컨테이너 내부판**.
#
# `bin/metadata-graph-sync.sh` (호스트 root cron + `docker exec`) 의 이관본. 호스트
# 래퍼는 `docker exec <worker> python /app/scripts/metadata_graph_sync.py` 였는데,
# ops-scheduler 는 같은 이미지라 그 파이썬 CLI 를 **직접** 실행한다(docker 소켓 불요).
#
# ⚠️ **lock 은 반드시 호스트와 공유해야 한다**. 2026-07-14 인시던트(§82): 동시성 가드
# 부재로 cron 실행이 이전 실행 위에 쌓여 pgbouncer 풀이 lock-wait 로 소진되고 워커
# 전체가 장애. 그 가드는 `bin/metadata-graph-sync.sh` 와 **`bin/routine-backfill.sh`
# (여전히 호스트 실행)** 가 공유하는 flock 이다. 본 스크립트는 같은 lock 파일을
# bind-mount 로 잡는다 — flock 은 inode 단위라 호스트/컨테이너 경로가 달라도 같은
# 파일이면 상호배제가 성립한다. 마운트가 없으면 **fail-loud**(가드 없이 도는 것보다
# 안 도는 편이 안전 — 위 인시던트의 재발 방지가 우선).
#
# Exit: 0 성공 / 1 부분오류·lock 마운트 부재 / 3 이전 실행 진행 중(overlap skip)
set -euo pipefail

LOCK_DIR="${OPS_GRAPH_SYNC_LOCK_DIR:-/opslocks}"
LOCK_FILE="${LOCK_DIR}/age-graph-sync.lock"

if [ ! -d "$LOCK_DIR" ]; then
  echo "ERROR: lock 디렉터리 미마운트 (${LOCK_DIR}) — 호스트 routine-backfill.sh 와의" >&2
  echo "       상호배제가 성립하지 않아 중단합니다. compose 의 ops-scheduler volumes 를 확인하세요." >&2
  exit 1
fi
# symlink pre-plant TOCTOU 방지 — 호스트 래퍼와 동일 가드.
if [ -L "$LOCK_FILE" ]; then
  echo "ERROR: lock 파일이 심볼릭 링크입니다 — 변조 의심, 중단 (${LOCK_FILE})" >&2
  exit 1
fi
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[ops-graph-sync] 이전 실행(또는 routine-backfill.sh)이 아직 진행 중 — skip (lock: ${LOCK_FILE})" >&2
  exit 3
fi

exec python /app/scripts/metadata_graph_sync.py "$@"
