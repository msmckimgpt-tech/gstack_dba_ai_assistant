#!/usr/bin/env bash
# drain-continue-cron.sh — parallel-work-structure 연속 드레인의 **재귀 자가 재호출** 체인
# (docs/improvements/parallel-work-structure/ROADMAP.md §6.4 정본, 2026-07-10 사용자 지시)
#
# 구조 (재귀):
#   [버스트 시작] --arm--> state{next_fire = now+310m}      (버스트 = 최초 스킬 호출 / 사용자 continue / 자동 재호출)
#   [크론 체커 */5] now >= next_fire 이면:
#       (1) 먼저 재-arm(next_fire = now+310m, TTL-1)  ← 버스트가 즉사해도 체인이 끊기지 않는 재귀 보장
#       (2) claude --continue -p "continue" 로 최신 드레인 대화를 헤드리스 재개
#       (3) 재개된 버스트는 §6.4 에 따라 시작 시 다시 arm (idempotent — (1)과 근사 동일값 덮어씀)
#   [드레인 완료(전 ITEM done/blocked)] --disarm--> 체인 종료. TTL(기본 40 fire)이 좀비 체인 백스톱.
#
# 왜 호스트 크론인가: 하네스 내부 예약(ScheduleWakeup)은 사용량 한도 리셋 후 stale 발화 사고
# 이력(2026-07)이 있어 금지 유지 — 크론 체커는 상태파일 기준이라 pending 이 쌓이지 않는다.
#
# 계정 모델: arm 을 실행한 계정의 $HOME 에 state 가 생기고, 그 계정의 크론 체커만 발화한다
# (root/claude-corp 크론탭에 각각 체커 설치 — 드레인을 시작한 계정의 체인만 활성).
#
# 사용법:
#   drain-continue-cron.sh arm [--minutes 310] [--ttl 40] [--project-dir DIR]   # 버스트 시작 시
#   drain-continue-cron.sh check                                                # 크론 전용 (*/5)
#   drain-continue-cron.sh disarm                                               # 드레인 종료 시
#   drain-continue-cron.sh status
#
# 헤드리스 호출 패턴은 dqa-doc-sync-cron.sh 의 2026-07-07 incident fix 를 승계:
#   CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 (BG 대기 600s 강제종료 → rc=0 오판 방지)
#   + 외곽 timeout 300m (다음 fire(310m)와 겹치지 않는 최종 상한).

set -u

STATE="${HOME}/.claude/drain-continue.state"
LOCK="${HOME}/.claude/drain-continue.lock"
LOGDIR="${HOME}/.claude/drain-continue-logs"
CLAUDE_BIN="${DRAIN_CLAUDE_BIN:-/usr/local/bin/claude}"
DEFAULT_MINUTES=310          # 5시간 10분 = 토큰 재할당(5h rolling window) + 여유 10분
DEFAULT_TTL=40               # 재-arm 없이 최대 40 fire(약 8.6일) 후 자동 disarm (좀비 체인 백스톱)
DEFAULT_PROJECT_DIR="/root/download/docker/mysql_ai_delegated_dev"
BURST_TIMEOUT="${DRAIN_BURST_TIMEOUT:-300m}"

log() { echo "[$(date '+%F %T')] $*"; }

load_state() {
  ENABLED=0; NEXT_FIRE_EPOCH=0; TTL=0; PROJECT_DIR="$DEFAULT_PROJECT_DIR"
  # shellcheck disable=SC1090
  [ -f "$STATE" ] && . "$STATE"
}

write_state() {
  mkdir -p "$(dirname "$STATE")"
  cat > "$STATE" <<EOF
ENABLED=$ENABLED
NEXT_FIRE_EPOCH=$NEXT_FIRE_EPOCH
TTL=$TTL
PROJECT_DIR="$PROJECT_DIR"
EOF
}

cmd="${1:-status}"; shift || true

case "$cmd" in
  arm)
    minutes=$DEFAULT_MINUTES; ttl=$DEFAULT_TTL; pdir=$DEFAULT_PROJECT_DIR
    while [ $# -gt 0 ]; do
      case "$1" in
        --minutes) minutes="$2"; shift 2 ;;
        --ttl) ttl="$2"; shift 2 ;;
        --project-dir) pdir="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
      esac
    done
    ENABLED=1; NEXT_FIRE_EPOCH=$(( $(date +%s) + minutes * 60 )); TTL=$ttl; PROJECT_DIR="$pdir"
    write_state
    log "ARMED next_fire=$(date -d "@${NEXT_FIRE_EPOCH}" '+%F %T') (+${minutes}m) ttl=$TTL project=$PROJECT_DIR user=$(whoami)"
    ;;

  disarm)
    load_state; ENABLED=0; write_state
    log "DISARMED (user=$(whoami))"
    ;;

  status)
    load_state
    if [ "$ENABLED" = "1" ]; then
      log "ENABLED next_fire=$(date -d "@${NEXT_FIRE_EPOCH}" '+%F %T') ttl=$TTL project=$PROJECT_DIR"
    else
      log "DISABLED"
    fi
    if [ -e "$LOCK" ] && ! flock -n "$LOCK" -c true 2>/dev/null; then
      log "NOTE: 버스트 실행 중(lock 점유) — 이 시점의 수동 continue 는 동시접근이 되므로 자제"
    fi
    ;;

  check)
    load_state
    [ "$ENABLED" = "1" ] || exit 0
    now=$(date +%s)
    [ "$now" -ge "$NEXT_FIRE_EPOCH" ] || exit 0
    mkdir -p "$LOGDIR" "$(dirname "$LOCK")"
    exec 9>"$LOCK"
    flock -n 9 || { log "skip: 이전 버스트 실행 중(lock)"; exit 0; }

    if [ "$TTL" -le 0 ]; then
      ENABLED=0; write_state
      log "TTL 소진 — 체인 자동 종료(disarm). 드레인 미완이면 수동 arm 으로 재개."
      exit 0
    fi

    # (1) 재귀 재-arm 먼저 — 버스트가 어떤 이유로든 실패해도 체인은 이어진다
    NEXT_FIRE_EPOCH=$(( now + DEFAULT_MINUTES * 60 )); TTL=$(( TTL - 1 ))
    write_state
    runlog="${LOGDIR}/burst-$(date '+%Y%m%dT%H%M%S').log"
    log "FIRE → burst 시작 (재-arm: next=$(date -d "@${NEXT_FIRE_EPOCH}" '+%F %T'), ttl=$TTL) log=$runlog"

    # (2) 최신 드레인 대화를 헤드리스로 재개 — cwd 가 세션 slug 를 결정하므로 project dir 고정
    (
      cd "$PROJECT_DIR" || { log "FATAL: project dir 진입 실패: $PROJECT_DIR"; exit 1; }
      CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 timeout "$BURST_TIMEOUT" \
        "$CLAUDE_BIN" --continue -p "continue" \
        --dangerously-skip-permissions
    ) >> "$runlog" 2>&1
    rc=$?
    log "burst 종료 rc=$rc (124=timeout 상한 — 정상 범주, 다음 fire 가 이어감)"
    ;;

  *)
    echo "usage: $0 {arm|check|disarm|status}" >&2; exit 2 ;;
esac
