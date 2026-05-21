#!/usr/bin/env bash
# kb-pg-role-bootstrap.sh — TASK-0015 §2.1.3 M1: agent_kb_rw / agent_kb_ro Postgres
# role 신설 + database 생성 + 본 schema sql 적용.
#
# 본 스크립트는 인증/인가 변경 (§12.3 Major) 의 핵심 step. 1회 실행 후 멱등 — 다시
# 실행해도 IF NOT EXISTS / DO $$ guard 로 안전. ADR-0021 (KB Postgres 분리 후 RBAC
# catalog 재정의) 의 실행 도구.
#
# Bootstrap 순서:
#   1. database agent_kb 생성 (없으면)
#   2. role agent_kb_rw / agent_kb_ro 생성 (없으면)
#   3. agent_kb_schema.sql 적용 (멱등 — CREATE TABLE IF NOT EXISTS)
#   4. role 권한 grant (schema sql 의 DO $$ block 이 처리)
#
# Role 권한 모델 (ADR-0021 §3):
#   agent_kb_rw — SELECT/INSERT/UPDATE/DELETE on 5 KB tables + USAGE on schema.
#                 M2 dual-write 부터 agent 컨테이너의 _pg_connect() 가 본 role 사용.
#   agent_kb_ro — SELECT only. read-only audit / debug 용 (M4+ 의 인간 검토 시점).
#
# 운영 변경: AGENT_KB_PG_USER 의 default 가 'postgres' → 본 cycle 후 'agent_kb_rw' 로
# 변경 권장 (.env 직접 수정). superuser (postgres) 직접 사용은 audit 추적성 떨어짐.
#
# Usage:
#   bin/kb-pg-role-bootstrap.sh                  # 전체 bootstrap (default)
#   bin/kb-pg-role-bootstrap.sh --create-db      # database agent_kb 만 생성
#   bin/kb-pg-role-bootstrap.sh --create-roles   # role 만 생성
#   bin/kb-pg-role-bootstrap.sh --apply-schema   # agent_kb_schema.sql 만 적용
#   bin/kb-pg-role-bootstrap.sh --rotate-password agent_kb_rw <new-pw>
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
if [ -f "${MAIN_REPO_ROOT}/.env" ]; then
  ENV_FILE="${MAIN_REPO_ROOT}/.env"
else
  ENV_FILE="${REPO_ROOT}/.env"
fi

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-repo}"
PG_CONTAINER="${COMPOSE_PROJECT_NAME}-postgres-1"

# Superuser credentials (from .env, default postgres/<AGENT_KB_PG_PASSWORD>).
env_get() {
  local var="$1" default="${2:-}"
  local val
  val="$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | head -1 || true)"
  [ -z "$val" ] && val="$default"
  printf '%s' "$val"
}

SUPER_USER="$(env_get AGENT_KB_PG_USER postgres)"
SUPER_PW="$(env_get AGENT_KB_PG_PASSWORD)"
TARGET_DB="$(env_get AGENT_KB_PG_DB agent_kb)"

# Role 비밀번호 (실 운영에서는 vault / docker secret 권장).
# outside-voice review (REV-20260520-0005) Section D Critical: 'change_me_*' literal
# fallback 은 인증/인가 cycle 의 결함 → fail-loud 강화. env 또는 .env 에서 명시
# 미설정 + 명시 confirm flag 부재 시 exit.
RW_PW="${AGENT_KB_PG_RW_PASSWORD:-$(env_get AGENT_KB_PG_RW_PASSWORD)}"
RO_PW="${AGENT_KB_PG_RO_PASSWORD:-$(env_get AGENT_KB_PG_RO_PASSWORD)}"
if [ -z "$RW_PW" ] || [ -z "$RO_PW" ]; then
  if [ "${AGENT_KB_BOOTSTRAP_ALLOW_WEAK_PW:-0}" = "1" ]; then
    echo "WARN: AGENT_KB_PG_RW_PASSWORD / RO_PASSWORD 미설정 — weak literal 'change_me_*' 사용. 운영 환경에서 즉시 rotate 필수." >&2
    RW_PW="${RW_PW:-change_me_kb_rw}"
    RO_PW="${RO_PW:-change_me_kb_ro}"
  else
    echo "ERROR: AGENT_KB_PG_RW_PASSWORD 또는 AGENT_KB_PG_RO_PASSWORD 가 .env (또는 환경) 에 설정되지 않았습니다." >&2
    echo "ADR-0021 의 인증/인가 cycle 결함 방지 — 두 변수를 채우거나 일회성 dev 사용 시 AGENT_KB_BOOTSTRAP_ALLOW_WEAK_PW=1 환경변수로 명시 confirm 후 재실행하세요." >&2
    exit 1
  fi
fi

# Schema sql 위치 (worktree 또는 main repo).
SCHEMA_SQL="${REPO_ROOT}/unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql"
if [ ! -f "$SCHEMA_SQL" ]; then
  SCHEMA_SQL="${MAIN_REPO_ROOT}/unit/feature-0002-agent-core/src/scripts/agent_kb_schema.sql"
fi

MODE="all"
ROTATE_ROLE=""
ROTATE_PW=""
while [ $# -gt 0 ]; do
  case "$1" in
    --create-db|--create-roles|--apply-schema|--all)
      MODE="${1#--}"; shift ;;
    --rotate-password)
      MODE="rotate-password"; ROTATE_ROLE="$2"; ROTATE_PW="$3"; shift 3 ;;
    -h|--help)
      sed -n '2,35p' "$0"; exit 0 ;;
    *)
      echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[ -n "$SUPER_PW" ] || { echo "AGENT_KB_PG_PASSWORD empty in $ENV_FILE" >&2; exit 1; }

# Helper: docker exec psql as superuser, 결과 출력.
psql_super() {
  local db="${1:-postgres}"
  shift
  docker exec -i -e PGPASSWORD="$SUPER_PW" "$PG_CONTAINER" \
    psql -h localhost -p 5432 -U "$SUPER_USER" -d "$db" -tAc "$@" 2>&1 \
    | grep -v '^psql:' || true
}

create_database() {
  echo "[STEP] CREATE DATABASE ${TARGET_DB} IF NOT EXISTS"
  if psql_super postgres "SELECT 1 FROM pg_database WHERE datname='${TARGET_DB}'" \
       2>&1 | grep -qx '1'; then
    echo "  DB '${TARGET_DB}' already exists — skip"
  else
    docker exec -i -e PGPASSWORD="$SUPER_PW" "$PG_CONTAINER" \
      createdb -h localhost -p 5432 -U "$SUPER_USER" "${TARGET_DB}"
    echo "  DB '${TARGET_DB}' created"
  fi
}

create_roles() {
  echo "[STEP] CREATE ROLE agent_kb_rw / agent_kb_ro"
  # Single DO $$ block for idempotency.
  docker exec -i -e PGPASSWORD="$SUPER_PW" "$PG_CONTAINER" \
    psql -h localhost -p 5432 -U "$SUPER_USER" -d postgres <<SQL
DO \$do\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_kb_rw') THEN
        CREATE ROLE agent_kb_rw LOGIN PASSWORD '${RW_PW}';
        RAISE NOTICE 'created role agent_kb_rw';
    ELSE
        RAISE NOTICE 'role agent_kb_rw already exists — skip';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_kb_ro') THEN
        CREATE ROLE agent_kb_ro LOGIN PASSWORD '${RO_PW}';
        RAISE NOTICE 'created role agent_kb_ro';
    ELSE
        RAISE NOTICE 'role agent_kb_ro already exists — skip';
    END IF;
    -- agent_kb DB 의 CONNECT 권한 부여.
    GRANT CONNECT ON DATABASE ${TARGET_DB} TO agent_kb_rw, agent_kb_ro;
END
\$do\$;
SQL
}

apply_schema() {
  echo "[STEP] APPLY agent_kb_schema.sql"
  if [ ! -f "$SCHEMA_SQL" ]; then
    echo "schema sql missing: $SCHEMA_SQL" >&2
    return 1
  fi
  # Mount schema sql via stdin to avoid filesystem dependency in container.
  docker exec -i -e PGPASSWORD="$SUPER_PW" "$PG_CONTAINER" \
    psql -h localhost -p 5432 -U "$SUPER_USER" -d "${TARGET_DB}" -v ON_ERROR_STOP=1 < "$SCHEMA_SQL"
}

rotate_password() {
  [ -n "$ROTATE_ROLE" ] && [ -n "$ROTATE_PW" ] || \
    { echo "Usage: --rotate-password <agent_kb_rw|agent_kb_ro> <new-pw>" >&2; exit 2; }
  case "$ROTATE_ROLE" in
    agent_kb_rw|agent_kb_ro) ;;
    *) echo "role must be agent_kb_rw or agent_kb_ro" >&2; exit 2 ;;
  esac
  docker exec -i -e PGPASSWORD="$SUPER_PW" "$PG_CONTAINER" \
    psql -h localhost -p 5432 -U "$SUPER_USER" -d postgres \
    -c "ALTER ROLE ${ROTATE_ROLE} WITH PASSWORD '${ROTATE_PW}';"
  echo "rotated password for ${ROTATE_ROLE}"
}

case "$MODE" in
  all)
    create_database
    create_roles
    apply_schema
    ;;
  create-db)     create_database ;;
  create-roles)  create_roles ;;
  apply-schema)  apply_schema ;;
  rotate-password) rotate_password ;;
esac

echo "kb-pg-role-bootstrap: DONE (mode=${MODE})"
