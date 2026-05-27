#!/usr/bin/env bash
# agent-runtime-bootstrap.sh — AR-M0: agent_kb DB 안 agent_runtime schema 신설 + role grant
#
# 본 스크립트는 docs/MIGRATION_AGENT_MEMORY_TO_PG.md Phase 2 AR-M0 cycle 의 핵심 산출물이다.
# 6 agent runtime 테이블 이관 준비 — agent_runtime schema 생성 + agent_kb_rw/ro 에 USAGE 부여.
# 멱등 — 다시 실행해도 IF NOT EXISTS 로 안전.
#
# Bootstrap 순서:
#   1. agent_runtime schema CREATE IF NOT EXISTS
#   2. agent_kb_rw 에 USAGE ON SCHEMA agent_runtime + 추후 table grant 포함
#   3. agent_kb_ro 에 USAGE ON SCHEMA agent_runtime (read-only)
#   4. DEFAULT PRIVILEGES — 이후 CREATE TABLE 시 자동 grant
#
# Role 권한 모델 (ADR-0021 §3 의 agent_runtime 확장):
#   agent_kb_rw — USAGE on schema + (추후) ALL TABLES IN SCHEMA agent_runtime
#   agent_kb_ro — USAGE on schema + (추후) SELECT on ALL TABLES IN SCHEMA agent_runtime
#   DDL 은 superuser (postgres) 만 실행 — agent_kb_rw/ro 는 DML 전용
#
# Usage:
#   bin/agent-runtime-bootstrap.sh                       # 전체 bootstrap
#   bin/agent-runtime-bootstrap.sh --create-schema       # schema 만 CREATE
#   bin/agent-runtime-bootstrap.sh --grant-roles         # role USAGE grant 만
#   bin/agent-runtime-bootstrap.sh --check               # 상태 확인 (read-only)
#
# Defaults:
#   container: ${COMPOSE_PROJECT_NAME:-repo}-postgres-1
#   superuser: postgres
#   db:        agent_kb
#
# Exit codes:
#   0 — 모든 step PASS
#   1 — bootstrap 중 실패 (stderr 사유)
#   2 — invalid args

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WRAPPER_A="$(dirname "$REPO_ROOT")"
WRAPPER_B="$(dirname "$WRAPPER_A")"
if [ -d "${WRAPPER_A}/repo" ] && [ -f "${WRAPPER_A}/repo/.env" ]; then
  WRAPPER_ROOT="$WRAPPER_A"
elif [ -d "${WRAPPER_B}/repo" ] && [ -f "${WRAPPER_B}/repo/.env" ]; then
  WRAPPER_ROOT="$WRAPPER_B"
else
  WRAPPER_ROOT="$WRAPPER_A"
fi
MAIN_REPO_ROOT="${WRAPPER_ROOT}/repo"
ENV_FILE="${MAIN_REPO_ROOT}/.env"
if [ ! -f "$ENV_FILE" ]; then
  ENV_FILE="${REPO_ROOT}/.env"
fi

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-repo}"
PG_CONTAINER="${COMPOSE_PROJECT_NAME}-postgres-1"

env_get() {
  local var="$1" default="${2:-}"
  local val
  val="$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | head -1 || true)"
  [ -z "$val" ] && val="$default"
  printf '%s' "$val"
}

SUPER_USER="$(env_get AGENT_KB_PG_SUPERUSER "$(env_get AGENT_KB_PG_USER postgres)")"
SUPER_PW="$(env_get AGENT_KB_PG_SUPERPASSWORD "$(env_get AGENT_KB_PG_PASSWORD)")"
TARGET_DB="$(env_get AGENT_KB_PG_DB agent_kb)"
TARGET_SCHEMA="agent_runtime"

MODE="all"

usage() {
  cat >&2 <<'EOF'
Usage:
  bin/agent-runtime-bootstrap.sh              # all: schema + grant
  bin/agent-runtime-bootstrap.sh --create-schema
  bin/agent-runtime-bootstrap.sh --grant-roles
  bin/agent-runtime-bootstrap.sh --check
EOF
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --create-schema) MODE="schema"; shift ;;
    --grant-roles)   MODE="grant";  shift ;;
    --check)         MODE="check";  shift ;;
    *) usage ;;
  esac
done

pg_exec() {
  local sql="$1"
  if [ -n "$SUPER_PW" ]; then
    PGPASSWORD="$SUPER_PW" docker exec -e PGPASSWORD="$SUPER_PW" "$PG_CONTAINER" \
      psql -U "$SUPER_USER" -d "$TARGET_DB" -c "$sql" 2>&1
  else
    docker exec "$PG_CONTAINER" \
      psql -U "$SUPER_USER" -d "$TARGET_DB" -c "$sql" 2>&1
  fi
}

create_schema() {
  echo "[1/3] Creating schema ${TARGET_SCHEMA} in ${TARGET_DB} ..." >&2
  pg_exec "CREATE SCHEMA IF NOT EXISTS ${TARGET_SCHEMA};"
  echo "  schema ${TARGET_SCHEMA} ready." >&2
}

grant_roles() {
  echo "[2/3] Granting USAGE on schema ${TARGET_SCHEMA} to agent_kb_rw / agent_kb_ro ..." >&2

  # RW: USAGE + CREATE (DDL는 superuser만, 하지만 CREATE 권한은 future-proof)
  pg_exec "GRANT USAGE ON SCHEMA ${TARGET_SCHEMA} TO agent_kb_rw;"
  # RO: USAGE only
  pg_exec "GRANT USAGE ON SCHEMA ${TARGET_SCHEMA} TO agent_kb_ro;"

  # DEFAULT PRIVILEGES: 이후 superuser가 agent_runtime schema에 생성하는 테이블에 자동 grant
  pg_exec "ALTER DEFAULT PRIVILEGES IN SCHEMA ${TARGET_SCHEMA}
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO agent_kb_rw;"
  pg_exec "ALTER DEFAULT PRIVILEGES IN SCHEMA ${TARGET_SCHEMA}
    GRANT SELECT ON TABLES TO agent_kb_ro;"

  echo "  role grants complete." >&2
}

check_status() {
  echo "[check] agent_runtime schema status in ${TARGET_DB}:" >&2
  pg_exec "SELECT schema_name, schema_owner FROM information_schema.schemata WHERE schema_name = '${TARGET_SCHEMA}';"
  pg_exec "SELECT
    has_schema_privilege('agent_kb_rw', '${TARGET_SCHEMA}', 'USAGE') AS rw_usage,
    has_schema_privilege('agent_kb_ro', '${TARGET_SCHEMA}', 'USAGE') AS ro_usage;"
}

case "$MODE" in
  all)
    create_schema
    grant_roles
    echo "[3/3] Verifying ..." >&2
    check_status
    echo "agent-runtime-bootstrap: PASS" >&2
    ;;
  schema)
    create_schema
    echo "agent-runtime-bootstrap --create-schema: PASS" >&2
    ;;
  grant)
    grant_roles
    echo "agent-runtime-bootstrap --grant-roles: PASS" >&2
    ;;
  check)
    check_status
    ;;
esac
