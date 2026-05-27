#!/usr/bin/env bash
# agent-runtime-measure-baseline.sh — AR-M-1 phase: 6 agent runtime 테이블 사전 baseline 측정 (read-only)
#
# 본 스크립트는 docs/MIGRATION_AGENT_MEMORY_TO_PG.md Phase 2 AR-M-1 cycle 의 산출물이다.
# 후속 AR-M0~AR-M5 cycle 의 회귀 판정 baseline 을 정량 측정으로 확보한다.
#
# 측정 항목:
#   --rows     6 runtime 테이블 row count + DATA_LENGTH + AUTO_INCREMENT
#   --schema   각 테이블의 컬럼 목록 + PK + 인덱스 (DDL summary)
#   --callsites read/write call site 인벤토리 (grep 기반)
#   --fk       FK 관계 분석 (agentmemorykv PK 정합 포함)
#   --kv       AgentMemoryKv conversation_id scoping 분포
#   --all      위 5종 모두 실행 후 단일 JSON artifact 로 저장
#
# Usage:
#   bin/agent-runtime-measure-baseline.sh --all [--out <path>]
#   bin/agent-runtime-measure-baseline.sh --rows
#   bin/agent-runtime-measure-baseline.sh --schema
#   bin/agent-runtime-measure-baseline.sh --callsites
#   bin/agent-runtime-measure-baseline.sh --fk
#   bin/agent-runtime-measure-baseline.sh --kv
#
# Defaults:
#   --container repo-mysql-1
#   --db        agent_memory
#   --password  MYSQL_ROOT_PASSWORD (env var name, value extracted from main worktree .env)
#   --out       artifacts/shared/agent-runtime-baseline-$(date -I).json

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

MAIN_REPO="${WRAPPER_ROOT}/repo"
ENV_FILE="${MAIN_REPO}/.env"

# Default params
CONTAINER="repo-mysql-1"
DB="agent_memory"
PASSWORD_VAR="MYSQL_ROOT_PASSWORD"
OUT_DEFAULT="${WRAPPER_ROOT}/artifacts/shared/agent-runtime-baseline-$(date -I).json"
OUT=""

MODE_ROWS=0
MODE_SCHEMA=0
MODE_CALLSITES=0
MODE_FK=0
MODE_KV=0
MODE_ALL=0

usage() {
  cat >&2 <<'EOF'
Usage:
  bin/agent-runtime-measure-baseline.sh --all [--out <path>]
  bin/agent-runtime-measure-baseline.sh --rows
  bin/agent-runtime-measure-baseline.sh --schema
  bin/agent-runtime-measure-baseline.sh --callsites
  bin/agent-runtime-measure-baseline.sh --fk
  bin/agent-runtime-measure-baseline.sh --kv
EOF
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)       MODE_ALL=1; MODE_ROWS=1; MODE_SCHEMA=1; MODE_CALLSITES=1; MODE_FK=1; MODE_KV=1; shift ;;
    --rows)      MODE_ROWS=1; shift ;;
    --schema)    MODE_SCHEMA=1; shift ;;
    --callsites) MODE_CALLSITES=1; shift ;;
    --fk)        MODE_FK=1; shift ;;
    --kv)        MODE_KV=1; shift ;;
    --out)       OUT="$2"; shift 2 ;;
    --container) CONTAINER="$2"; shift 2 ;;
    --db)        DB="$2"; shift 2 ;;
    --password)  PASSWORD_VAR="$2"; shift 2 ;;
    *) usage ;;
  esac
done

if [[ $((MODE_ROWS + MODE_SCHEMA + MODE_CALLSITES + MODE_FK + MODE_KV)) -eq 0 ]]; then
  usage
fi

if [ -z "$OUT" ]; then OUT="$OUT_DEFAULT"; fi

# Extract password from .env
DB_PASS=""
if [ -f "$ENV_FILE" ]; then
  DB_PASS=$(grep -E "^${PASSWORD_VAR}=" "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"' || true)
fi
if [ -z "$DB_PASS" ]; then
  DB_PASS="${!PASSWORD_VAR:-}"
fi
if [ -z "$DB_PASS" ]; then
  echo "ERROR: cannot resolve DB password from ${ENV_FILE} or env var ${PASSWORD_VAR}" >&2
  exit 1
fi

mysql_exec() {
  docker exec "$CONTAINER" mysql -uroot "-p${DB_PASS}" -D "$DB" --batch --silent "$@" 2>/dev/null
}

RUNTIME_TABLES="agentcoreconversations agentcoremessages agentmemorykv agentmemorymessages agentmemorysteps agentmemorysummary"

# ---- rows ----
measure_rows() {
  echo "[rows]" >&2
  mysql_exec -e "
SELECT TABLE_NAME, TABLE_ROWS, DATA_LENGTH, INDEX_LENGTH, AUTO_INCREMENT
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = '${DB}'
  AND TABLE_NAME IN ('agentcoreconversations','agentcoremessages','agentmemorykv','agentmemorymessages','agentmemorysteps','agentmemorysummary')
ORDER BY TABLE_NAME
"
  echo "--- exact counts ---" >&2
  mysql_exec -e "
SELECT 'agentcoreconversations' as tbl, COUNT(*) as cnt FROM agentcoreconversations
UNION ALL SELECT 'agentcoremessages', COUNT(*) FROM agentcoremessages
UNION ALL SELECT 'agentmemorykv', COUNT(*) FROM agentmemorykv
UNION ALL SELECT 'agentmemorymessages', COUNT(*) FROM agentmemorymessages
UNION ALL SELECT 'agentmemorysteps', COUNT(*) FROM agentmemorysteps
UNION ALL SELECT 'agentmemorysummary', COUNT(*) FROM agentmemorysummary
"
}

# ---- schema ----
measure_schema() {
  echo "[schema]" >&2
  for tbl in $RUNTIME_TABLES; do
    echo "--- ${tbl} ---" >&2
    mysql_exec -e "DESCRIBE ${tbl}"
  done
}

# ---- callsites ----
measure_callsites() {
  echo "[callsites]" >&2
  local src_root="${MAIN_REPO}/unit/feature-0002-agent-core/src"
  local web_root="${MAIN_REPO}/unit/feature-0003-agent-web-ui/src"
  local pattern="AgentCoreConversations|AgentCoreMessages|AgentMemoryKv|AgentMemoryMessages|AgentMemorySteps|AgentMemorySummary|agentcoreconversations|agentcoremessages|agentmemorykv|agentmemorymessages|agentmemorysteps|agentmemorysummary"

  echo "=== feature-0002-agent-core/src ===" >&2
  grep -rn -E "$pattern" "${src_root}" --include="*.py" 2>/dev/null | \
    grep -v "^Binary\|\.pyc" | \
    sed 's|'"${MAIN_REPO}"'/||' || true

  echo "=== feature-0003-agent-web-ui/src ===" >&2
  grep -rn -E "$pattern" "${web_root}" --include="*.py" 2>/dev/null | \
    grep -v "^Binary\|\.pyc" | \
    sed 's|'"${MAIN_REPO}"'/||' || true
}

# ---- fk ----
measure_fk() {
  echo "[fk]" >&2
  mysql_exec -e "
SELECT TABLE_NAME, COLUMN_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = '${DB}'
  AND REFERENCED_TABLE_NAME IS NOT NULL
  AND TABLE_NAME IN ('agentcoreconversations','agentcoremessages','agentmemorykv','agentmemorymessages','agentmemorysteps','agentmemorysummary')
ORDER BY TABLE_NAME
"
  echo "--- agentmemorykv PK sample ---" >&2
  mysql_exec -e "SELECT ConversationId, \`Key\`, LENGTH(Value) as value_len FROM agentmemorykv LIMIT 10"
}

# ---- kv ----
measure_kv() {
  echo "[kv]" >&2
  mysql_exec -e "
SELECT ConversationId,
       COUNT(*) as key_count
FROM agentmemorykv
GROUP BY ConversationId
ORDER BY key_count DESC
LIMIT 15
"
  echo "--- unique keys sample ---" >&2
  mysql_exec -e "SELECT DISTINCT \`Key\` FROM agentmemorykv ORDER BY \`Key\` LIMIT 30"
}

# Run selected modes
if [[ $MODE_ROWS -eq 1 ]];      then measure_rows;      fi
if [[ $MODE_SCHEMA -eq 1 ]];    then measure_schema;    fi
if [[ $MODE_CALLSITES -eq 1 ]]; then measure_callsites; fi
if [[ $MODE_FK -eq 1 ]];        then measure_fk;        fi
if [[ $MODE_KV -eq 1 ]];        then measure_kv;        fi

if [[ $MODE_ALL -eq 1 ]]; then
  mkdir -p "$(dirname "$OUT")"
  echo "Saving baseline to: $OUT" >&2

  # exact counts
  conv_cnt=$(mysql_exec -e "SELECT COUNT(*) FROM agentcoreconversations" | tail -1)
  msg_cnt=$(mysql_exec -e "SELECT COUNT(*) FROM agentcoremessages" | tail -1)
  kv_cnt=$(mysql_exec -e "SELECT COUNT(*) FROM agentmemorykv" | tail -1)
  mmsg_cnt=$(mysql_exec -e "SELECT COUNT(*) FROM agentmemorymessages" | tail -1)
  steps_cnt=$(mysql_exec -e "SELECT COUNT(*) FROM agentmemorysteps" | tail -1)
  summary_cnt=$(mysql_exec -e "SELECT COUNT(*) FROM agentmemorysummary" | tail -1)
  total=$((conv_cnt + msg_cnt + kv_cnt + mmsg_cnt + steps_cnt + summary_cnt))

  # data lengths
  dl_info=$(mysql_exec -e "SELECT TABLE_NAME, DATA_LENGTH FROM information_schema.TABLES WHERE TABLE_SCHEMA='${DB}' AND TABLE_NAME IN ('agentcoreconversations','agentcoremessages','agentmemorykv','agentmemorymessages','agentmemorysteps','agentmemorysummary') ORDER BY TABLE_NAME")

  # insert rates
  rate_msg=$(mysql_exec -e "SELECT ROUND(COUNT(*) / GREATEST(DATEDIFF(MAX(created_at), MIN(created_at)), 1), 2) FROM agentcoremessages" | tail -1)
  rate_mmsg=$(mysql_exec -e "SELECT ROUND(COUNT(*) / GREATEST(DATEDIFF(MAX(CreatedAt), MIN(CreatedAt)), 1), 2) FROM agentmemorymessages" | tail -1)
  rate_steps=$(mysql_exec -e "SELECT ROUND(COUNT(*) / GREATEST(DATEDIFF(MAX(CreatedAt), MIN(CreatedAt)), 1), 2) FROM agentmemorysteps" | tail -1)

  # callsite counts
  src_root="${MAIN_REPO}/unit/feature-0002-agent-core/src"
  web_root="${MAIN_REPO}/unit/feature-0003-agent-web-ui/src"
  pattern="AgentCoreConversations|AgentCoreMessages|AgentMemoryKv|AgentMemoryMessages|AgentMemorySteps|AgentMemorySummary"
  core_hits=$(grep -rn -E "$pattern" "${src_root}" --include="*.py" 2>/dev/null | grep -v "^Binary\|\.pyc" | wc -l || true)
  web_hits=$(grep -rn -E "$pattern" "${web_root}" --include="*.py" 2>/dev/null | grep -v "^Binary\|\.pyc" | wc -l || true)

  # kv scoping
  global_kv=$(mysql_exec -e "SELECT COUNT(*) FROM agentmemorykv WHERE ConversationId='__global__'" | tail -1)
  conv_kv=$(mysql_exec -e "SELECT COUNT(*) FROM agentmemorykv WHERE ConversationId<>'__global__'" | tail -1)

  measured_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  kernel=$(uname -srm)
  mysql_ver=$(docker exec "$CONTAINER" mysql --version 2>/dev/null | head -1 || echo "unknown")

  cat > "$OUT" <<JSONEOF
{
  "meta": {
    "task_cycle": "AR-M-1",
    "plan_reference": "docs/MIGRATION_AGENT_MEMORY_TO_PG.md Phase 2",
    "measured_at": "${measured_at}",
    "host_kernel": "${kernel}",
    "mysql_container": "${CONTAINER}",
    "mysql_version": "${mysql_ver}",
    "agent_memory_db": "${DB}"
  },
  "rows": {
    "AgentCoreConversations": ${conv_cnt},
    "AgentCoreMessages": ${msg_cnt},
    "AgentMemoryKv": ${kv_cnt},
    "AgentMemoryMessages": ${mmsg_cnt},
    "AgentMemorySteps": ${steps_cnt},
    "AgentMemorySummary": ${summary_cnt},
    "total": ${total}
  },
  "insert_rate_per_day": {
    "AgentCoreMessages": ${rate_msg},
    "AgentMemoryMessages": ${rate_mmsg},
    "AgentMemorySteps": ${rate_steps},
    "note": "agentcoreconversations + agentmemorykv + agentmemorysummary: rare write, rate ~0"
  },
  "callsites": {
    "feature_0002_agent_core_src": ${core_hits},
    "feature_0003_agent_web_ui_src": ${web_hits},
    "note": "grep -rn pattern hits for 6 runtime table names in Python source files"
  },
  "kv_scoping": {
    "global_scope_rows": ${global_kv},
    "conversation_scoped_rows": ${conv_kv},
    "pk_schema": "PRIMARY KEY (ConversationId, Key)",
    "note": "__global__ scope rows used for insight_worker state, schema fingerprints, etc."
  },
  "fk_analysis": {
    "explicit_fk_constraints": 0,
    "implicit_fk": "agentcoremessages.conversation_id -> agentcoreconversations.conversation_id (no FOREIGN KEY constraint — application-level only)",
    "agentmemorymessages_conv_id": "agentmemorymessages.ConversationId (no FK constraint)",
    "agentmemorysteps_conv_id": "agentmemorysteps.ConversationId (no FK constraint)",
    "agentmemorykv_pk": "PRIMARY KEY (ConversationId, Key) — composite, UPSERT pattern",
    "agentmemorysummary_pk": "PRIMARY KEY (ConversationId) — one row per conversation",
    "note": "MySQL agent_memory has 0 explicit FK constraints across 6 runtime tables. PG DDL will use FOREIGN KEY for data integrity."
  },
  "pg_target": {
    "schema": "agent_runtime",
    "database": "agent_kb",
    "tables": [
      "core_conversations",
      "core_messages",
      "kv",
      "messages",
      "steps",
      "summary"
    ]
  }
}
JSONEOF

  echo "BASELINE SAVED: $OUT" >&2
  echo "total runtime rows: ${total}" >&2
fi
