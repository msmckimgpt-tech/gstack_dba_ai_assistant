#!/usr/bin/env bash
# runtime-dual-write-stress.sh — AR-M2-c synthetic load for runtime dual-write.
#
# kb-dual-write-stress.sh 패턴 답습 (TASK-0021). dual-write 가 활성화된 환경에서
# synthetic agent ask 를 발행하여 mirror write path 를 강제 exercising.
# runtime-dual-write-verify.sh --audit-sla 실행 직전 부하 생성용.
#
# Usage:
#   bin/runtime-dual-write-stress.sh                     # 5 scenario × 3 iterations
#   bin/runtime-dual-write-stress.sh --iterations 2
#   bin/runtime-dual-write-stress.sh --dry-run           # 명령만 출력, 실 호출 안 함
#
# Exit codes:
#   0 — stress 완료
#   1 — 일부 실행 실패
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

ITERATIONS=3
DRY_RUN=0
LOG_DIR=""

while [ $# -gt 0 ]; do
  case "$1" in
    --iterations)  ITERATIONS="$2"; shift 2 ;;
    --dry-run)     DRY_RUN=1; shift ;;
    --log-dir)     LOG_DIR="$2"; shift 2 ;;
    -h|--help)     sed -n '2,20p' "$0"; exit 0 ;;
    *)             echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ -n "$LOG_DIR" ]; then
  mkdir -p "$LOG_DIR"
  echo "[INFO] per-step logs → $LOG_DIR"
fi

step_log() {
  local sid="$1"; shift
  local msg="$*"
  [ -n "$LOG_DIR" ] && printf '[%s] %s\n' "$(date -Iseconds)" "$msg" >> "${LOG_DIR}/${sid}.log"
  echo "$msg"
}

# agent_runtime 쓰기 경로를 exercising 하는 5가지 쿼리 시나리오
SCENARIOS=(
  "최근 7일간 가입한 사용자 수를 알려줘"
  "users 테이블의 컬럼 목록을 보여줘"
  "가장 최근에 생성된 레코드 3개를 보여줘"
  "전체 row 개수가 가장 많은 테이블 TOP 5 는?"
  "agent_memory 관련 테이블이 있으면 보여줘"
)

run_or_print() {
  if [ "$DRY_RUN" = "1" ]; then
    echo "[DRY-RUN] $*"
  else
    "$@"
  fi
}

FAILURES=0
compose_file="${MAIN_REPO_ROOT}/docker-compose.yml"

echo "[runtime-dual-write-stress] iterations=${ITERATIONS} scenarios=${#SCENARIOS[@]}"
echo "  AGENT_RUNTIME_DUAL_WRITE must be=1 for mirror writes to exercise."

for iter in $(seq 1 "$ITERATIONS"); do
  local_idx=0
  for question in "${SCENARIOS[@]}"; do
    local_idx=$(( local_idx + 1 ))
    step_id="stress-iter${iter}-s${local_idx}"
    step_log "$step_id" "[ask] iter=${iter}/${ITERATIONS} S${local_idx}/${#SCENARIOS[@]}: ${question}"
    run_or_print docker compose -f "$compose_file" -p "$COMPOSE_PROJECT_NAME" \
      run --rm --remove-orphans agent "$question" \
      || { step_log "$step_id" "[FAIL] iter=${iter} S${local_idx}"; FAILURES=$(( FAILURES + 1 )); }
  done
done

echo ""
echo "runtime-dual-write-stress 완료"
echo "  iterations: ${ITERATIONS} × ${#SCENARIOS[@]} = $(( ITERATIONS * ${#SCENARIOS[@]} ))"
echo "  failures: ${FAILURES}"

[ "$FAILURES" -eq 0 ] && exit 0 || { echo "FAIL — 일부 stress step 실패" >&2; exit 1; }
