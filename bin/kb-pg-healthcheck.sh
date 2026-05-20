#!/usr/bin/env bash
# kb-pg-healthcheck.sh — M0 phase 의 KB Postgres (pgvector/pgvector:pg16) 가용성 점검
#
# 본 스크립트는 TASK-0015 §2.1.3 M0 cycle 의 검증 도구. docker-compose 의 `postgres`
# 서비스가 healthy 한지 + agent 컨테이너의 `_pg_connect()` helper 가 작동하는지
# 두 단계로 점검한다. 본 cycle 의 산출 #4 — `make start` regression check 의 명시
# 검증 항목 (outside-voice review Section F-4 권고).
#
# Usage:
#   bin/kb-pg-healthcheck.sh                  # all checks (default)
#   bin/kb-pg-healthcheck.sh --container      # postgres 컨테이너 status / healthcheck
#   bin/kb-pg-healthcheck.sh --connect        # docker exec 로 psql -c "SELECT 1"
#   bin/kb-pg-healthcheck.sh --pg-connect     # agent 컨테이너의 _pg_connect() 호출
#   bin/kb-pg-healthcheck.sh --extension      # pgvector extension 설치 가능성 점검
#
# Exit codes:
#   0 — all checks PASS
#   1 — at least one check FAIL (stderr 에 사유)
#   2 — invalid args

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WRAPPER_CANDIDATE_A="$(dirname "$REPO_ROOT")"
WRAPPER_CANDIDATE_B="$(dirname "$WRAPPER_CANDIDATE_A")"
if [ -d "${WRAPPER_CANDIDATE_A}/repo" ] && [ -f "${WRAPPER_CANDIDATE_A}/repo/.env" ]; then
  WRAPPER_ROOT="$WRAPPER_CANDIDATE_A"
elif [ -d "${WRAPPER_CANDIDATE_B}/repo" ] && [ -f "${WRAPPER_CANDIDATE_B}/repo/.env" ]; then
  WRAPPER_ROOT="$WRAPPER_CANDIDATE_B"
else
  WRAPPER_ROOT="$WRAPPER_CANDIDATE_A"
fi
MAIN_REPO_ROOT="${WRAPPER_ROOT}/repo"
if [ -f "${MAIN_REPO_ROOT}/.env" ]; then
  ENV_FILE="${MAIN_REPO_ROOT}/.env"
else
  ENV_FILE="${REPO_ROOT}/.env"
fi

# COMPOSE_PROJECT_NAME 강제 — 본 worktree path 에서 호출돼도 main worktree 의
# repo 프로젝트와 동일 컨테이너 세트를 참조. M-1 baseline 에서 학습한 패턴.
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-repo}"

PG_CONTAINER="${COMPOSE_PROJECT_NAME}-postgres-1"
AGENT_CONTAINER="${COMPOSE_PROJECT_NAME}-web-1"

MODE="all"
while [ $# -gt 0 ]; do
  case "$1" in
    --container|--connect|--pg-connect|--extension|--all)
      MODE="${1#--}"; shift ;;
    -h|--help)
      sed -n '2,21p' "$0"; exit 0 ;;
    *)
      echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Helper: load var from .env (read-only).
env_get() {
  local var="$1" default="${2:-}"
  local val
  val="$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | head -1 || true)"
  if [ -z "$val" ]; then val="$default"; fi
  printf '%s' "$val"
}

PG_HOST="$(env_get AGENT_KB_PG_HOST postgres)"
PG_PORT="$(env_get AGENT_KB_PG_PORT 5432)"
PG_DB="$(env_get AGENT_KB_PG_DB agent_kb)"
PG_USER="$(env_get AGENT_KB_PG_USER postgres)"
PG_PASSWORD="$(env_get AGENT_KB_PG_PASSWORD)"

failed=0
pass()  { printf "PASS  %s\n" "$1"; }
fail()  { printf "FAIL  %s :: %s\n" "$1" "$2" >&2; failed=$((failed + 1)); }
note()  { printf "NOTE  %s\n" "$1"; }

check_container() {
  if ! docker ps --filter "name=${PG_CONTAINER}" --filter "status=running" --format '{{.Names}}' 2>/dev/null | grep -qx "${PG_CONTAINER}"; then
    fail "postgres container running" "${PG_CONTAINER} not found in docker ps (start with: make start)"
    return
  fi
  pass "postgres container running (${PG_CONTAINER})"
  local hstatus
  hstatus="$(docker inspect --format '{{.State.Health.Status}}' "$PG_CONTAINER" 2>/dev/null || echo "unknown")"
  if [ "$hstatus" = "healthy" ]; then
    pass "postgres healthcheck (status=healthy)"
  elif [ "$hstatus" = "starting" ]; then
    note "postgres healthcheck (status=starting — try again after 30s)"
  else
    fail "postgres healthcheck" "status=${hstatus}"
  fi
}

check_connect() {
  if [ -z "$PG_PASSWORD" ]; then
    fail "psql connect" "AGENT_KB_PG_PASSWORD empty in $ENV_FILE"
    return
  fi
  local out
  if out="$(docker exec -i -e PGPASSWORD="$PG_PASSWORD" "$PG_CONTAINER" \
             psql -h localhost -p 5432 -U "$PG_USER" -d "$PG_DB" -tAc 'SELECT 1' 2>&1)"; then
    if printf '%s' "$out" | grep -qx '1'; then
      pass "psql SELECT 1 (user=${PG_USER}, db=${PG_DB})"
    else
      fail "psql SELECT 1" "unexpected output: $out"
    fi
  else
    fail "psql SELECT 1" "$out"
  fi
}

check_pg_connect() {
  if ! docker ps --filter "name=${AGENT_CONTAINER}" --filter "status=running" --format '{{.Names}}' 2>/dev/null | grep -qx "${AGENT_CONTAINER}"; then
    fail "_pg_connect() smoke test" "${AGENT_CONTAINER} not running — skip (run after make start)"
    return
  fi
  local out
  if out="$(docker exec -i "$AGENT_CONTAINER" python -c '
from modules.db import _pg_connect, _pg_available
print(f"available={_pg_available()}")
if not _pg_available():
    raise SystemExit(0)
conn = _pg_connect()
with conn.cursor() as cur:
    cur.execute("SELECT 1")
    print(f"select1={cur.fetchone()[0]}")
conn.close()
print("ok")
' 2>&1)"; then
    if printf '%s' "$out" | grep -q '^ok$'; then
      pass "_pg_connect() smoke test"
    else
      note "_pg_connect() partial: $out"
    fi
  else
    fail "_pg_connect() smoke test" "$out"
  fi
}

check_extension() {
  local out
  if out="$(docker exec -i -e PGPASSWORD="$PG_PASSWORD" "$PG_CONTAINER" \
             psql -h localhost -p 5432 -U "$PG_USER" -d "$PG_DB" -tAc \
             'SELECT extname FROM pg_available_extensions WHERE name = '"'"'vector'"'"';' 2>&1)"; then
    if printf '%s' "$out" | grep -qx 'vector'; then
      pass "pgvector extension available (CREATE EXTENSION 가능)"
    else
      fail "pgvector extension" "vector not in pg_available_extensions — image 가 pgvector/pgvector:pg16 인지 확인"
    fi
  else
    fail "pgvector extension query" "$out"
  fi
}

case "$MODE" in
  all)
    check_container
    if [ "$failed" -eq 0 ]; then
      check_connect
      check_extension
      check_pg_connect
    fi
    ;;
  container) check_container ;;
  connect)   check_connect ;;
  pg-connect) check_pg_connect ;;
  extension) check_extension ;;
esac

if [ "$failed" -eq 0 ]; then
  echo "kb-pg-healthcheck: PASS"
  exit 0
fi
echo "kb-pg-healthcheck: FAIL (${failed} check(s))" >&2
exit 1
