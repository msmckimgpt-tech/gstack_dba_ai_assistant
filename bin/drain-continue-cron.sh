#!/usr/bin/env bash
# drain-continue-cron.sh — parallel-work-structure 연속 드레인의 **재귀 자가 재호출** 체인
# (docs/improvements/parallel-work-structure/ROADMAP.md §6.4 정본; v3 2026-07-11)
#
# 구조 (재귀):
#   [드레인 시작]  --arm [--session-id <워커>]-->  state{ENABLED=1, next_fire, DRAIN_SESSION_ID=<워커>}
#   [크론 체커 */5]  now >= next_fire 이면 (flock 로 단일 버스트 보장):
#       (1) 실패-내성 앵커: next_fire=+310m 를 버스트 전 먼저 기록 (check 가 죽어도 체인 유지)
#       (2) **pin 된 워커 세션을 `claude --resume <id> -p continue` 로 재개** — 컨텍스트를 보존한
#           채 직전 작업을 이어감(사용자 의도: 사용량 만료마다 작업 누락 방지). pin 이 없으면
#           `-p "<재앵커>"` **새 세션**(부트스트랩/컨텍스트死 복구)으로 시작하고, 그 새 세션을
#           다음 fire 부터 재개하도록 **재-pin** 한다.
#       (3) **버스트 종료 사유로 다음 발사 간격 결정**:
#             · usage-limit(사용량 한도)  → +310m 리셋 대기(pin 유지)          [TTL-1]
#             · context 소진(현 세션 만석) → pin 해제 → 다음 fire 새 세션+재-pin  (+SHORT)
#             · 진전 있음(새 서명 커밋)     → +SHORT **신속 재개**(토큰 유휴 방지)
#             · 진전 없음 N회 연속(스핀)   → +310m 백오프                       [TTL-1]
#   [드레인 완료(전 ITEM done/blocked)]  --disarm-->  체인 종료. TTL(기본 40)=좀비 백스톱.
#
# ─ v3 (2026-07-11) 근거 — always-fresh(v2) → **세션 재개 연속성** 으로 정정 ─
#  사용자 의도: 드레인을 **현 개발환경(Claude Code for VSCode)의 그 세션에서 컨텍스트 보존한 채
#  재개**. v2 의 always-fresh 는 매 fire 신규 세션이라 사용량 만료마다 직전 세션 컨텍스트/미완
#  작업이 누락됐다. v3 은 **pin 된 특정 세션을 `--resume`** 해 연속성을 되살린다.
#  · 하이재킹(패널 B2)은 "최신 세션 자동탐지"가 원인이었으므로, pin 은 **명시 지정**(arm
#    --session-id / 새 세션 생성 후 cron 재-pin)만 쓰고 arm 은 절대 자동탐지하지 않는다.
#  · 컨텍스트死(패널 B3)는 **실제 "Prompt is too long" 감지 시에만** 새 세션으로 넘어가(재-pin)
#    무한 orphan 을 막는다.
#  · 진전 판정(N1)·usage-limit 판정(N3)·타이밍은 v2.2 유지(아래).
#  ⚠ 동시접근: pin 된 세션이 VSCode 에 열려 있는 동안 cron 이 headless `--resume` 하면 한 대화에
#    두 클라이언트가 붙는다. flock 은 cron 측 단일 버스트만 보장하므로, **자동 버스트 중 수동
#    continue 는 자제**(`status` 로 lock 확인). (사용자 승인 하에 채택된 trade-off.)
#
#  [v2.2 유지] 진전 = "버스트 시작 이후 committer-date 로 커밋된 **서명 커밋 수**"
#    (`--since=@start --grep=parallel-work-structure`) → pull 유입 과거커밋·동시 sibling 커밋 배제.
#  [v2.2 유지] usage-limit / context-death = **비-서술 3조건 AND**(진전0 ∧ dur<90 ∧ 종단3줄이
#    해당 CLI 문구) — 드레인이 본문에서 한도/컨텍스트를 서술해도 오탐되지 않는다.
#
# 왜 호스트 크론인가: 하네스 내부 예약(ScheduleWakeup)은 사용량 한도 리셋 후 stale 발화 사고
# 이력(2026-07)이 있어 금지 유지 — 크론 체커는 상태파일 기준이라 pending 이 쌓이지 않는다.
# 계정 모델: arm 을 실행한 계정의 $HOME 에 state 가 생기고 그 계정의 크론 체커만 발화한다.
#
# 사용법:
#   drain-continue-cron.sh arm [--session-id <UUID>] [--minutes 310] [--ttl 40] [--project-dir DIR]
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
SHORT_MINUTES="${DRAIN_SHORT_MINUTES:-2}"        # 진전/컨텍스트死 종료 시 신속 재발사 간격(다음 */5 틱)
SHORT_BURST_SEC="${DRAIN_SHORT_BURST_SEC:-90}"   # 이보다 짧은 버스트=무진전/즉시-abort 후보(진전판정 폴백 + limit/death 게이트)
MAX_NOPROG="${DRAIN_MAX_NOPROG:-6}"              # 무진전 연속 N회 → +310m 백오프(스핀 방지)
# 진전(이 버스트의 실작업) 식별용 커밋 메시지 서명 — 이니셔티브 커밋만 계수해 동시 sibling
# worktree·cron 커밋을 진전으로 오인하지 않는다(패널 N1). 드레인 커밋은 "(parallel-work-structure ITEM-NN…)" 규약.
DRAIN_PROGRESS_GREP="${DRAIN_PROGRESS_GREP:-parallel-work-structure}"
# 새 세션(부트스트랩/컨텍스트死 복구) 재앵커 프롬프트 (§6.4/§6.5).
REANCHOR_PROMPT="parallel-work-structure 연속 드레인을 이어서 수행하라. docs/improvements/parallel-work-structure/ROADMAP.md 의 §5(진행현황)·§6(운영모드, 특히 §6.5 하드-스톱 규약)를 읽고, git worktree list·미커밋 diff·마지막 커밋을 교차확인해 in-progress 항목부터 중단 지점을 복원한 뒤, §6.5 하드-스톱 조건 전까지 연속으로 진행하라. 토큰·컨텍스트·ready 작업이 남아 있는 한 자발적으로 멈추지 말 것. 첫 커밋 전 'bash bin/drain-continue-cron.sh arm' 로 체인을 유지하라."
# pin 된 세션 재개 시 프롬프트 — 세션이 이미 컨텍스트를 갖고 있으므로 짧게, §6.5 만 상기.
# (맥락이 옅은 세션 대비 §5/§6 재확인 폴백 포함.)
RESUME_PROMPT="continue — §6.5 하드-스톱(usage-limit·context 소진·전 ready blocked·완주) 전까지 자발적으로 멈추지 말고 in-progress 항목을 이어서 진행하라. 직전 맥락이 옅으면 docs/improvements/parallel-work-structure/ROADMAP.md §5·§6 과 git worktree list·마지막 커밋으로 중단 지점을 먼저 복원하라."

log() { echo "[$(date '+%F %T')] $*"; }

load_state() {
  ENABLED=0; NEXT_FIRE_EPOCH=0; TTL=0; PROJECT_DIR="$DEFAULT_PROJECT_DIR"
  NOPROG=0; DRAIN_SESSION_ID=""; BACKOFF_STREAK=0
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
DRAIN_SESSION_ID="$DRAIN_SESSION_ID"
BACKOFF_STREAK=$BACKOFF_STREAK
EOF
}

project_slug() { printf '%s' "$1" | sed 's#[/_.]#-#g'; }

# 버스트 시작(epoch) 이후 committer-date 로 커밋된 **이니셔티브 서명 커밋 수** — 이 버스트의 진전.
# ① --since=@epoch → pull 유입 과거 외부 커밋 제외  ② --grep=<서명> → 동시 sibling 커밋 제외
# ③ --branches → refs/remotes 배제. 측정 불능이면 -1.
commits_since_epoch() {
  local pdir="$1" epoch="$2" repo n
  repo="$pdir/repo"; [ -d "$repo/.git" ] || repo="$pdir"
  n=$(git -C "$repo" rev-list --branches --count --since="@${epoch}" \
        --grep="$DRAIN_PROGRESS_GREP" 2>/dev/null) || n=""
  case "$n" in ''|*[!0-9]*) echo "-1" ;; *) echo "$n" ;; esac
}

# 새 세션의 결정론적 id 생성 — mtime 로 "가장 최근 jsonl" 을 추측하면 공유 slug 의 무관 세션
# (사용자 VSCode·orchestrator·타 cron)을 잡아 하이재킹된다(패널 B2, 라이브 재현). 대신 UUID 를
# 미리 만들어 `claude --session-id <uuid>` 로 그 id 를 강제하고, 그 값을 그대로 pin 한다.
new_session_uuid() {
  cat /proc/sys/kernel/random/uuid 2>/dev/null || uuidgen 2>/dev/null || true
}

cmd="${1:-status}"; shift || true

case "$cmd" in
  arm)
    load_state   # 기존 pin 보존(연속성) — arm 은 절대 자동탐지하지 않는다(하이재킹 방지)
    minutes=$DEFAULT_MINUTES; ttl=$DEFAULT_TTL; pdir="$PROJECT_DIR"; sid_arg=""; sid_set=0
    while [ $# -gt 0 ]; do
      case "$1" in
        --minutes) minutes="$2"; shift 2 ;;
        --ttl) ttl="$2"; shift 2 ;;
        --project-dir) pdir="$2"; shift 2 ;;
        --session-id) sid_arg="$2"; sid_set=1; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
      esac
    done
    ENABLED=1; NEXT_FIRE_EPOCH=$(( $(date +%s) + minutes * 60 )); TTL=$ttl; PROJECT_DIR="$pdir"; NOPROG=0; BACKOFF_STREAK=0
    [ "$sid_set" = "1" ] && DRAIN_SESSION_ID="$sid_arg"   # 명시 지정 시에만 갱신, 아니면 기존 pin 유지
    write_state
    log "ARMED next_fire=$(date -d "@${NEXT_FIRE_EPOCH}" '+%F %T') (+${minutes}m) ttl=$TTL session=${DRAIN_SESSION_ID:-<none→첫 fire 새 세션>} project=$PROJECT_DIR user=$(whoami)"
    ;;

  disarm)
    load_state; ENABLED=0; write_state
    log "DISARMED (user=$(whoami))"
    ;;

  status)
    load_state
    if [ "$ENABLED" = "1" ]; then
      log "ENABLED next_fire=$(date -d "@${NEXT_FIRE_EPOCH}" '+%F %T') ttl=$TTL noprog=$NOPROG session=${DRAIN_SESSION_ID:-<none>} project=$PROJECT_DIR"
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

    # (1) 실패-내성 앵커: 버스트 전 next_fire=+310m 먼저 기록. TTL 은 +310m reset-fire 에서만 감소.
    NEXT_FIRE_EPOCH=$(( now + DEFAULT_MINUTES * 60 ))
    write_state
    runlog="${LOGDIR}/burst-$(date '+%Y%m%dT%H%M%S').log"

    # (2) 재개 대상 결정: pin 된 세션이 있고 그 jsonl 이 실재하면 **--resume**(연속성), 아니면
    #     **결정론적 UUID 로 새 세션**(--session-id) 시작. fresh_id 는 launch 전에 확정되므로
    #     재-pin 이 mtime 추측 없이 정확하다(패널 B2 해소).
    slug=$(project_slug "$PROJECT_DIR")
    sess_jsonl="${HOME}/.claude/projects/${slug}/${DRAIN_SESSION_ID}.jsonl"
    fresh_id=""
    if [ -n "$DRAIN_SESSION_ID" ] && [ -f "$sess_jsonl" ]; then
      mode="resume"; was_fresh=0; resume_desc="--resume ${DRAIN_SESSION_ID}"
    else
      mode="fresh"; was_fresh=1; fresh_id="$(new_session_uuid)"
      resume_desc="fresh --session-id ${fresh_id:-<uuid-gen-fail>}"
    fi
    log "FIRE → burst 시작 [$resume_desc] (anchor +${DEFAULT_MINUTES}m, ttl=$TTL) log=$runlog"

    start=$(date +%s)
    (
      cd "$PROJECT_DIR" || { echo "FATAL: project dir 진입 실패: $PROJECT_DIR"; exit 1; }
      if [ "$mode" = "resume" ]; then
        exec env CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 timeout "$BURST_TIMEOUT" \
          "$CLAUDE_BIN" --resume "$DRAIN_SESSION_ID" -p "$RESUME_PROMPT" --dangerously-skip-permissions
      elif [ -n "$fresh_id" ]; then
        exec env CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 timeout "$BURST_TIMEOUT" \
          "$CLAUDE_BIN" --session-id "$fresh_id" -p "$REANCHOR_PROMPT" --dangerously-skip-permissions
      else
        # UUID 생성 실패(양 소스 부재) — 극히 드묾. --session-id 없이 fresh(재-pin 불가, 다음 fire 도 fresh).
        exec env CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 timeout "$BURST_TIMEOUT" \
          "$CLAUDE_BIN" -p "$REANCHOR_PROMPT" --dangerously-skip-permissions
      fi
    ) >> "$runlog" 2>&1
    rc=$?
    end=$(date +%s); dur=$(( end - start ))

    # (3) 종료 사유 판정 → 다음 발사 간격. 버스트 중 세션이 arm 했을 수 있어 state 재적재.
    load_state
    now=$(date +%s)

    # 진전 = 버스트 창 내 서명 커밋 수(패널 N1). 측정 불능(-1)이면 기간 폴백.
    newcommits=$(commits_since_epoch "$PROJECT_DIR" "$start")
    progressed=0
    if [ "$newcommits" -ge 0 ]; then
      [ "$newcommits" -gt 0 ] && progressed=1
    else
      [ "$dur" -ge "$SHORT_BURST_SEC" ] && progressed=1
    fi

    # usage-limit / context-death: 비-서술 3조건 AND(진전0 ∧ dur<90 ∧ 종단3줄 CLI 문구) — 패널 N3.
    tail3="$(grep -vE '^[[:space:]]*$' "$runlog" 2>/dev/null | tail -n 3)"
    usage_limit=0; context_dead=0
    if [ "$progressed" = "0" ] && [ "$dur" -lt "$SHORT_BURST_SEC" ]; then
      printf '%s' "$tail3" | grep -qiE "hit your (session|usage) limit" && usage_limit=1
      printf '%s' "$tail3" | grep -qiF "Prompt is too long" && context_dead=1
    fi

    # 새 세션(fresh) 버스트였다면, **미리 확정한 UUID** 를 그대로 pin(결정론적 재-pin, 패널 B2).
    if [ "$was_fresh" = "1" ] && [ -n "$fresh_id" ]; then
      DRAIN_SESSION_ID="$fresh_id"; log "재-pin(결정론적): 새 워커 세션 = $fresh_id"
    fi

    if [ "$usage_limit" = "1" ]; then
      NEXT_FIRE_EPOCH=$(( now + DEFAULT_MINUTES * 60 )); TTL=$(( TTL - 1 )); NOPROG=0; BACKOFF_STREAK=0
      log "burst 종료 rc=$rc dur=${dur}s newcommits=$newcommits — usage-limit 감지(pin 유지) → +${DEFAULT_MINUTES}m 리셋 대기 (ttl=$TTL)"
    elif [ "$context_dead" = "1" ]; then
      DRAIN_SESSION_ID=""; NEXT_FIRE_EPOCH=$(( now + SHORT_MINUTES * 60 )); NOPROG=0; BACKOFF_STREAK=0
      log "burst 종료 rc=$rc dur=${dur}s newcommits=$newcommits — context 소진(Prompt too long) → pin 해제, 다음 fire 새 세션 +${SHORT_MINUTES}m"
    elif [ "$progressed" = "1" ]; then
      NOPROG=0; BACKOFF_STREAK=0; NEXT_FIRE_EPOCH=$(( now + SHORT_MINUTES * 60 ))
      log "burst 종료 rc=$rc dur=${dur}s newcommits=$newcommits — 진전 있음 → +${SHORT_MINUTES}m 신속 재개(토큰 유휴 방지)"
    else
      NOPROG=$(( NOPROG + 1 ))
      if [ "$NOPROG" -ge "$MAX_NOPROG" ]; then
        # 무진전 N회 연속 = 백오프. 하지만 "놓친 usage-limit(건강한 세션)"과 "막힌 세션(죽음)"을
        # 즉시 구분 못 하므로 **2단계**(패널 MINOR-1 — 사용자 핵심의도 '컨텍스트 보존' 보호):
        #  ·resume 세션의 1차 백오프 → **pin 유지** + +310m(리셋 대기). 놓친 usage-limit 이면 리셋
        #    후 같은 세션이 진전 → 컨텍스트 보존. (건강한 세션을 성급히 버리지 않는다.)
        #  ·리셋 뒤에도 무진전(streak≥2) 또는 애초에 fresh 부트스트랩 실패 → **pin 해제** 재부트스트랩
        #    (context-death 미탐 영구 스톨 방지 — 패널 MAJOR).
        TTL=$(( TTL - 1 )); BACKOFF_STREAK=$(( BACKOFF_STREAK + 1 )); NOPROG=0
        NEXT_FIRE_EPOCH=$(( now + DEFAULT_MINUTES * 60 ))
        if [ "$was_fresh" = "0" ] && [ "$BACKOFF_STREAK" -lt 2 ]; then
          log "burst 종료 rc=$rc dur=${dur}s newcommits=$newcommits — 무진전 ${MAX_NOPROG}회(놓친 usage-limit 가능, pin 유지) → +${DEFAULT_MINUTES}m 리셋 대기 (ttl=$TTL, streak=$BACKOFF_STREAK)"
        else
          DRAIN_SESSION_ID=""; BACKOFF_STREAK=0
          log "burst 종료 rc=$rc dur=${dur}s newcommits=$newcommits — 무진전 지속(리셋 후에도/부트스트랩 실패, 막힌 세션 판정) → pin 해제 재부트스트랩 + +${DEFAULT_MINUTES}m 백오프 (ttl=$TTL)"
        fi
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
