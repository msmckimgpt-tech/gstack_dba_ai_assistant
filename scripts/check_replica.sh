#!/usr/bin/env bash
# Replica MySQL 연결 smoke check (TASK-0045).
# agent 컨테이너 내부에서 REPLICA_DB_* 환경값으로 SELECT 1 을 수행해 AI 전용 복제
# 인스턴스 접근 가능 여부를 확인한다. 정본 문서: unit/feature-0001-platform-runtime/docs/FUNCTION.md §14.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "[replica-check] .env 파일이 없다. cp .env.example .env 후 REPLICA_DB_* 를 채우고 재시도하라." >&2
  exit 1
fi

host="$(sed -n 's/^REPLICA_DB_HOST=//p' .env | tail -n 1)"
if [ -z "${host}" ]; then
  echo "[replica-check] .env 의 REPLICA_DB_HOST 가 비어 있다. 복제 인스턴스 접속 정보를 기입 후 재시도하라." >&2
  exit 2
fi

COMPOSE_BAKE=false docker compose --ansi=never run --rm --remove-orphans \
  --entrypoint bash agent -lc '
    set -euo pipefail
    : "${REPLICA_DB_HOST:?REPLICA_DB_HOST 가 agent 컨테이너에 주입되지 않았다}"
    : "${REPLICA_DB_PORT:=3306}"
    : "${REPLICA_DB_USER:?REPLICA_DB_USER 가 agent 컨테이너에 주입되지 않았다}"
    : "${REPLICA_DB_PASSWORD:?REPLICA_DB_PASSWORD 가 agent 컨테이너에 주입되지 않았다}"
    echo "[replica-check] host=${REPLICA_DB_HOST} port=${REPLICA_DB_PORT} user=${REPLICA_DB_USER} db=${REPLICA_DB_NAME:-<none>}"
    if [ -n "${REPLICA_DB_NAME:-}" ]; then
      mysql --protocol=TCP -h "$REPLICA_DB_HOST" -P "$REPLICA_DB_PORT" -u "$REPLICA_DB_USER" -p"$REPLICA_DB_PASSWORD" "$REPLICA_DB_NAME" -e "SELECT 1 AS replica_ok;"
    else
      mysql --protocol=TCP -h "$REPLICA_DB_HOST" -P "$REPLICA_DB_PORT" -u "$REPLICA_DB_USER" -p"$REPLICA_DB_PASSWORD" -e "SELECT 1 AS replica_ok;"
    fi
  '

echo "[replica-check] OK"
