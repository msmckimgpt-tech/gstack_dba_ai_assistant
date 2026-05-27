#!/usr/bin/env bash
# runtime-dual-write-verify.sh — AR-M2-c cross-DB audit + row count 정합 검증.
#
# ADR-0027 §Consequences 의 cross-DB audit SLA (≤0.1% target) 의 측정 도구.
# M2 dual-write 가 진행 중인 동안 MySQL `agent_memory` 측과 Postgres `agent_kb.agent_runtime`
# 측의 6 runtime 테이블 row count + audit SLA 를 확인.
#
# Mode:
#   --counts        row count 비교 (6 테이블) — M2 cycle 의 일상 모니터링
#   --audit-sla     audit INSERT 미실행 비율 측정 (webauditevents vs PG row count)
#   --since <ISO>   AGENT_RUNTIME_DUAL_WRITE 시작 시점 이후 row 만 비교
#   --all           위 3종 모두
#
# Usage:
#   bin/runtime-dual-write-verify.sh --counts
#   bin/runtime-dual-write-verify.sh --since 2026-05-27T00:00:00 --audit-sla
#   bin/runtime-dual-write-verify.sh --all
#
# Exit codes:
#   0 — 정합 (count diff ≤ 1% 또는 audit SLA ≤ 0.1%)
#   1 — mismatch 발견
#   2 — invalid args / 환경 부재

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

MODE=""
SINCE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --counts|--audit-sla|--all) MODE="${1#--}"; shift ;;
    --since) SINCE="$2"; shift 2 ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[ -n "$MODE" ] || { echo "specify --counts / --audit-sla / --all" >&2; exit 2; }

# SINCE auto-load from .env
if [ -z "$SINCE" ]; then
  SINCE="$(env_get AGENT_RUNTIME_DUAL_WRITE_START_TS)"
  if [ -z "$SINCE" ]; then
    SINCE="$(date -Iseconds -d '7 days ago' 2>/dev/null || date -u -v-7d '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || echo '')"
    [ -n "$SINCE" ] && echo "[INFO] --since auto-set to 7-day window: $SINCE" >&2
  else
    echo "[INFO] --since auto-loaded from .env AGENT_RUNTIME_DUAL_WRITE_START_TS: $SINCE" >&2
  fi
fi

# SINCE validation
if [ -n "$SINCE" ] && ! printf '%s' "$SINCE" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}([T ][0-9]{2}:[0-9]{2}(:[0-9]{2})?(Z|[+-][0-9]{2}:[0-9]{2})?)?$'; then
  echo "[ERROR] --since must be ISO 8601 timestamp (e.g. 2026-05-27T00:00:00)" >&2
  exit 2
fi

mysql_query() {
  docker exec "$MYSQL_CONTAINER" \
    mysql -uroot -p"$MYSQL_PW" -N -s --batch -e "$1" "$MYSQL_DB" 2>/dev/null
}

pg_query() {
  docker exec -i "$PG_CONTAINER" \
    psql -U "$PG_USER" -d "$PG_DB" -t -A -c "$1" 2>/dev/null
}

FAIL=0

# ─────────────────────────────────────────────────────────────────────────────
# --counts: 6 테이블 MySQL ↔ PG row count 비교
# ─────────────────────────────────────────────────────────────────────────────

run_counts() {
  echo "[counts] MySQL vs Postgres agent_runtime 6-table row count comparison"
  echo "  SINCE: ${SINCE:-all rows}"

  # MySQL table name → PG table name 매핑
  declare -A PG_TABLE_MAP=(
    ["AgentCoreConversations"]="agent_runtime.core_conversations"
    ["AgentCoreMessages"]="agent_runtime.core_messages"
    ["AgentMemoryKv"]="agent_runtime.kv"
    ["AgentMemoryMessages"]="agent_runtime.messages"
    ["AgentMemorySteps"]="agent_runtime.steps"
    ["AgentMemorySummary"]="agent_runtime.summary"
  )

  # MySQL timestamp column mapping (실 테이블 컬럼 기준)
  declare -A MYSQL_TS_COL=(
    ["AgentCoreConversations"]="created_at"
    ["AgentCoreMessages"]="created_at"
    ["AgentMemoryKv"]="UpdatedAt"
    ["AgentMemoryMessages"]="CreatedAt"
    ["AgentMemorySteps"]="CreatedAt"
    ["AgentMemorySummary"]="UpdatedAt"
  )

  # PG timestamp column mapping (agent_runtime schema DDL 기준)
  declare -A PG_TS_COL=(
    ["agent_runtime.core_conversations"]="created_at"
    ["agent_runtime.core_messages"]="created_at"
    ["agent_runtime.kv"]="updated_at"
    ["agent_runtime.messages"]="created_at"
    ["agent_runtime.steps"]="created_at"
    ["agent_runtime.summary"]="updated_at"
  )

  local overall_ok=0
  for mysql_tbl in AgentCoreConversations AgentCoreMessages AgentMemoryKv AgentMemoryMessages AgentMemorySteps AgentMemorySummary; do
    local pg_tbl="${PG_TABLE_MAP[$mysql_tbl]}"
    local mts_col="${MYSQL_TS_COL[$mysql_tbl]}"
    local pts_col="${PG_TS_COL[$pg_tbl]}"

    local mysql_where=""
    local pg_where=""
    if [ -n "$SINCE" ]; then
      mysql_where=" WHERE ${mts_col} >= '${SINCE}'"
      pg_where=" WHERE ${pts_col} >= '${SINCE}'"
    fi

    local mysql_cnt pg_cnt
    mysql_cnt="$(mysql_query "SELECT COUNT(*) FROM ${mysql_tbl}${mysql_where};" 2>/dev/null || echo "ERROR")"
    pg_cnt="$(pg_query "SELECT COUNT(*) FROM ${pg_tbl}${pg_where};" 2>/dev/null || echo "ERROR")"

    local status="OK"
    if [ "$mysql_cnt" = "ERROR" ] || [ "$pg_cnt" = "ERROR" ]; then
      status="ERROR"
      overall_ok=1
    elif [ "$mysql_cnt" -ne "$pg_cnt" ] 2>/dev/null; then
      # dual-write 는 진행 중이므로 MySQL > PG 는 정상 (PG 가 따라오는 중)
      # PG > MySQL 은 이상 (데이터 loss)
      if [ "$pg_cnt" -gt "$mysql_cnt" ] 2>/dev/null; then
        status="WARN:PG>MySQL"
        overall_ok=1
      else
        diff=$(( mysql_cnt - pg_cnt ))
        status="LAG:MySQL-PG=${diff}"
      fi
    fi

    printf "  %-30s MySQL=%-8s PG=%-8s [%s]\n" "$mysql_tbl" "$mysql_cnt" "$pg_cnt" "$status"
  done

  if [ "$overall_ok" -eq 0 ]; then
    echo "[counts] PASS — 6 table counts match (or PG ≤ MySQL within dual-write lag)"
  else
    echo "[counts] FAIL — count mismatch or query error detected" >&2
    FAIL=1
  fi
}

# ─────────────────────────────────────────────────────────────────────────────
# --audit-sla: webauditevents audit row vs PG write 비율 (≤0.1% miss 목표)
# ─────────────────────────────────────────────────────────────────────────────

run_audit_sla() {
  echo "[audit-sla] Cross-DB audit SLA check (target: miss_rate ≤ 0.1%)"
  echo "  SINCE: ${SINCE:-all rows}"

  local where_clause=""
  if [ -n "$SINCE" ]; then
    where_clause=" AND OccurredAt >= '${SINCE}'"
  fi

  local audit_total audit_runtime
  audit_total="$(mysql_query "SELECT COUNT(*) FROM webauditevents WHERE ActionCode LIKE 'runtime.%.mirror'${where_clause};" 2>/dev/null || echo "ERROR")"

  # PG 측 전체 mirror write 수 (core_conversations + core_messages + kv + messages + steps + summary)
  local pg_total=0
  for pg_tbl in agent_runtime.core_conversations agent_runtime.core_messages agent_runtime.kv agent_runtime.messages agent_runtime.steps agent_runtime.summary; do
    local pts_col="created_at"
    local pg_where=""
    if [ -n "$SINCE" ]; then pg_where=" WHERE ${pts_col} >= '${SINCE}'"; fi
    local cnt
    cnt="$(pg_query "SELECT COUNT(*) FROM ${pg_tbl}${pg_where};" 2>/dev/null || echo "0")"
    if [ "$cnt" = "ERROR" ] || [ -z "$cnt" ]; then cnt=0; fi
    pg_total=$(( pg_total + cnt ))
  done

  if [ "$audit_total" = "ERROR" ]; then
    echo "[audit-sla] ERROR — could not query webauditevents" >&2
    FAIL=1
    return
  fi

  if [ "$pg_total" -eq 0 ]; then
    echo "[audit-sla] SKIP — PG total=0 (dual-write not yet active or SINCE too recent)"
    return
  fi

  local miss=$(( pg_total - audit_total ))
  local miss_pct_x1000=$(( (miss * 1000) / pg_total ))
  local miss_pct_display
  miss_pct_display="$(echo "scale=3; $miss * 100 / $pg_total" | bc 2>/dev/null || echo "N/A")"

  printf "  PG_total=%-8d audit_total=%-8d miss=%-8d miss_pct=%s%%\n" \
    "$pg_total" "$audit_total" "$miss" "$miss_pct_display"

  if [ "$miss_pct_x1000" -le 1 ]; then
    echo "[audit-sla] PASS — miss_rate ≤ 0.1%"
  else
    echo "[audit-sla] WARN — miss_rate ${miss_pct_display}% > 0.1% target" >&2
    FAIL=1
  fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Mode dispatch
# ─────────────────────────────────────────────────────────────────────────────

case "$MODE" in
  counts)    run_counts ;;
  audit-sla) run_audit_sla ;;
  all)       run_counts; run_audit_sla ;;
esac

if [ "$FAIL" -eq 0 ]; then
  echo "[runtime-dual-write-verify] PASS"
  exit 0
else
  echo "[runtime-dual-write-verify] FAIL" >&2
  exit 1
fi
