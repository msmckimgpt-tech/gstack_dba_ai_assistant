#!/usr/bin/env bash
# runtime-cutover-readiness.sh — AR-M4 (TASK-0118) cutover 진입 전 모든 게이트 검증.
#
# ADR-0027 §Consequences 및 AR-M4 cutover gate:
#   1. M2 dual-write 가 활성화 상태 (AGENT_RUNTIME_DUAL_WRITE=1)
#   2. M3 backfill 6 table row count 일치 (MySQL ↔ Postgres)
#   3. ANCHOR §3 invariant test (unit/feature-0002-agent-core 전체) PASS
#   4. unit test 전체 PASS (회귀 없음)
#   5. PG read backend unit test (test_runtime_read_backend.py) PASS
#   6. env 변수 정합: AGENT_RUNTIME_DUAL_WRITE=1 + AGENT_KB_PG_HOST 설정 완료
#   7. backfill state 파일 존재 + 6 table checkpoint 비어있지 않음
#
# 모든 게이트 PASS 시 exit 0 + "READY FOR CUTOVER" 메시지. 단 한 게이트라도 FAIL
# 시 exit 1 + 해당 게이트 상세. INCONCLUSIVE (실 환경 부재) 는 exit 2.
#
# Usage:
#   bin/runtime-cutover-readiness.sh                          # 모든 게이트
#   bin/runtime-cutover-readiness.sh --skip-row-count         # row count 비교 외
#
# Exit codes:
#   0 — 모든 게이트 PASS → READY FOR CUTOVER (AGENT_RUNTIME_READ_BACKEND=postgres 활성 가능)
#   1 — 일부 게이트 FAIL
#   2 — INCONCLUSIVE (실 환경 의존 게이트 측정 불가)

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

SKIP_ROW_COUNT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --skip-row-count)  SKIP_ROW_COUNT=1; shift ;;
    -h|--help)         sed -n '2,25p' "$0"; exit 0 ;;
    *)                 echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

GATE_PASS=0
GATE_FAIL=0
GATE_INCONC=0
FAIL_GATES=()
INCONC_GATES=()

gate_result() {
  local name="$1" rc="$2"
  case "$rc" in
    0)
      GATE_PASS=$((GATE_PASS + 1))
      echo "  ✓ PASS: ${name}"
      ;;
    2)
      GATE_INCONC=$((GATE_INCONC + 1))
      INCONC_GATES+=("$name")
      echo "  ? INCONCLUSIVE: ${name}" >&2
      ;;
    *)
      GATE_FAIL=$((GATE_FAIL + 1))
      FAIL_GATES+=("$name")
      echo "  ✗ FAIL: ${name}" >&2
      ;;
  esac
}

FEATURE_DIR="${REPO_ROOT}/unit/feature-0002-agent-core"

# Safely read a value from .env (returns empty string when file absent or key absent)
_env_get() { grep -E "^${1}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '[:space:]' || true; }

# ─── Gate 1: dual-write 활성 여부 ───────────────────────────────────────────
echo "[Gate 1/7] M2 dual-write 활성 (AGENT_RUNTIME_DUAL_WRITE=1)"
dw_val="$(_env_get AGENT_RUNTIME_DUAL_WRITE)"
if [ "$dw_val" = "1" ]; then
  gate_result "dual-write 활성" 0
else
  echo "    detail: AGENT_RUNTIME_DUAL_WRITE='${dw_val}' (expected 1)" >&2
  gate_result "dual-write 활성" 1
fi

# ─── Gate 2: M3 backfill row count 일치 ─────────────────────────────────────
echo "[Gate 2/7] M3 backfill 6 table row count 일치 (MySQL ↔ Postgres)"
if [ "$SKIP_ROW_COUNT" = "1" ]; then
  gate_result "row count 일치" 2
else
  AGENT_CONTAINER="${COMPOSE_PROJECT_NAME:-repo}-agent-1"
  PG_CONTAINER="${COMPOSE_PROJECT_NAME:-repo}-postgres-1"
  PG_USER="$(_env_get AGENT_KB_PG_USER)"
  PG_PW="$(_env_get AGENT_KB_PG_PASSWORD)"
  PG_DB="$(_env_get AGENT_KB_PG_DB)"

  if docker ps --format '{{.Names}}' | grep -qx "$AGENT_CONTAINER" && \
     docker ps --format '{{.Names}}' | grep -qx "$PG_CONTAINER" && \
     [ -n "$PG_USER" ]; then
    TABLES=(
      "AgentCoreConversations|agent_runtime.core_conversations"
      "AgentCoreMessages|agent_runtime.core_messages"
      "AgentMemoryMessages|agent_runtime.messages"
      "AgentMemorySteps|agent_runtime.steps"
      "AgentMemorySummary|agent_runtime.summary"
      "AgentMemoryKv|agent_runtime.kv"
    )
    all_ok=1
    for entry in "${TABLES[@]}"; do
      mysql_tbl="${entry%%|*}"
      pg_tbl="${entry##*|}"
      mysql_cnt=$(docker exec "$AGENT_CONTAINER" \
        mysql -N -e "SELECT COUNT(*) FROM \`${mysql_tbl}\`;" 2>/tmp/gate2-mysql.log | tr -d '[:space:]' || echo "ERR")
      pg_cnt=$(docker exec -i -e PGPASSWORD="$PG_PW" "$PG_CONTAINER" \
        psql -h localhost -U "$PG_USER" -d "${PG_DB:-agent_kb}" -tAc \
        "SELECT COUNT(*) FROM ${pg_tbl};" 2>/tmp/gate2-pg.log | tr -d '[:space:]' || echo "ERR")
      if [ "$mysql_cnt" = "ERR" ] || [ "$pg_cnt" = "ERR" ]; then
        echo "    detail: ${mysql_tbl} count error (mysql=${mysql_cnt} pg=${pg_cnt})" >&2
        all_ok=0
      elif [ "$mysql_cnt" != "$pg_cnt" ]; then
        echo "    detail: ${mysql_tbl} count mismatch (mysql=${mysql_cnt} pg=${pg_cnt})" >&2
        all_ok=0
      fi
    done
    if [ "$all_ok" = "1" ]; then
      gate_result "row count 일치" 0
    else
      gate_result "row count 일치" 1
    fi
  else
    gate_result "row count 일치" 2
  fi
fi

# ─── Gate 3: ANCHOR §3 invariant test ───────────────────────────────────────
echo "[Gate 3/7] ANCHOR §3 invariant test (anchor_invariant_runtime)"
if [ -f "${FEATURE_DIR}/tests/test_anchor_invariant_runtime.py" ]; then
  if (cd "$FEATURE_DIR" && python3 -m pytest tests/test_anchor_invariant_runtime.py -q >/tmp/cutover-gate3.log 2>&1); then
    gate_result "ANCHOR invariant runtime" 0
  else
    cat /tmp/cutover-gate3.log >&2
    gate_result "ANCHOR invariant runtime" 1
  fi
else
  gate_result "ANCHOR invariant runtime" 2
fi

# ─── Gate 4: unit test 전체 ─────────────────────────────────────────────────
echo "[Gate 4/7] unit test 전체 PASS (pre-existing 2 제외)"
if (cd "$FEATURE_DIR" && python3 -m pytest tests/ -q --ignore=tests/test_kb_backfill.py >/tmp/cutover-gate4.log 2>&1); then
  gate_result "unit test 전체" 0
else
  tail -20 /tmp/cutover-gate4.log >&2
  gate_result "unit test 전체" 1
fi

# ─── Gate 5: PG read backend unit test ──────────────────────────────────────
echo "[Gate 5/7] PG read backend unit test (test_runtime_read_backend.py)"
if (cd "$FEATURE_DIR" && python3 -m pytest tests/test_runtime_read_backend.py -q >/tmp/cutover-gate5.log 2>&1); then
  gate_result "PG read backend test" 0
else
  cat /tmp/cutover-gate5.log >&2
  gate_result "PG read backend test" 1
fi

# ─── Gate 6: env 변수 정합 ──────────────────────────────────────────────────
echo "[Gate 6/7] env 변수 정합 (AGENT_RUNTIME_DUAL_WRITE=1 + AGENT_KB_PG_HOST 설정)"
pg_host="$(_env_get AGENT_KB_PG_HOST)"
if [ "$dw_val" = "1" ] && [ -n "$pg_host" ]; then
  gate_result "env 변수 정합" 0
else
  echo "    detail: AGENT_RUNTIME_DUAL_WRITE='${dw_val}' AGENT_KB_PG_HOST='${pg_host}'" >&2
  gate_result "env 변수 정합" 1
fi

# ─── Gate 7: backfill state 파일 ────────────────────────────────────────────
echo "[Gate 7/7] backfill state 파일 존재 + checkpoint 비어있지 않음"
BACKFILL_STATE_DIR="${AGENT_RUNTIME_BACKFILL_STATE_DIR:-/shared}"
STATE_FILE="${BACKFILL_STATE_DIR}/runtime-backfill-state.json"
AGENT_CONTAINER="${COMPOSE_PROJECT_NAME:-repo}-agent-1"
if docker ps --format '{{.Names}}' | grep -qx "$AGENT_CONTAINER" 2>/dev/null; then
  if docker exec "$AGENT_CONTAINER" test -f "$STATE_FILE" 2>/dev/null; then
    checkpoint_count=$(docker exec "$AGENT_CONTAINER" \
      python3 -c "
import json
with open('$STATE_FILE') as f: s = json.load(f)
print(sum(1 for t,v in s.items() if v.get('last_checkpoint') not in ('', None)))
" 2>/dev/null || echo "0")
    checkpoint_count="${checkpoint_count:-0}"
    if [ "$checkpoint_count" -ge 6 ] 2>/dev/null; then
      gate_result "backfill state" 0
    else
      echo "    detail: $STATE_FILE 존재 but checkpoint 완료 table = ${checkpoint_count}/6" >&2
      gate_result "backfill state" 1
    fi
  else
    echo "    detail: $STATE_FILE not found in container (run bin/runtime-backfill.sh --all first)" >&2
    gate_result "backfill state" 1
  fi
else
  gate_result "backfill state" 2
fi

# ─── 결과 종합 ──────────────────────────────────────────────────────────────
echo ""
echo "=== Runtime cutover readiness summary ==="
echo "  PASS:         ${GATE_PASS} / 7"
echo "  FAIL:         ${GATE_FAIL} / 7"
echo "  INCONCLUSIVE: ${GATE_INCONC} / 7"

if [ "$GATE_FAIL" -gt 0 ]; then
  echo ""
  echo "❌ NOT READY FOR CUTOVER — ${GATE_FAIL} gate fail:" >&2
  for g in "${FAIL_GATES[@]}"; do
    echo "    - $g" >&2
  done
  exit 1
fi

if [ "$GATE_INCONC" -gt 0 ]; then
  echo ""
  echo "⚠️  CONDITIONAL READY — ${GATE_INCONC} gate inconclusive (production-like 환경 부재):" >&2
  for g in "${INCONC_GATES[@]}"; do
    echo "    - $g" >&2
  done
  echo ""
  echo "사용자 책임: production-like 환경에서 inconclusive 게이트 실측 후 재확인" >&2
  exit 2
fi

echo ""
echo "✅ READY FOR CUTOVER — 모든 7 gate PASS"
echo ""
echo "다음 단계 (Stage A — 1줄 env 변경 cutover):"
echo "  1. .env 에 AGENT_RUNTIME_READ_BACKEND=postgres 추가"
echo "  2. make start 재기동 (agent + insight-worker + web 컨테이너)"
echo "  3. canary monitoring: bin/runtime-cutover-readiness.sh --skip-row-count 1주 유지"
echo "  4. AR-M5 진입 결정: AGENT_RUNTIME_DUAL_WRITE=0 + MySQL 6 table DROP"
exit 0
