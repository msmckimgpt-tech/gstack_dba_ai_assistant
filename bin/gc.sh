#!/usr/bin/env bash
# TASK-0134 (#15): 운영 데이터 GC — 무한 증가 정리.
#
# 감사 DEEP_AUDIT_20260529.md #15: 정리 없이 누적되던 (a) kv 고아행(삭제된 대화의 잔존,
# Task 2 _pg_delete_conversation 으로 신규 발생은 차단됐으나 historical 잔존), (b) 만료
# webauthsessions. kv 의 __global__(insight 워커 fingerprint)은 보존. 멱등·재실행 안전.
#
# 사용: bin/gc.sh   (repo/ 에서; host cron 또는 make gc 로 주기 실행)
# 환경: GC_SESSION_GRACE_DAYS(기본 1) — 만료 후 이 일수 지난 세션만 삭제.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env.mysql ] && { set -a; . ./.env.mysql; set +a; }
[ -f .env.postgres ] && { set -a; . ./.env.postgres; set +a; }

PG_CONTAINER="${PG_CONTAINER:-repo-postgres-1}"
MYSQL_CONTAINER="${MYSQL_CONTAINER:-repo-mysql-1}"
PG_USER="${AGENT_KB_PG_USER:-postgres}"
PG_DB="${AGENT_KB_PG_DB:-agent_kb}"
GRACE="${GC_SESSION_GRACE_DAYS:-1}"

echo "[gc] (1) agent_runtime.kv 고아행 삭제 (core_conversations 미존재 + __global__ 아님)"
docker exec -e PGPASSWORD="${AGENT_KB_PG_PASSWORD:-}" "$PG_CONTAINER" \
  psql -U "$PG_USER" -d "$PG_DB" -c \
  "DELETE FROM agent_runtime.kv kv
     WHERE kv.conversation_id <> '__global__'
       AND NOT EXISTS (SELECT 1 FROM agent_runtime.core_conversations c
                       WHERE c.conversation_id = kv.conversation_id);"

echo "[gc] (2) 만료 WebAuthSessions 삭제 (ExpiresAt < now - ${GRACE}d)"
docker exec "$MYSQL_CONTAINER" mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" agent_memory 2>/dev/null -e \
  "DELETE FROM WebAuthSessions
     WHERE ExpiresAt IS NOT NULL AND ExpiresAt < (NOW() - INTERVAL ${GRACE} DAY);
   SELECT ROW_COUNT() AS purged_sessions;"

echo "[gc] 완료"
