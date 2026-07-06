#!/usr/bin/env bash
# feature-0016 routine-dbanalysis(§53): 함수·프로시저 introspect 전 datasource backfill 래퍼.
#
# 등록된 전 datasource(또는 --scope <key>)의 routine 을 즉시 introspect 해 routine_objects 에
# upsert 하고 scope 별 AGE 그래프로 투영한다 — insight-worker cadence 전파를 기다리지 않는
# 결정론 수단. per-(ds, DB, schema) 카운트/에러를 JSON 으로 리포트한다.
#
# Usage:
#   bin/routine-backfill.sh                    # 전 datasource
#   bin/routine-backfill.sh --scope <ds-key>   # 특정 datasource 만
#   bin/routine-backfill.sh --dry-run          # 대상 열거만
#   bin/routine-backfill.sh --cap 300          # 스키마당 routine 상한
#   bin/routine-backfill.sh --include-disabled # insight_enabled=0 datasource 도 포함
#
# Exit: 0 성공 / 1 부분 오류(리포트 errors 참조) / 2 실행 가능한 컨테이너 부재
set -euo pipefail

COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-repo}"
PASS_ARGS=("$@")

# insight-worker 우선(모듈 정본 거주), 부재/구이미지 대비 web-a/web-b 폴백 — 모두 modules.* 탑재.
# 컨테이너 목록은 변수로 캡처 — `docker ps | grep -q` 는 pipefail 에서 SIGPIPE(141) 오탐 가능(§18.8 NIT).
RUNNING="$(docker ps --format '{{.Names}}')"
for svc in insight-worker web-a web-b; do
  c="${COMPOSE_PROJECT_NAME}-${svc}-1"
  if grep -qx "$c" <<< "$RUNNING"; then
    if docker exec "$c" python -c "import modules.routine_backfill" 2>/dev/null; then
      echo "[routine-backfill] exec → ${c}" >&2
      exec docker exec "$c" python -m modules.routine_backfill "${PASS_ARGS[@]}"
    else
      echo "[routine-backfill] ${c}: modules.routine_backfill 부재(구이미지) — 다음 후보" >&2
    fi
  fi
done

echo "[routine-backfill] 실행 가능한 컨테이너가 없습니다 (insight-worker/web-a/web-b 중 신규 이미지 필요)." >&2
exit 2
