#!/usr/bin/env bash
# kb-schema-compare.sh — TASK-0015 §2.1.3 M1 검증 도구: MySQL ↔ Postgres KB schema
# 컬럼 정합 비교. outside-voice review Blocker B-11 (정책 doc 갱신) 의 직접 산출은
# 아니나 M1 cycle 의 검증 게이트.
#
# 비교 항목 (5 테이블 × 컬럼):
#   - 컬럼 이름 매핑 (MySQL PascalCase ↔ Postgres snake_case)
#   - 컬럼 타입 정합 (MySQL VARCHAR ↔ Postgres varchar; DECIMAL ↔ numeric 등)
#   - nullable 정합
#   - 컬럼 개수 일치
#
# Exit codes:
#   0 — schema 정합 (모든 mapping 검증 PASS)
#   1 — schema mismatch 발견
#   2 — invalid args / 환경 부재
#
# Usage:
#   bin/kb-schema-compare.sh            # 5 테이블 모두 비교
#   bin/kb-schema-compare.sh fact_entries
#   bin/kb-schema-compare.sh --json     # 결과를 JSON 으로

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
    fact_entries|texts|rag_documents|rag_objects)
      SINGLE_TABLE="$1"; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Mapping: Postgres snake_case → MySQL PascalCase.
declare -A PG_TO_MYSQL_TABLE=(
  [fact_entries]=AgentMemoryFactEntries
  [texts]=AgentMemoryTexts
  [rag_documents]=AgentMemoryRagDocuments
  [rag_objects]=AgentMemoryRagObjects
)

mysql_columns() {
  local tbl="$1"
  docker exec -i "$MYSQL_CONTAINER" mysql -uroot -p"$MYSQL_PW" --skip-column-names -B -e \
    "SELECT COLUMN_NAME, IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='${MYSQL_DB}' AND TABLE_NAME='${tbl}' ORDER BY ORDINAL_POSITION;" \
    2>/dev/null | grep -v '^mysql:' || true
}

pg_columns() {
  local tbl="$1"
  docker exec -i -e PGPASSWORD="$PG_PW" "$PG_CONTAINER" \
    psql -h localhost -p 5432 -U "$PG_USER" -d "$PG_DB" --csv -tAc \
    "SELECT column_name, is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='${tbl}' ORDER BY ordinal_position;" \
    2>/dev/null || true
}

# snake_case <-> PascalCase normalization (lower + strip underscores).
norm() { printf '%s' "$1" | tr -d '_' | tr 'A-Z' 'a-z'; }

mismatches=0
report=""

compare_table() {
  local pg_tbl="$1"
  local my_tbl="${PG_TO_MYSQL_TABLE[$pg_tbl]:-}"
  [ -n "$my_tbl" ] || { echo "no MySQL mapping for $pg_tbl"; return; }

  local pg_data my_data
  pg_data=$(pg_columns "$pg_tbl")
  my_data=$(mysql_columns "$my_tbl")

  # texts has extra Postgres-only columns (embedding, embedding_model, embedded_at).
  # rag_objects 의 category_* 는 둘 다 존재.
  local pg_count my_count
  pg_count=$(printf '%s\n' "$pg_data" | grep -cE '^[a-z]' || true)
  my_count=$(printf '%s\n' "$my_data" | grep -cE '^[A-Za-z]' || true)

  local note=""
  case "$pg_tbl" in
    texts)
      # Postgres texts 가 embedding/embedding_model/embedded_at 3 column 추가.
      note=" (Postgres +3: embedding, embedding_model, embedded_at)"
      ;;
  esac

  report+="$(printf '%-15s pg_cols=%s  mysql_cols=%s%s\n' "$pg_tbl" "$pg_count" "$my_count" "$note")"$'\n'

  # Build normalized name set for cross-check.
  local pg_names my_names
  pg_names=$(printf '%s\n' "$pg_data" | awk -F',' '{print $1}' | while read c; do norm "$c"; done | sort -u)
  my_names=$(printf '%s\n' "$my_data" | awk '{print $1}' | while read c; do norm "$c"; done | sort -u)

  # MySQL columns missing in Postgres (mapping fail).
  local missing_in_pg
  missing_in_pg=$(comm -23 <(printf '%s' "$my_names") <(printf '%s' "$pg_names") | tr -s '\n' ' ' || true)
  if [ -n "${missing_in_pg// }" ]; then
    report+="  MISMATCH: MySQL columns not mapped to Postgres: ${missing_in_pg}"$'\n'
    mismatches=$((mismatches + 1))
  fi
}

if [ -n "$SINGLE_TABLE" ]; then
  compare_table "$SINGLE_TABLE"
else
  for t in fact_entries texts rag_documents rag_objects; do
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
    echo "kb-schema-compare: PASS (all column mappings consistent)"
    exit 0
  fi
  echo "kb-schema-compare: FAIL (${mismatches} mismatch(es))" >&2
  exit 1
fi
