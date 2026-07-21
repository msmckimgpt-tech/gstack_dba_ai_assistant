#!/usr/bin/env bash
# scratch-pg-bootstrap.sh — feature-0022: agent PG scratch workspace 부트스트랩.
#
# `agent_scratch` database + `agent_scratch_rw` login role 을 신설하고, 관리(레지스트리)
# 스키마를 적용한다. kb-pg-role-bootstrap.sh (ADR-0021) 의 형제 — 별도 database 라 alembic
# (agent_kb 대상) 밖에 있으므로 전용 bootstrap 이 필요하다.
#
# Bootstrap 순서 (멱등 — 반복 실행 안전):
#   1. database agent_scratch 생성 (없으면)
#   2. role agent_scratch_rw 생성 (없으면) + CONNECT 부여
#   3. agent_scratch_schema.sql 적용 (레지스트리 스키마 + CONNECT/CREATE 잠금)
#
# Role 권한 모델 (feature-0022 ADR-SCRATCH-0001):
#   agent_scratch_rw — agent_scratch DB 안에서 완전 자율(스키마/테이블 CREATE·DROP·CRUD).
#                      non-superuser. CONNECT 는 agent_scratch 에만(+무-grant·코드 dbname 고정·
#                      PG cross-DB 불가) → agent_kb/runtime/web/datasource 실질 도달 불가.
#                      --harden-kb-isolation 로 sibling DB PUBLIC CONNECT 회수 시 role 레벨까지 봉인.
#
# 격리 강화(선택): --harden-kb-isolation 은 REVOKE CONNECT ON DATABASE agent_kb FROM PUBLIC
#   를 수행해 scratch role(및 여타 PUBLIC-의존 role)의 agent_kb 접속 자체를 차단한다. agent_kb_rw/
#   agent_kb_ro 는 명시 GRANT 를 보유하므로 영향 없음. 기본은 미수행 (기존 인프라 blast-radius 0;
#   무-grant 로 이미 실질 격리). 운영에서 최대 보호를 원할 때만 명시 opt-in.
#
# Usage:
#   bin/scratch-pg-bootstrap.sh                    # 전체 bootstrap (default)
#   bin/scratch-pg-bootstrap.sh --create-db        # database 만 생성
#   bin/scratch-pg-bootstrap.sh --create-roles     # role 만 생성
#   bin/scratch-pg-bootstrap.sh --apply-schema     # 레지스트리 스키마 sql 만 적용
#   bin/scratch-pg-bootstrap.sh --harden-kb-isolation   # (선택) agent_kb PUBLIC CONNECT 회수
#   bin/scratch-pg-bootstrap.sh --rotate-password <new-pw>
#
# Exit codes:
#   0 — 모든 step PASS   1 — 실패   2 — invalid args
#
# Requires: docker exec 로 postgres 컨테이너 접근 (kb-pg-role-bootstrap.sh 와 동일 경로).

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

env_get() {
  local var="$1" default="${2:-}"
  local val
  val="$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | head -1 || true)"
  [ -z "$val" ] && val="$default"
  printf '%s' "$val"
}

# Superuser: agent_scratch DB/role 생성엔 실제 PG superuser 가 필요하다. 운영에서 AGENT_KB_PG_USER 는
# 감사용 non-superuser(agent_kb_rw)로 바뀌어 있을 수 있으므로(ADR-0021 권장) 별도 superuser 를 쓴다.
# 기본 'postgres'(컨테이너 unix 소켓 trust/peer — 비밀번호 불요). AGENT_SCRATCH_PG_SUPERUSER /
# AGENT_SCRATCH_PG_SUPERUSER_PW 로 override 가능(비-소켓·비-trust 환경).
SUPER_USER="$(env_get AGENT_SCRATCH_PG_SUPERUSER)"; [ -z "$SUPER_USER" ] && SUPER_USER="postgres"
SUPER_PW="${AGENT_SCRATCH_PG_SUPERUSER_PW:-$(env_get AGENT_SCRATCH_PG_SUPERUSER_PW)}"
KB_DB="$(env_get AGENT_KB_PG_DB agent_kb)"

# scratch DB / role.
SCRATCH_DB="$(env_get AGENT_SCRATCH_PG_DB agent_scratch)"
SCRATCH_USER="$(env_get AGENT_SCRATCH_PG_USER agent_scratch_rw)"

# scratch role 비밀번호 — kb-pg-role-bootstrap 과 동일한 fail-loud 정책(weak literal 금지).
SCRATCH_PW="${AGENT_SCRATCH_PG_PASSWORD:-$(env_get AGENT_SCRATCH_PG_PASSWORD)}"
if [ -z "$SCRATCH_PW" ]; then
  if [ "${AGENT_SCRATCH_BOOTSTRAP_ALLOW_WEAK_PW:-0}" = "1" ]; then
    echo "WARN: AGENT_SCRATCH_PG_PASSWORD 미설정 — weak literal 'change_me_scratch' 사용. 운영에서 즉시 rotate 필수." >&2
    SCRATCH_PW="change_me_scratch"
  else
    echo "ERROR: AGENT_SCRATCH_PG_PASSWORD 가 .env(또는 환경)에 설정되지 않았습니다." >&2
    echo "채우거나 일회성 dev 사용 시 AGENT_SCRATCH_BOOTSTRAP_ALLOW_WEAK_PW=1 로 명시 confirm 후 재실행하세요." >&2
    exit 1
  fi
fi

SCHEMA_SQL="${REPO_ROOT}/unit/feature-0002-agent-core/src/scripts/agent_scratch_schema.sql"
if [ ! -f "$SCHEMA_SQL" ]; then
  SCHEMA_SQL="${MAIN_REPO_ROOT}/unit/feature-0002-agent-core/src/scripts/agent_scratch_schema.sql"
fi

MODE="all"
ROTATE_PW=""
while [ $# -gt 0 ]; do
  case "$1" in
    --create-db|--create-roles|--apply-schema|--harden-kb-isolation|--all)
      MODE="${1#--}"; shift ;;
    --rotate-password)
      MODE="rotate-password"; ROTATE_PW="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,33p' "$0"; exit 0 ;;
    *)
      echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# 소켓 trust/peer(기본 postgres)면 비밀번호 불요 — SUPER_PW 는 override 시에만 사용(빈 값 무해).

psql_super() {
  local db="${1:-postgres}"
  shift
  docker exec -i -e PGPASSWORD="$SUPER_PW" "$PG_CONTAINER" \
    psql  -U "$SUPER_USER" -d "$db" -tAc "$@" 2>&1 \
    | grep -v '^psql:' || true
}

create_database() {
  echo "[STEP] CREATE DATABASE ${SCRATCH_DB} IF NOT EXISTS"
  if psql_super postgres "SELECT 1 FROM pg_database WHERE datname='${SCRATCH_DB}'" \
       2>&1 | grep -qx '1'; then
    echo "  DB '${SCRATCH_DB}' already exists — skip"
  else
    docker exec -i -e PGPASSWORD="$SUPER_PW" "$PG_CONTAINER" \
      createdb  -U "$SUPER_USER" "${SCRATCH_DB}"
    echo "  DB '${SCRATCH_DB}' created"
  fi
}

create_roles() {
  echo "[STEP] CREATE ROLE ${SCRATCH_USER}"
  docker exec -i -e PGPASSWORD="$SUPER_PW" "$PG_CONTAINER" \
    psql  -U "$SUPER_USER" -d postgres <<SQL
DO \$do\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${SCRATCH_USER}') THEN
        CREATE ROLE ${SCRATCH_USER} LOGIN PASSWORD '${SCRATCH_PW}';
        RAISE NOTICE 'created role ${SCRATCH_USER}';
    ELSE
        RAISE NOTICE 'role ${SCRATCH_USER} already exists — skip';
    END IF;
    -- 완전 자율의 경계: agent_scratch DB 안에서만 작동. NOSUPERUSER/NOCREATEDB/NOCREATEROLE 명시.
    ALTER ROLE ${SCRATCH_USER} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
END
\$do\$;
SQL
}

apply_schema() {
  echo "[STEP] APPLY agent_scratch_schema.sql (db=${SCRATCH_DB})"
  if [ ! -f "$SCHEMA_SQL" ]; then
    echo "schema sql missing: $SCHEMA_SQL" >&2
    return 1
  fi
  docker exec -i -e PGPASSWORD="$SUPER_PW" "$PG_CONTAINER" \
    psql  -U "$SUPER_USER" -d "${SCRATCH_DB}" -v ON_ERROR_STOP=1 < "$SCHEMA_SQL"
}

harden_kb_isolation() {
  # 기본 격리(agent_scratch_rw 가 다른 DB 에 무-grant + 코드가 항상 agent_scratch 로만 연결 +
  # PG 단일세션 cross-DB 불가 + non-superuser)로 실질 도달 불가하나, agent_scratch_rw 는 PUBLIC
  # 멤버라 role 레벨엔 sibling DB CONNECT 가 남아 있다. 본 강화는 그 잔여마저 없앤다(defense-in-depth).
  # 주의: agent_kb_rw/agent_kb_ro/web* 등 정당 소비자는 명시 GRANT 보유 → 영향 없음. superuser 는
  # ACL bypass. 기존 인프라 blast-radius 를 줄이려 opt-in 기본 미수행.
  local db
  for db in "${KB_DB}" agent_runtime agent_memory web; do
    if psql_super postgres "SELECT 1 FROM pg_database WHERE datname='${db}'" 2>&1 | grep -qx '1'; then
      echo "[STEP] HARDEN: REVOKE CONNECT ON DATABASE ${db} FROM PUBLIC"
      docker exec -i -e PGPASSWORD="$SUPER_PW" "$PG_CONTAINER" \
        psql  -U "$SUPER_USER" -d postgres -v ON_ERROR_STOP=1 \
        -c "REVOKE CONNECT ON DATABASE ${db} FROM PUBLIC;" || echo "  (skip ${db} — revoke 실패, 계속)"
    fi
  done
}

rotate_password() {
  [ -n "$ROTATE_PW" ] || { echo "Usage: --rotate-password <new-pw>" >&2; exit 2; }
  docker exec -i -e PGPASSWORD="$SUPER_PW" "$PG_CONTAINER" \
    psql  -U "$SUPER_USER" -d postgres \
    -c "ALTER ROLE ${SCRATCH_USER} WITH PASSWORD '${ROTATE_PW}';"
  echo "rotated password for ${SCRATCH_USER}"
}

case "$MODE" in
  all)
    create_database
    create_roles
    apply_schema
    ;;
  create-db)            create_database ;;
  create-roles)         create_roles ;;
  apply-schema)         apply_schema ;;
  harden-kb-isolation)  harden_kb_isolation ;;
  rotate-password)      rotate_password ;;
esac

echo "scratch-pg-bootstrap: DONE (mode=${MODE})"
