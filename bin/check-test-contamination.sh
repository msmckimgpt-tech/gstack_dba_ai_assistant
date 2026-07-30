#!/usr/bin/env bash
# bin/check-test-contamination.sh
#
# 단위 테스트가 라이브 관리 콘솔 설정(`agent_memory.WebRuntimeSettings`)을 덮어쓴 흔적을
# 감사 로그에서 찾아 리포트한다.
#
# ## 왜 필요한가
#
# 테스트 프로세스가 라이브 컨트롤플레인에 도달할 수 있는 환경에서, PUT 을 태우는 테스트가
# 운영 설정을 테스트 리터럴로 덮어썼다(2026-07-13 ~ 07-29, 150건). 격리는 Makefile ·
# 루트 `conftest.py` · 전용 compose 프로젝트로 3중으로 세웠지만, 그 방어는 모두 **저장소
# 파일**에 있어 이미 분기된 worktree 사본에는 없다. 실제로 격리를 머지한 10분 뒤 오래된
# 사본에서 오염이 재발했고, **사용자가 하루 뒤에 발견**했다 — 그 탐지 지연이 이 스크립트의
# 존재 이유다. 오염은 조용하다(설정 화면 숫자가 바뀌어 있을 뿐 에러가 없다).
#
# ## 판별 신호
#
# 애플리케이션이 남기는 감사 기록에서 테스트 유입은 명확히 갈린다:
#   RemoteAddr = UserAgent = 'testclient'   (FastAPI TestClient 의 기본값)
# 사람의 콘솔 변경은 실제 IP + 브라우저 UA 로 남는다.
#
# ## 사용법
#
#   bash bin/check-test-contamination.sh            # 최근 7일
#   bash bin/check-test-contamination.sh --days 30
#   bash bin/check-test-contamination.sh --quiet     # 종료코드만 (cron/게이트용)
#
# ## 종료 코드
#
#   0 — 오염 흔적 없음, 또는 있었으나 현재 값이 이미 사람 설정값으로 복구됨
#   1 — **현재 라이브 값이 테스트가 쓴 값 그대로 남아 있다** (조치 필요)
#   2 — usage / 환경 오류 (컨테이너 미기동 등)
set -uo pipefail

DAYS=7
QUIET=0
while [ $# -gt 0 ]; do
  case "$1" in
    --days) DAYS="${2:-7}"; shift 2;;
    --quiet) QUIET=1; shift;;
    -h|--help) sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# .env 에서 root 비밀번호만 취한다(컨테이너 내부 env 를 쓰면 worktree 사본 차이에 영향받지 않음).
MYSQL_CONTAINER="${MYSQL_CONTAINER:-repo-mysql-1}"
if ! docker inspect "$MYSQL_CONTAINER" >/dev/null 2>&1; then
  [ "$QUIET" = 1 ] || echo "check-test-contamination: MySQL 컨테이너 '$MYSQL_CONTAINER' 를 찾을 수 없습니다 (MYSQL_CONTAINER 로 지정 가능)." >&2
  exit 2
fi

mysql_q() {
  # 컨테이너 안의 MYSQL_ROOT_PASSWORD 를 그대로 사용 — 호스트에 비밀번호를 노출하지 않는다.
  docker exec -i "$MYSQL_CONTAINER" sh -lc 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -B -e "$(cat)"' 2>/dev/null
}

# 오염 이벤트 목록 (최근 $DAYS 일)
EVENTS="$(printf '%s' "
SELECT ResourceId, JSON_UNQUOTE(JSON_EXTRACT(ChangeJson,'\$.value')), OccurredAt
FROM agent_memory.WebAuditEvents
WHERE ActionCode LIKE 'system.runtime%'
  AND RemoteAddr = 'testclient'
  AND OccurredAt >= NOW() - INTERVAL $DAYS DAY
ORDER BY Id;" | mysql_q)"

if [ -z "$EVENTS" ]; then
  [ "$QUIET" = 1 ] || echo "check-test-contamination: 최근 ${DAYS}일간 테스트 유입 흔적 없음 (PASS)"
  exit 0
fi

EVENT_COUNT="$(printf '%s\n' "$EVENTS" | grep -c . || true)"
KEYS="$(printf '%s\n' "$EVENTS" | awk -F'\t' '{print $1}' | sort -u)"

# 각 키별로 "현재 라이브 값" vs "테스트가 마지막으로 쓴 값" vs "사람이 마지막으로 쓴 값" 대조.
STALE=0
REPORT=""
while IFS= read -r key; do
  [ -n "$key" ] || continue
  cur="$(printf '%s' "SELECT SettingValue FROM agent_memory.WebRuntimeSettings WHERE SettingKey='$key';" | mysql_q | head -1)"
  test_val="$(printf '%s' "
SELECT JSON_UNQUOTE(JSON_EXTRACT(ChangeJson,'\$.value'))
FROM agent_memory.WebAuditEvents
WHERE ActionCode LIKE 'system.runtime%' AND RemoteAddr='testclient' AND ResourceId='$key'
ORDER BY Id DESC LIMIT 1;" | mysql_q | head -1)"
  human_val="$(printf '%s' "
SELECT JSON_UNQUOTE(JSON_EXTRACT(ChangeJson,'\$.value'))
FROM agent_memory.WebAuditEvents
WHERE ActionCode LIKE 'system.runtime%' AND RemoteAddr<>'testclient' AND ResourceId='$key'
ORDER BY Id DESC LIMIT 1;" | mysql_q | head -1)"

  if [ -n "$cur" ] && [ "$cur" = "$test_val" ]; then
    STALE=$((STALE + 1))
    if [ -n "$human_val" ] && [ "$human_val" != "$test_val" ]; then
      REPORT="${REPORT}  [오염 잔존] ${key}: 현재=${cur} (테스트가 쓴 값) / 사람 최종 설정=${human_val}"$'\n'
    else
      REPORT="${REPORT}  [오염 잔존] ${key}: 현재=${cur} (테스트가 쓴 값) / 사람 설정 이력 없음 — 이 override 자체가 테스트 산물일 수 있음"$'\n'
    fi
  else
    REPORT="${REPORT}  [복구됨]   ${key}: 현재=${cur:-<override 없음>} (테스트가 쓴 값 ${test_val} 아님)"$'\n'
  fi
done <<< "$KEYS"

if [ "$QUIET" != 1 ]; then
  echo "check-test-contamination: 최근 ${DAYS}일간 테스트 유입(RemoteAddr=testclient) ${EVENT_COUNT}건 감지"
  printf '%s' "$REPORT"
  if [ "$STALE" -gt 0 ]; then
    echo
    echo "→ ${STALE}개 키가 테스트 값 그대로입니다. 관리 콘솔 '시스템 > 설정' 에서 의도한 값으로 되돌리세요."
    echo "→ 유입 경로 점검: 격리 없는 worktree 사본에서 라이브 compose 프로젝트로 테스트를 돌리지 않았는지"
    echo "   확인 (Makefile 의 DC_TEST / 루트 conftest.py 도달성 가드 참조)."
  fi
fi

[ "$STALE" -gt 0 ] && exit 1
exit 0
