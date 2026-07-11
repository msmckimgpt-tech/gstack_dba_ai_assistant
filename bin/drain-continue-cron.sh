#!/usr/bin/env bash
# drain-continue-cron.sh — parallel-work-structure 연속 드레인의 **재귀 자가 재호출** 체인
# (docs/improvements/parallel-work-structure/ROADMAP.md §6.4 정본, 2026-07-10 / v2 2026-07-11)
#
# 구조 (재귀):
#   [드레인 시작]  --arm-->  state{ENABLED=1, next_fire=+310m, refcount=<현재 커밋수>}
#   [크론 체커 */5]  now >= next_fire 이면 (flock 로 단일 버스트 보장):
#       (1) 실패-내성 앵커: next_fire=+310m 를 버스트 전 먼저 기록 (check 가 죽어도 체인 유지)
#       (2) **새 세션**을 헤드리스로 시작: claude -p "<재앵커 프롬프트>" (§6.4/§6.5)
#           — 재앵커 세션이 ROADMAP §5 + worktree + 마지막 커밋에서 중단 지점을 복원해 이어감
#       (3) **버스트 종료 사유로 다음 발사 간격 결정**:
#             · usage-limit(사용량 한도)  → +310m 리셋 대기               [TTL-1]
#             · 진전 있음(새 커밋 발생)    → +SHORT **신속 재개**(토큰 유휴 방지)
#             · 진전 없음 N회 연속(스핀)   → +310m 백오프                  [TTL-1]
#   [드레인 완료(전 ITEM done/blocked)]  --disarm-->  체인 종료. TTL(기본 40)=좀비 백스톱.
#
# ─ v2 (2026-07-11) 재설계 근거 (§18.8 적대 패널 2라운드 반영) ─
#  B1/N3) 종료사유를 버스트 출력 free-text 로 판정하는 것은 근본적으로 오탐한다 — 드레인의 도메인
#      자체가 "한도·리셋"이라 productive 버스트도 그 용어를 서술하고, 오탐 1건이 곧 +5h10m 유휴
#      (고치려던 원래 버그)다. 그래서 usage-limit 은 **비-서술 3조건 AND** 로만 인정한다:
#      (i) 진전 0(이 버스트가 이니셔티브 커밋을 못 남김) ∧ (ii) dur < 90s(즉시 abort) ∧
#      (iii) **마지막 비어있지 않은 줄**이 "hit your (session|usage) limit". 미탐은 무진전
#      백오프가 +5h10m 로 받아내므로(저위험) 오탐보다 미탐을 택한다.
#  B2/B3) 특정 세션 --resume/--continue pin 폐기 — 프로젝트 slug 이 다수 세션에 공유돼 "최신
#      jsonl" 이 무관 세션(하이재킹) 또는 orphan 무한 양산으로 이어졌다. 이제 **매 fire 는 항상
#      새 세션**을 띄우고 ROADMAP §5(진행현황)+worktree 상태(미커밋 diff 포함)에서 복원한다
#      (§6.4 의 "§5+worktree 가 복원 기준점" 계약과 정합 — 컨텍스트 누적사(死)도 원천 제거).
#  M4/N1) 진전 판정을 **"버스트 시작 이후 committer-date 로 새로 커밋된 수"**(`--since=@start`,
#      로컬 브랜치)로 한다. 전역 커밋수 델타는 `git fetch`/pull 로 유입된 외부·타-initiative
#      커밋(과거 날짜)까지 "진전"으로 오인해 스핀 가드를 무력화했다(패널 N1). committer-date 창
#      기준이라 pull 로 들어온 과거 커밋은 제외되고, 이 버스트가 실제로 만든 커밋만 계수한다.
#      새 커밋 0 이면 무진전 → NOPROG 누적 → 백오프. (측정 불능 시 기간 <90s 휴리스틱 폴백.)
#
# 왜 호스트 크론인가: 하네스 내부 예약(ScheduleWakeup)은 사용량 한도 리셋 후 stale 발화 사고
# 이력(2026-07)이 있어 금지 유지 — 크론 체커는 상태파일 기준이라 pending 이 쌓이지 않는다.
# 계정 모델: arm 을 실행한 계정의 $HOME 에 state 가 생기고 그 계정의 크론 체커만 발화한다.
#
# 사용법:
#   drain-continue-cron.sh arm [--minutes 310] [--ttl 40] [--project-dir DIR]   # 드레인 시작 시
#   drain-continue-cron.sh check                                                # 크론 전용 (*/5)
#   drain-continue-cron.sh disarm                                               # 드레인 종료 시
#   drain-continue-cron.sh status
#
# 헤드리스 호출 패턴은 dqa-doc-sync-cron.sh 의 2026-07-07 incident fix 승계:
#   CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 (BG 대기 600s 강제종료 → rc=0 오판 방지)
#   + 외곽 timeout 300m (다음 fire 와 겹치지 않는 최종 상한).

set -u

STATE="${HOME}/.claude/drain-continue.state"
LOCK="${HOME}/.claude/drain-continue.lock"
LOGDIR="${HOME}/.claude/drain-continue-logs"
CLAUDE_BIN="${DRAIN_CLAUDE_BIN:-/usr/local/bin/claude}"
DEFAULT_MINUTES=310          # 5시간 10분 = 토큰 재할당(5h rolling window) + 여유 10분
DEFAULT_TTL=40               # 재-arm 없이 최대 40 reset-fire(약 8.6일) 후 자동 disarm (좀비 백스톱)
DEFAULT_PROJECT_DIR="/root/download/docker/mysql_ai_delegated_dev"
BURST_TIMEOUT="${DRAIN_BURST_TIMEOUT:-300m}"
SHORT_MINUTES="${DRAIN_SHORT_MINUTES:-2}"        # 진전 있는 종료 시 신속 재발사 간격(다음 */5 틱에 재개)
SHORT_BURST_SEC="${DRAIN_SHORT_BURST_SEC:-90}"   # 이보다 짧은 버스트=무진전/즉시-abort 후보(진전판정 폴백 + usage-limit 게이트)
MAX_NOPROG="${DRAIN_MAX_NOPROG:-6}"              # 무진전 연속 N회 → +310m 백오프(스핀 방지)
# 진전(이 버스트의 실작업) 식별용 커밋 메시지 서명 — 이니셔티브 커밋만 계수해 동시 sibling
# worktree·cron 커밋을 진전으로 오인하지 않는다(패널 N1). 본 크론은 parallel-work-structure
# 전용이므로 기본값이 그 슬러그. (드레인 커밋은 "(parallel-work-structure ITEM-NN…)" 규약.)
DRAIN_PROGRESS_GREP="${DRAIN_PROGRESS_GREP:-parallel-work-structure}"
# 새 세션 재앵커 프롬프트 (§6.4/§6.5). 주의: 종료사유 판정을 오염시키지 않도록 트리거
# 토큰("resets" 등)을 담지 않는다(판정은 §6.4 v2 마지막-줄 규칙이라 사실상 무해하나 방어).
REANCHOR_PROMPT="parallel-work-structure 연속 드레인을 이어서 수행하라. docs/improvements/parallel-work-structure/ROADMAP.md 의 §5(진행현황)·§6(운영모드, 특히 §6.5 하드-스톱 규약)를 읽고, git worktree list·미커밋 diff·마지막 커밋을 교차확인해 in-progress 항목부터 중단 지점을 복원한 뒤, §6.5 하드-스톱 조건 전까지 연속으로 진행하라. 토큰·컨텍스트·ready 작업이 남아 있는 한 자발적으로 멈추지 말 것. 첫 커밋 전 'bash bin/drain-continue-cron.sh arm' 로 체인을 유지하라."

log() { echo "[$(date '+%F %T')] $*"; }

load_state() {
  ENABLED=0; NEXT_FIRE_EPOCH=0; TTL=0; PROJECT_DIR="$DEFAULT_PROJECT_DIR"
  NOPROG=0
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
NOPROG=$NOPROG
EOF
}

# 버스트 시작(epoch) 이후 committer-date 로 커밋된 **이니셔티브 커밋 수**(메시지가
# $DRAIN_PROGRESS_GREP 매치) — 이 버스트의 진전 측정용. 두 겹 격리(패널 N1):
#   ① `--since=@epoch`  → pull 로 유입된 과거 날짜 외부 커밋 제외(committer-date 창)
#   ② `--grep=<서명>`    → 창 안이라도 **동시 sibling worktree/cron 커밋**(딴 이니셔티브)은
#                          메시지 서명이 없어 제외 — 이 드레인이 실제로 만든 커밋만 계수
# `--branches` 로 refs/remotes 도 배제. 측정 불능이면 -1.
commits_since_epoch() {
  local pdir="$1" epoch="$2" repo n
  repo="$pdir/repo"
  [ -d "$repo/.git" ] || repo="$pdir"
  n=$(git -C "$repo" rev-list --branches --count --since="@${epoch}" \
        --grep="$DRAIN_PROGRESS_GREP" 2>/dev/null) || n=""
  case "$n" in ''|*[!0-9]*) echo "-1" ;; *) echo "$n" ;; esac
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
    NOPROG=0
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
      log "ENABLED next_fire=$(date -d "@${NEXT_FIRE_EPOCH}" '+%F %T') ttl=$TTL noprog=$NOPROG project=$PROJECT_DIR"
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

    # (1) 실패-내성 앵커: 버스트 전 next_fire=+310m 먼저 기록. TTL 은 건드리지 않는다
    #     (신속 재발사는 좀비 백스톱을 소모하지 않음 — TTL 은 +310m reset-fire 에서만 감소).
    NEXT_FIRE_EPOCH=$(( now + DEFAULT_MINUTES * 60 ))
    write_state
    runlog="${LOGDIR}/burst-$(date '+%Y%m%dT%H%M%S').log"

    # (2) **항상 새 세션** 을 재앵커 프롬프트로 헤드리스 시작 (세션 pin/continue 없음 — 하이재킹·
    #     orphan·컨텍스트 누적사 원천 제거; §5+worktree 가 복원 기준점).
    log "FIRE → burst 시작 [fresh -p 재앵커] (anchor +${DEFAULT_MINUTES}m, ttl=$TTL) log=$runlog"
    start=$(date +%s)
    (
      cd "$PROJECT_DIR" || { echo "FATAL: project dir 진입 실패: $PROJECT_DIR"; exit 1; }
      exec env CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 timeout "$BURST_TIMEOUT" \
        "$CLAUDE_BIN" -p "$REANCHOR_PROMPT" --dangerously-skip-permissions
    ) >> "$runlog" 2>&1
    rc=$?
    end=$(date +%s); dur=$(( end - start ))

    # (3) 버스트 종료 사유 판정 → 다음 발사 간격 결정.
    #     버스트 중 재앵커 세션이 arm 했을 수 있어 최신 state 재적재(TTL/NOPROG 반영).
    load_state
    now=$(date +%s)

    # 진전 판정: **버스트 시작 이후 새로 커밋된 이니셔티브 커밋 수**(committer-date 창 + 서명 grep).
    # pull 유입 외부 커밋·동시 sibling 커밋을 제외하고 이 드레인이 만든 커밋만 계수(패널 N1).
    # 측정 불능(-1)이면 기간 휴리스틱 폴백.
    newcommits=$(commits_since_epoch "$PROJECT_DIR" "$start")
    progressed=0
    if [ "$newcommits" -ge 0 ]; then
      [ "$newcommits" -gt 0 ] && progressed=1
    else
      [ "$dur" -ge "$SHORT_BURST_SEC" ] && progressed=1   # 폴백: 측정 불능 시 기간으로 추정
    fi

    # usage-limit: free-text 서술은 근본적으로 오탐(→5h 유휴 = 원래 버그)을 일으키므로(패널 N3),
    # **비-서술 3조건 AND** 로 엄격 판정 — (i) 진전 0(이 버스트가 아무것도 못 커밋) ∧ (ii) 짧은
    # dur(즉시 abort) ∧ (iii) **마지막 비어있지 않은 줄**이 한도 문구. 실 CLI 한도 abort 는 한도
    # 메시지를 종단 출력으로 남기고 즉시 끝난다(관측: 04:20 로그가 그 한 줄뿐). 반면 모델이 본문에서
    # 한도/리셋을 서술해도 그 버스트는 대개 커밋을 남기거나(진전>0) 길거나(dur≥90) 종단이 요약문이라
    # 오탐되지 않는다. **미탐(→무진전 백오프가 +310m 로 받아냄, 저위험)을 오탐보다 택한다.**
    usage_limit=0
    if [ "$progressed" = "0" ] && [ "$dur" -lt "$SHORT_BURST_SEC" ] \
       && grep -vE '^[[:space:]]*$' "$runlog" 2>/dev/null | tail -n 3 \
            | grep -qiE "hit your (session|usage) limit"; then
      usage_limit=1   # 종단 3줄까지 허용(실 abort 뒤 epilogue 한두 줄 대비, N2 churn 감소).
                      # FP 는 progressed==0 ∧ dur<90 게이트가 계속 차단(패널 R4 권장).
    fi

    if [ "$usage_limit" = "1" ]; then
      NEXT_FIRE_EPOCH=$(( now + DEFAULT_MINUTES * 60 )); TTL=$(( TTL - 1 )); NOPROG=0
      log "burst 종료 rc=$rc dur=${dur}s newcommits=$newcommits — usage-limit 감지 → +${DEFAULT_MINUTES}m 리셋 대기 (ttl=$TTL)"
    elif [ "$progressed" = "1" ]; then
      NOPROG=0; NEXT_FIRE_EPOCH=$(( now + SHORT_MINUTES * 60 ))
      log "burst 종료 rc=$rc dur=${dur}s newcommits=$newcommits — 진전 있음 → +${SHORT_MINUTES}m 신속 재개(토큰 유휴 방지)"
    else
      NOPROG=$(( NOPROG + 1 ))
      if [ "$NOPROG" -ge "$MAX_NOPROG" ]; then
        NEXT_FIRE_EPOCH=$(( now + DEFAULT_MINUTES * 60 )); TTL=$(( TTL - 1 )); NOPROG=0
        log "burst 종료 rc=$rc dur=${dur}s newcommits=$newcommits — 무진전 ${MAX_NOPROG}회 연속(스핀 추정) → +${DEFAULT_MINUTES}m 백오프 (ttl=$TTL)"
      else
        NEXT_FIRE_EPOCH=$(( now + SHORT_MINUTES * 60 ))
        log "burst 종료 rc=$rc dur=${dur}s newcommits=$newcommits — 무진전(noprog=$NOPROG/$MAX_NOPROG) → +${SHORT_MINUTES}m 재시도"
      fi
    fi
    write_state
    ;;

  *)
    echo "usage: $0 {arm|check|disarm|status}" >&2; exit 2 ;;
esac
