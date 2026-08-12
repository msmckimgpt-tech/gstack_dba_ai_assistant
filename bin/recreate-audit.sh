#!/usr/bin/env bash
# =============================================================================
# recreate-audit.sh — **인가되지 않은 서빙 컨테이너 재생성**을 사후 적발한다.
#
# 왜 필요한가 (CHG-20260812T200000):
#   raw `docker compose up -d` 는 CLI 다 — 스크립트로 물리적으로 막을 수 없다. 2026-08-12
#   17:30 사고가 정확히 그 경로였고(배포 lock 은 그 시각 이전 값 그대로, 배포는 17:49·18:07 에
#   따로 돌았다), **아무 신호도 남지 않아** 사용자 보고가 오기 전까지 아무도 몰랐다.
#   막을 수 없는 것은 **보이게** 만든다: 인가된 경로(deploy-web.sh · safe-recreate.sh)가
#   스탬프를 남기고, 이 스크립트가 컨테이너의 실제 `StartedAt` 과 대조해 스탬프 없는 재생성을
#   보고한다. 사고 원인 규명이 "며칠 뒤 추측" 에서 "즉시 조회" 로 바뀐다.
#
# 판정:
#   각 서빙 서비스의 컨테이너 `StartedAt` 이, 그 서비스에 대한 **가장 가까운 이전 스탬프**보다
#   `TOLERANCE_SEC`(기본 900) 이상 뒤라면 → **인가되지 않은 재생성**으로 본다.
#   스탬프가 아예 없으면(스탬프 도입 이전 컨테이너) `unknown` 으로 보고한다 — 위반과 구분한다.
#
# Usage:
#   bin/recreate-audit.sh              # 사람이 읽는 표 (인가되지 않은 항목이 있으면 exit 1)
#   bin/recreate-audit.sh --quiet      # 위반만 출력
#   RECREATE_AUDIT_TOLERANCE_SEC=1800 bin/recreate-audit.sh
#
# Exit: 0 위반 없음 / 1 인가되지 않은 재생성 있음 / 2 조회 불가.
# =============================================================================
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

STAMP_FILE="${SAFE_RECREATE_STAMP_FILE:-../artifacts/deploy/recreate-sanctioned.log}"
TOLERANCE_SEC="${RECREATE_AUDIT_TOLERANCE_SEC:-900}"
QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1

# 사용자 요청을 들고 있는(=재생성이 대화를 끊는) 서비스만 감사 대상.
SERVICES=(web-a web-b ask-worker bedrock-gateway)

DC=(docker compose -f docker-compose.yml)

_epoch() {  # ISO8601 → epoch (실패 시 빈 값)
  date -u -d "$1" +%s 2>/dev/null || true
}

_container_started() {  # $1 = svc → ISO8601 | 빈 값
  local cid
  cid="$("${DC[@]}" ps -q "$1" 2>/dev/null | head -1)"
  [ -n "$cid" ] || return 0
  docker inspect "$cid" --format '{{.State.StartedAt}}' 2>/dev/null || true
}

_last_stamp_epoch() {  # $1 = svc → epoch | 빈 값 (해당 서비스의 마지막 인가 스탬프)
  [ -r "$STAMP_FILE" ] || return 0
  local ts
  ts="$(awk -F'\t' -v s="$1" '$2==s {t=$1} END{if(t!="") print t}' "$STAMP_FILE" 2>/dev/null)"
  [ -n "$ts" ] || return 0
  _epoch "$ts"
}

violations=0
unknowns=0
rows=""

for svc in "${SERVICES[@]}"; do
  started="$(_container_started "$svc")"
  if [ -z "$started" ]; then
    rows="${rows}${svc}\t(미기동)\t-\tskip\n"
    continue
  fi
  s_ep="$(_epoch "$started")"
  if [ -z "$s_ep" ]; then
    printf '[recreate-audit] ERROR: StartedAt 파싱 실패(%s: %s)\n' "$svc" "$started" >&2
    exit 2
  fi
  k_ep="$(_last_stamp_epoch "$svc")"
  if [ -z "$k_ep" ]; then
    rows="${rows}${svc}\t${started}\t(스탬프 없음)\tunknown\n"
    unknowns=$(( unknowns + 1 ))
    continue
  fi
  delta=$(( s_ep - k_ep ))
  if [ "$delta" -gt "$TOLERANCE_SEC" ]; then
    rows="${rows}${svc}\t${started}\t+${delta}s\tUNSANCTIONED\n"
    violations=$(( violations + 1 ))
  else
    rows="${rows}${svc}\t${started}\t+${delta}s\tok\n"
  fi
done

if [ "$QUIET" -eq 1 ]; then
  printf '%b' "$rows" | grep -E 'UNSANCTIONED' || true
else
  printf '[recreate-audit] 스탬프: %s · 허용 오차: %ss\n' "$STAMP_FILE" "$TOLERANCE_SEC" >&2
  printf 'SERVICE\tSTARTED_AT\tSINCE_STAMP\tVERDICT\n'
  printf '%b' "$rows"
fi

if [ "$violations" -gt 0 ]; then
  printf '\n[recreate-audit] 인가되지 않은 재생성 %s건 — 배포/safe-recreate 를 경유하지 않았다.\n' "$violations" >&2
  printf '[recreate-audit] 그 창에 진행 중이던 대화는 끊겼을 수 있다. 앞으로는:\n' >&2
  printf '[recreate-audit]   sudo -E bin/safe-recreate.sh <service>   (또는 make deploy-web)\n' >&2
  exit 1
fi
[ "$unknowns" -gt 0 ] && printf '[recreate-audit] 스탬프 없는 서비스 %s건 — 스탬프 도입 이전 기동으로 보인다(위반 아님).\n' "$unknowns" >&2
exit 0
