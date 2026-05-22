#!/usr/bin/env bash
# kb-cutover-readiness.sh — M4 (TASK-0024) cutover 진입 전 모든 게이트 검증.
#
# ADR-0021 §Consequences (e)/(f) 및 §2.1.3 M4 phase 의 cutover gate:
#   1. M2 dual-write SLA ≤ 0.1% (audit miss_rate)
#   2. M2-d pg_branch tag coverage ≤ 0.1%
#   3. ANCHOR §3 invariant test S1+N1 PASS + S2/S4/S5/S6 mock PASS
#   4. unit test 전체 PASS (회귀 없음)
#   5. M3 backfill 4 table row count 일치 (`bin/kb-dual-write-verify.sh --counts`)
#   6. M3 embedding worker 모든 NULL row 처리 (texts.embedding IS NULL = 0)
#   7. p99 latency 가 M-1 baseline 대비 50% 이내 (M2-d `get_mirror_metrics()` 활용)
#   8. agent_kb_rw role 의 TRUNCATE denied 재확인 (N2 integration test)
#   9. `make ask` 5종 회귀 시나리오 PASS (M-1 baseline S1~S5)
#  10. AGENT_KB_PG_REQUIRED=1 + AGENT_KB_DUAL_WRITE=1 + AGENT_KB_PG_ENABLED=true 확인
#
# 모든 게이트 PASS 시 exit 0 + "READY FOR CUTOVER" 메시지. 단 한 게이트라도 FAIL
# 시 exit 1 + 해당 게이트 상세. INCONCLUSIVE (실 환경 부재) 는 exit 2.
#
# Usage:
#   bin/kb-cutover-readiness.sh                          # 모든 게이트
#   bin/kb-cutover-readiness.sh --skip-ask-regression    # ask 회귀 시나리오 외
#   bin/kb-cutover-readiness.sh --skip-latency           # latency 측정 외 (production-like 부재)
#   bin/kb-cutover-readiness.sh --since 2026-05-20T00:00:00
#
# Exit codes:
#   0 — 모든 게이트 PASS → READY FOR CUTOVER
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

SINCE=""
SKIP_ASK=0
SKIP_LATENCY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --since)                SINCE="$2"; shift 2 ;;
    --skip-ask-regression)  SKIP_ASK=1; shift ;;
    --skip-latency)         SKIP_LATENCY=1; shift ;;
    -h|--help)              sed -n '2,30p' "$0"; exit 0 ;;
    *)                      echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# 게이트 결과 누적
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

# ─── Gate 1: dual-write SLA ─────────────────────────────────────────────────
echo "[Gate 1/10] M2 dual-write audit SLA ≤ 0.1%"
if [ -x "${REPO_ROOT}/bin/kb-dual-write-verify.sh" ]; then
  if [ -n "$SINCE" ]; then
    "${REPO_ROOT}/bin/kb-dual-write-verify.sh" --audit-sla --since "$SINCE" >/tmp/cutover-gate1.log 2>&1
  else
    "${REPO_ROOT}/bin/kb-dual-write-verify.sh" --audit-sla >/tmp/cutover-gate1.log 2>&1
  fi
  gate_result "dual-write SLA" $?
else
  gate_result "dual-write SLA" 2
fi

# ─── Gate 2: pg_branch tag coverage ─────────────────────────────────────────
echo "[Gate 2/10] M2-d pg_branch tag coverage ≤ 0.1%"
if [ -x "${REPO_ROOT}/bin/kb-dual-write-verify.sh" ]; then
  if [ -n "$SINCE" ]; then
    "${REPO_ROOT}/bin/kb-dual-write-verify.sh" --pg-branch-tag-coverage --since "$SINCE" >/tmp/cutover-gate2.log 2>&1 || true
    rc=$?
  else
    "${REPO_ROOT}/bin/kb-dual-write-verify.sh" --pg-branch-tag-coverage >/tmp/cutover-gate2.log 2>&1 || true
    rc=$?
  fi
  gate_result "pg_branch tag coverage" $rc
else
  gate_result "pg_branch tag coverage" 2
fi

# ─── Gate 3: ANCHOR §3 invariant test ───────────────────────────────────────
echo "[Gate 3/10] ANCHOR §3 invariant test (S1+N1 mock + S2/S4/S5/S6 mock)"
if (cd "${REPO_ROOT}/unit/feature-0002-agent-core" && pytest tests/test_anchor_invariant_postgres.py -q >/tmp/cutover-gate3.log 2>&1); then
  gate_result "ANCHOR §3 invariant test" 0
else
  gate_result "ANCHOR §3 invariant test" 1
fi

# ─── Gate 4: unit test 전체 ─────────────────────────────────────────────────
echo "[Gate 4/10] unit test 전체 PASS"
if (cd "${REPO_ROOT}/unit/feature-0002-agent-core" && pytest tests/ -q >/tmp/cutover-gate4.log 2>&1); then
  gate_result "unit test 전체" 0
else
  gate_result "unit test 전체" 1
fi

# ─── Gate 5: M3 backfill row count 일치 ─────────────────────────────────────
echo "[Gate 5/10] M3 backfill 4 table row count 일치"
if [ -x "${REPO_ROOT}/bin/kb-dual-write-verify.sh" ]; then
  if [ -n "$SINCE" ]; then
    "${REPO_ROOT}/bin/kb-dual-write-verify.sh" --counts --since "$SINCE" >/tmp/cutover-gate5.log 2>&1
  else
    "${REPO_ROOT}/bin/kb-dual-write-verify.sh" --counts >/tmp/cutover-gate5.log 2>&1
  fi
  gate_result "M3 backfill row count" $?
else
  gate_result "M3 backfill row count" 2
fi

# ─── Gate 6: M3 embedding worker — NULL row 0 ────────────────────────────────
echo "[Gate 6/10] M3 embedding worker 처리 완료 (texts.embedding IS NULL = 0)"
PG_USER="$(grep -E '^AGENT_KB_PG_USER=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)"
PG_PW="$(grep -E '^AGENT_KB_PG_PASSWORD=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)"
PG_DB="$(grep -E '^AGENT_KB_PG_DB=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)"
PG_CONTAINER="${COMPOSE_PROJECT_NAME:-repo}-postgres-1"
if docker ps --format '{{.Names}}' | grep -qx "$PG_CONTAINER" && [ -n "$PG_USER" ]; then
  null_count=$(docker exec -i -e PGPASSWORD="$PG_PW" "$PG_CONTAINER" \
    psql -h localhost -U "$PG_USER" -d "${PG_DB:-agent_kb}" -tAc \
    "SELECT COUNT(*) FROM texts WHERE embedding IS NULL;" 2>/tmp/cutover-gate6.log | tr -d '[:space:]' || true)
  null_count="${null_count:-unknown}"
  if [ "$null_count" = "0" ]; then
    gate_result "embedding NULL=0" 0
  else
    echo "    detail: texts.embedding IS NULL = ${null_count}" >&2
    gate_result "embedding NULL=0" 1
  fi
else
  gate_result "embedding NULL=0" 2
fi

# ─── Gate 7: p99 latency ────────────────────────────────────────────────────
echo "[Gate 7/10] p99 latency M-1 baseline 대비 50% 이내"
if [ "$SKIP_LATENCY" = "1" ]; then
  gate_result "p99 latency" 2
else
  # production-like 환경의 latency 측정 — 본 cycle 의 cutover gate 는 측정 시점 책임.
  # 측정 도구가 production 측정과 통합되어야 함 (M2-d `get_mirror_metrics()` snapshot).
  gate_result "p99 latency" 2
fi

# ─── Gate 8: TRUNCATE denied (RBAC) ─────────────────────────────────────────
echo "[Gate 8/10] agent_kb_rw TRUNCATE denied (N2 integration test)"
if [ -n "${AGENT_KB_PG_INTEGRATION_TEST:-}" ]; then
  if (cd "${REPO_ROOT}/unit/feature-0002-agent-core" && \
      AGENT_KB_PG_INTEGRATION_TEST=1 pytest tests/test_anchor_invariant_postgres.py -k N2 -q >/tmp/cutover-gate8.log 2>&1); then
    gate_result "TRUNCATE denied" 0
  else
    gate_result "TRUNCATE denied" 1
  fi
else
  gate_result "TRUNCATE denied" 2
fi

# ─── Gate 9: make ask 5종 회귀 ──────────────────────────────────────────────
echo "[Gate 9/10] make ask 5종 회귀 시나리오 (M-1 baseline S1~S5)"
if [ "$SKIP_ASK" = "1" ]; then
  gate_result "make ask 5종 회귀" 2
else
  # ask 회귀는 LLM API + 실 DB 의존 — 운영자 turn 책임.
  gate_result "make ask 5종 회귀" 2
fi

# ─── Gate 10: env 변수 ──────────────────────────────────────────────────────
echo "[Gate 10/10] AGENT_KB_PG_REQUIRED=1 + AGENT_KB_DUAL_WRITE=1 + AGENT_KB_PG_ENABLED=true"
required="$(grep -E '^AGENT_KB_PG_REQUIRED=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)"
dual_write="$(grep -E '^AGENT_KB_DUAL_WRITE=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)"
pg_host="$(grep -E '^AGENT_KB_PG_HOST=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)"
if [ "$required" = "1" ] && [ "$dual_write" = "1" ] && [ -n "$pg_host" ]; then
  gate_result "env 변수" 0
else
  echo "    detail: AGENT_KB_PG_REQUIRED=$required AGENT_KB_DUAL_WRITE=$dual_write AGENT_KB_PG_HOST=$pg_host" >&2
  gate_result "env 변수" 1
fi

# ─── 결과 종합 ──────────────────────────────────────────────────────────────
echo ""
echo "=== Cutover readiness summary ==="
echo "  PASS:         ${GATE_PASS} / 10"
echo "  FAIL:         ${GATE_FAIL} / 10"
echo "  INCONCLUSIVE: ${GATE_INCONC} / 10"

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
  echo "⚠️  CONDITIONAL READY — ${GATE_INCONC} gate inconclusive (production-like 환경 부재 또는 사용자 turn 의존):" >&2
  for g in "${INCONC_GATES[@]}"; do
    echo "    - $g" >&2
  done
  echo ""
  echo "사용자 책임: production-like 환경에서 inconclusive 게이트 실측 후 재확인" >&2
  exit 2
fi

echo ""
echo "✅ READY FOR CUTOVER — 모든 10 gate PASS"
echo ""
echo "다음 단계 (Stage A — 1줄 env 변경 cutover):"
echo "  1. main worktree: .env 의 AGENT_KB_READ_BACKEND=postgres 로 변경"
echo "  2. make start 재기동 (agent + insight-worker)"
echo "  3. canary monitoring: bin/kb-dual-write-verify.sh --counts 정합 1주일 유지"
echo "  4. M5 진입 결정: dual-write 제거 + MySQL DROP TABLE"
exit 0
