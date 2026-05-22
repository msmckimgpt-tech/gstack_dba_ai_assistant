#!/usr/bin/env bash
# kb-dual-write-stress.sh — TASK-0015 §2.1.3 M2 dual-write phase 의 synthetic load.
#
# outside-voice review Blocker B-3 의 권고 흡수: "1주일 dual-write 의 통계적 power
# 부족 — synthetic write load 게이트 필요". M-1 baseline (`artifacts/shared/
# kb-baseline-2026-05-20.json`) 의 KB write 빈도가 매우 낮아 (cycle 당 fact 28→30)
# 1주일 wait 의 신뢰도가 calendar comfort 에 가까움. 본 script 가 강제 trigger:
#
# - **insight cycle 3회 강제 실행** — `run_insight_cycle()` 직접 호출. insight-worker
#   container 의 정상 가동 중 cycle 외 추가 trigger.
# - **`make ask` 5종 시나리오 5회** — kb-measure-baseline.sh 의 --latency mode 와 동일
#   시나리오. 5 × 5 = 25 ask 실행. 약 12분 + LLM API cost.
#
# M2-c (TASK-0021): 실 호출 body 구현. dual-write 활성 환경에서 audit miss_rate
# 검증 직전 강제 부하 trigger 로 사용.
#
# Usage:
#   bin/kb-dual-write-stress.sh                # default — insight 3회 + ask 5×5
#   bin/kb-dual-write-stress.sh --insight-cycles 1 --ask-iterations 2
#   bin/kb-dual-write-stress.sh --dry-run      # 명령만 출력, 실 호출 안 함
#
# Exit codes:
#   0 — synthetic load 완료 (모든 단계 성공)
#   1 — 일부 실행 실패 (stderr 사유)
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
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-repo}"

INSIGHT_CYCLES=3
ASK_ITERATIONS=5
DRY_RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --insight-cycles) INSIGHT_CYCLES="$2"; shift 2 ;;
    --ask-iterations) ASK_ITERATIONS="$2"; shift 2 ;;
    --dry-run)        DRY_RUN=1; shift ;;
    -h|--help)        sed -n '2,25p' "$0"; exit 0 ;;
    *)                echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# 5 시나리오 (M-1 baseline 의 S1~S5)
SCENARIOS=(
  "최근 7일간 가입한 사용자 수를 알려줘"
  "그 중 PaymentMethod 가 카드인 비율은?"
  "최근에 trend 가 어떻게 되고 있어?"
  "users 관련 테이블이 뭐가 있어?"
  "관리자 권한이 있는 사용자 중 마지막 로그인이 7일 이상 지난 사용자는 누구야?"
)

run_or_print() {
  if [ "$DRY_RUN" = "1" ]; then
    echo "[DRY-RUN] $*"
  else
    "$@"
  fi
}

FAILURES=0

trigger_insight_cycles() {
  echo "[STEP] insight cycle x ${INSIGHT_CYCLES}"
  local insight_container="${COMPOSE_PROJECT_NAME}-insight-worker-1"
  if [ "$DRY_RUN" != "1" ] && ! docker ps --format '{{.Names}}' | grep -qx "$insight_container"; then
    echo "[WARN] container '${insight_container}' not running — fallback to docker compose run" >&2
    insight_container=""
  fi
  for i in $(seq 1 "$INSIGHT_CYCLES"); do
    echo "[INSIGHT] cycle ${i}/${INSIGHT_CYCLES}"
    if [ -n "$insight_container" ]; then
      run_or_print docker exec "$insight_container" \
        python -c "from agent_core import run_insight_cycle; print(run_insight_cycle('stress-${i}'))" \
        || { echo "[FAIL] insight cycle ${i}" >&2; FAILURES=$((FAILURES + 1)); }
    else
      run_or_print docker compose -f "${MAIN_REPO_ROOT}/docker-compose.yml" \
        -p "$COMPOSE_PROJECT_NAME" run --rm --remove-orphans insight-worker \
        python -c "from agent_core import run_insight_cycle; print(run_insight_cycle('stress-${i}'))" \
        || { echo "[FAIL] insight cycle ${i}" >&2; FAILURES=$((FAILURES + 1)); }
    fi
  done
}

trigger_ask_iterations() {
  echo "[STEP] ask iterations: ${ASK_ITERATIONS} × ${#SCENARIOS[@]} scenarios = $((ASK_ITERATIONS * ${#SCENARIOS[@]})) total"
  local compose_file="${MAIN_REPO_ROOT}/docker-compose.yml"
  for iter in $(seq 1 "$ASK_ITERATIONS"); do
    local sidx=0
    for question in "${SCENARIOS[@]}"; do
      sidx=$((sidx + 1))
      echo "[ASK] iter=${iter}/${ASK_ITERATIONS} S${sidx}/${#SCENARIOS[@]}: ${question}"
      run_or_print docker compose -f "$compose_file" -p "$COMPOSE_PROJECT_NAME" \
        run --rm --remove-orphans agent "$question" \
        || { echo "[FAIL] iter=${iter} S${sidx}" >&2; FAILURES=$((FAILURES + 1)); }
    done
  done
}

trigger_insight_cycles
trigger_ask_iterations

echo ""
echo "kb-dual-write-stress 완료"
echo "  insight cycles: ${INSIGHT_CYCLES}"
echo "  ask iterations: ${ASK_ITERATIONS} × ${#SCENARIOS[@]} = $((ASK_ITERATIONS * ${#SCENARIOS[@]}))"
echo "  failures: ${FAILURES}"
if [ "$FAILURES" -gt 0 ]; then
  echo "FAIL — 일부 stress step 실패" >&2
  exit 1
fi
exit 0
