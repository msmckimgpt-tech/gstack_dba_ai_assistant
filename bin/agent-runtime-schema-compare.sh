#!/usr/bin/env bash
# agent-runtime-schema-compare.sh — TASK-0112 AR-M1 검증 도구:
# MySQL agent_memory ↔ Postgres agent_runtime schema 컬럼 정합 비교.
#
# 비교 대상 (6 테이블):
#   AgentCoreConversations  → agent_runtime.core_conversations
#   AgentCoreMessages       → agent_runtime.core_messages
#   AgentMemoryKv           → agent_runtime.kv
#   AgentMemoryMessages     → agent_runtime.messages
#   AgentMemorySteps        → agent_runtime.steps
#   AgentMemorySummary      → agent_runtime.summary
#
# Exit codes:
#   0 — schema 정합 (모든 mapping PASS)
#   1 — schema mismatch 발견
#   2 — invalid args / 환경 부재
#
# Usage:
#   bin/agent-runtime-schema-compare.sh              # 6 테이블 모두 비교
#   bin/agent-runtime-schema-compare.sh core_conversations
#   bin/agent-runtime-schema-compare.sh --json       # JSON 출력

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
[ -f "$ENV_FILE" ] || ENV_FILE="${REPO_ROOT}/.env"

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-repo}"
MYSQL_CONTAINER="${COMPOSE_PROJECT_NAME}-mysql-1"
PG_CONTAINER="${COMPOSE_PROJECT_NAME}-postgres-1"

env_get() {
  local var="$1" def="${2:-}"
  local val
  val="$(grep -E "^${var}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | head -1 || true)"
  [ -z "$val" ] && val="$def"
  printf '%s' "$val"
}

MYSQL_PW="$(env_get MYSQL_ROOT_PASSWORD)"
PG_PW="$(env_get AGENT_KB_PG_PASSWORD)"
PG_USER="$(env_get AGENT_KB_PG_USER postgres)"
PG_DB="$(env_get AGENT_KB_PG_DB agent_kb)"
MYSQL_DB="$(env_get AGENT_MEMORY_DB agent_memory)"

JSON_MODE=0
SINGLE_TABLE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON_MODE=1; shift ;;
    core_conversations|core_messages|kv|messages|steps|summary)
      SINGLE_TABLE="$1"; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Mapping: Postgres snake_case → MySQL PascalCase.
declare -A PG_TO_MYSQL_TABLE=(
  [core_conversations]=AgentCoreConversations
  [core_messages]=AgentCoreMessages
  [kv]=AgentMemoryKv
  [messages]=AgentMemoryMessages
  [steps]=AgentMemorySteps
  [summary]=AgentMemorySummary
)

mysql_columns() {
  local tbl="$1"
  docker exec -i "$MYSQL_CONTAINER" mysql -uroot -p"$MYSQL_PW" --skip-column-names -B -e \
    "SELECT COLUMN_NAME, IS_NULLABLE FROM information_schema.COLUMNS \
     WHERE TABLE_SCHEMA='${MYSQL_DB}' AND TABLE_NAME='${tbl}' \
     ORDER BY ORDINAL_POSITION;" \
    2>/dev/null | grep -v '^mysql:' || true
}

pg_columns() {
  local tbl="$1"
  docker exec -i -e PGPASSWORD="$PG_PW" "$PG_CONTAINER" \
    psql -h localhost -p 5432 -U "$PG_USER" -d "$PG_DB" -t -A -F',' -c \
    "SELECT column_name, is_nullable \
     FROM information_schema.columns \
     WHERE table_schema='agent_runtime' AND table_name='${tbl}' \
     ORDER BY ordinal_position;" \
    2>/dev/null || true
}

# snake_case <-> PascalCase normalization (lower + strip underscores).
norm() { printf '%s' "$1" | tr -d '_' | tr 'A-Z' 'a-z'; }

mismatches=0
report=""

compare_table() {
  local pg_tbl="$1"
  local my_tbl="${PG_TO_MYSQL_TABLE[$pg_tbl]:-}"
  [ -n "$my_tbl" ] || { echo "no MySQL mapping for $pg_tbl" >&2; return; }

  local pg_data my_data
  pg_data=$(pg_columns "$pg_tbl")
  my_data=$(mysql_columns "$my_tbl")

  local pg_count my_count
  pg_count=$(printf '%s\n' "$pg_data" | grep -cE '^[a-z]' || true)
  my_count=$(printf '%s\n' "$my_data" | grep -cE '^[A-Za-z]' || true)

  report+="$(printf '%-22s pg_cols=%s  mysql_cols=%s\n' "$pg_tbl" "$pg_count" "$my_count")"$'\n'

  local pg_names my_names
  pg_names=$(printf '%s\n' "$pg_data" | awk -F',' '{print $1}' | while read -r c; do printf '%s\n' "$(norm "$c")"; done | sort -u)
  my_names=$(printf '%s\n' "$my_data" | awk '{print $1}' | while read -r c; do printf '%s\n' "$(norm "$c")"; done | sort -u)

  local missing_in_pg
  missing_in_pg=$(comm -23 <(printf '%s\n' "$my_names") <(printf '%s\n' "$pg_names") | tr -s '\n' ' ' || true)
  if [ -n "${missing_in_pg// }" ]; then
    report+="  MISMATCH: MySQL columns not mapped to Postgres: ${missing_in_pg}"$'\n'
    mismatches=$((mismatches + 1))
  fi
}

if [ -n "$SINGLE_TABLE" ]; then
  compare_table "$SINGLE_TABLE"
else
  for t in core_conversations core_messages kv messages steps summary; do
    compare_table "$t"
  done
fi

if [ "$JSON_MODE" = "1" ]; then
  printf '{"mismatches": %d, "report": %s}\n' \
    "$mismatches" \
    "$(printf '%s' "$report" | python3 -c 'import sys,json;print(json.dumps(sys.stdin.read()))' 2>/dev/null || printf '""')"
else
  printf '%s\n' "$report"
  if [ "$mismatches" -eq 0 ]; then
    echo "agent-runtime-schema-compare: PASS (all column mappings consistent)"
    exit 0
  fi
  echo "agent-runtime-schema-compare: FAIL (${mismatches} mismatch(es))" >&2
  exit 1
fi
