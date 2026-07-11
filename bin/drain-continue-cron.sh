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
RESET_BUFFER_SEC="${DRAIN_RESET_BUFFER_SEC:-300}" # 리셋 시각 + 버퍼(토큰 반영 여유 5분)
MAX_MODEL_FLAP="${DRAIN_MAX_MODEL_FLAP:-3}"       # model_limit⇄model_invalid 신속-재시도 연속 N회 → TTL 유계 백오프(핑퐁 방지)
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
  NOPROG=0; DRAIN_SESSION_ID=""; BACKOFF_STREAK=0; DRAIN_MODEL=""; MODEL_FLAP=0
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
DRAIN_MODEL="$DRAIN_MODEL"
MODEL_FLAP=$MODEL_FLAP
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

# usage-limit 버스트 로그에서 CLI 가 알려주는 **실제 리셋 시각**("… resets 7:20pm (Asia/Seoul)")을
# 파싱해 epoch 로 반환(실패 시 빈값). 왜 필요한가: 고정 +310m 은 한도를 5h 롤링 윈도우 **초반**에
# 맞으면(공유 quota 를 다른 세션들이 함께 소비) 실제 리셋을 크게 지나쳐 재개가 늦다 — 관측(2026-07-11):
# 16:25 한도 → +310m=21:35 예약 vs 메시지가 알려준 실제 리셋 19:20(=7:20pm). CLI 가 주는 리셋 시각을
# 쓰면 리셋 직후 정확히 재개. host TZ=메시지 TZ(Asia/Seoul) 전제(date -d 로컬 파싱).
parse_reset_epoch() {
  local runlog="$1" t ep nowe
  t=$(grep -oiE "resets +[0-9]{1,2}:[0-9]{2} *(am|pm)" "$runlog" 2>/dev/null | tail -1 \
        | grep -oiE "[0-9]{1,2}:[0-9]{2} *(am|pm)" | tr -d ' ')
  [ -n "$t" ] || return 0
  ep=$(date -d "$t" +%s 2>/dev/null) || return 0
  case "$ep" in ''|*[!0-9]*) return 0 ;; esac
  nowe=$(date +%s)
  [ "$ep" -le "$nowe" ] && ep=$(( ep + 86400 ))          # 지난 시각(자정 넘김)이면 다음날
  [ "$ep" -gt $(( nowe + 6*3600 )) ] && return 0         # 6h 초과=파싱 오류로 간주 → 폴백
  echo "$ep"
}

cmd="${1:-status}"; shift || true

case "$cmd" in
  arm)
    load_state   # 기존 pin 보존(연속성) — arm 은 절대 자동탐지하지 않는다(하이재킹 방지)
    minutes=$DEFAULT_MINUTES; ttl=$DEFAULT_TTL; pdir="$PROJECT_DIR"; sid_arg=""; sid_set=0; model_arg=""; model_set=0
    while [ $# -gt 0 ]; do
      case "$1" in
        --minutes) minutes="$2"; shift 2 ;;
        --ttl) ttl="$2"; shift 2 ;;
        --project-dir) pdir="$2"; shift 2 ;;
        --session-id) sid_arg="$2"; sid_set=1; shift 2 ;;
        --model) model_arg="$2"; model_set=1; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
      esac
    done
    ENABLED=1; NEXT_FIRE_EPOCH=$(( $(date +%s) + minutes * 60 )); TTL=$ttl; PROJECT_DIR="$pdir"; NOPROG=0; BACKOFF_STREAK=0; MODEL_FLAP=0
    [ "$sid_set" = "1" ] && DRAIN_SESSION_ID="$sid_arg"   # 명시 지정 시에만 갱신, 아니면 기존 pin 유지
    [ "$model_set" = "1" ] && DRAIN_MODEL="$model_arg"    # 명시 지정 시에만 갱신, 아니면 기존 모델 유지
    write_state
    log "ARMED next_fire=$(date -d "@${NEXT_FIRE_EPOCH}" '+%F %T') (+${minutes}m) ttl=$TTL session=${DRAIN_SESSION_ID:-<none→첫 fire 새 세션>} model=${DRAIN_MODEL:-<account-default>} project=$PROJECT_DIR user=$(whoami)"
    ;;

  disarm)
    load_state; ENABLED=0; write_state
    log "DISARMED (user=$(whoami))"
    ;;

  status)
    load_state
    if [ "$ENABLED" = "1" ]; then
      log "ENABLED next_fire=$(date -d "@${NEXT_FIRE_EPOCH}" '+%F %T') ttl=$TTL noprog=$NOPROG modelflap=$MODEL_FLAP session=${DRAIN_SESSION_ID:-<none>} model=${DRAIN_MODEL:-<account-default>} project=$PROJECT_DIR"
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
    # --model 은 DRAIN_MODEL 이 설정된 경우에만 주입(빈 배열이면 계정 기본 모델 사용).
    model_opts=(); [ -n "$DRAIN_MODEL" ] && model_opts=(--model "$DRAIN_MODEL")
    log "FIRE → burst 시작 [$resume_desc]${DRAIN_MODEL:+ [model=$DRAIN_MODEL]} (anchor +${DEFAULT_MINUTES}m, ttl=$TTL) log=$runlog"

    start=$(date +%s)
    (
      cd "$PROJECT_DIR" || { echo "FATAL: project dir 진입 실패: $PROJECT_DIR"; exit 1; }
      if [ "$mode" = "resume" ]; then
        exec env CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 timeout "$BURST_TIMEOUT" \
          "$CLAUDE_BIN" --resume "$DRAIN_SESSION_ID" "${model_opts[@]}" -p "$RESUME_PROMPT" --dangerously-skip-permissions
      elif [ -n "$fresh_id" ]; then
        exec env CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 timeout "$BURST_TIMEOUT" \
          "$CLAUDE_BIN" --session-id "$fresh_id" "${model_opts[@]}" -p "$REANCHOR_PROMPT" --dangerously-skip-permissions
      else
        # UUID 생성 실패(양 소스 부재) — 극히 드묾. --session-id 없이 fresh(재-pin 불가, 다음 fire 도 fresh).
        exec env CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 timeout "$BURST_TIMEOUT" \
          "$CLAUDE_BIN" "${model_opts[@]}" -p "$REANCHOR_PROMPT" --dangerously-skip-permissions
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

    # usage-limit / context-death 은 계정 전체 5h 윈도우 소진, model-limit 은 **특정 모델**만 소진
    # (다른 모델로 전환하면 즉시 재개 가능 — 별개 실패급, 별개 처방). 셋 다 비-서술 3조건 AND
    # (진전0 ∧ dur<90 ∧ 종단3줄 CLI 문구)로만 인정 — 패널 N3 원칙 유지.
    tail3="$(grep -vE '^[[:space:]]*$' "$runlog" 2>/dev/null | tail -n 3)"
    usage_limit=0; context_dead=0; model_limit=0; model_invalid=0
    if [ "$progressed" = "0" ] && [ "$dur" -lt "$SHORT_BURST_SEC" ]; then
      printf '%s' "$tail3" | grep -qiE "hit your (session|usage) limit" && usage_limit=1
      printf '%s' "$tail3" | grep -qiF "Prompt is too long" && context_dead=1
      # 실 CLI 문구: "You've reached your Fable 5 limit. /model to switch models."
      printf '%s' "$tail3" | grep -qiE "reached your .+ limit" \
        && printf '%s' "$tail3" | grep -qiF "/model" && model_limit=1
      # 실 CLI 문구: "There's an issue with the selected model (X). It may not exist or you
      # may not have access to it." — 자동 전환한 모델이 이 계정에 없거나 오타/폐기된 경우. 이걸
      # 놓치면 DRAIN_MODEL 이 깨진 값으로 영구 고정돼 매 fire 가 즉시 실패하면서 "무진전"으로
      # 위장돼 최대 TTL 소진(~8.6일)까지 무증상 정지한다(§18.8 MAJOR, 라이브 재현·2026-07-12).
      printf '%s' "$tail3" | grep -qiF "may not exist or you may not have access to it" && model_invalid=1
    fi

    # 새 세션(fresh) 버스트였다면, **미리 확정한 UUID** 를 그대로 pin(결정론적 재-pin, 패널 B2).
    if [ "$was_fresh" = "1" ] && [ -n "$fresh_id" ]; then
      DRAIN_SESSION_ID="$fresh_id"; log "재-pin(결정론적): 새 워커 세션 = $fresh_id"
    fi

    if [ "$model_invalid" = "1" ]; then
      # 자동 전환(또는 arm --model 명시)한 모델이 이 계정에 없음/오타/폐기 — 깨진 값을 pin 해
      # 두면 매 fire 가 즉시 재실패하며 영구 무증상 정지한다(패널 MAJOR). **즉시 계정 기본 모델로
      # 복귀**하고 신속 재시도 — 대기가 아니라 즉시 조치로 복구 가능.
      #
      # flap 가드(§18.8 재검토 MAJOR — model_limit⇄model_invalid 핑퐁): opus 가 정말 미보유고
      # 기본모델 한도가 2분 뒤에도 안 풀리면 두 신속-재시도 분기가 서로를 무한 왕복하며 TTL/NOPROG
      # 어느 백스톱도 건드리지 않아 무증상 무한 스핀이 될 수 있다. MODEL_FLAP 로 두 분기의 연속
      # 발생을 세어, 임계 도달 시 **모델 전환 자체를 이번 드레인에서 비활성화**(TTL 유계 백오프)한다.
      MODEL_FLAP=$(( MODEL_FLAP + 1 ))
      bad_model="${DRAIN_MODEL:-<account-default>}"
      DRAIN_MODEL=""; NOPROG=0; BACKOFF_STREAK=0
      if [ "$MODEL_FLAP" -ge "$MAX_MODEL_FLAP" ]; then
        TTL=$(( TTL - 1 )); MODEL_FLAP=0; NEXT_FIRE_EPOCH=$(( now + DEFAULT_MINUTES * 60 ))
        log "burst 종료 rc=$rc dur=${dur}s newcommits=$newcommits — 모델전환 핑퐁 ${MAX_MODEL_FLAP}회 감지(model=$bad_model) → 모델전환 이번 백오프 동안 중지(계정 기본 유지 — 리셋 뒤 재발 시 재시도) + +${DEFAULT_MINUTES}m 백오프 (ttl=$TTL)"
      else
        NEXT_FIRE_EPOCH=$(( now + SHORT_MINUTES * 60 ))
        log "burst 종료 rc=$rc dur=${dur}s newcommits=$newcommits — 모델 접근불가/미존재(model=$bad_model) → 계정 기본 모델로 복귀, +${SHORT_MINUTES}m 재시도 (flap=$MODEL_FLAP/$MAX_MODEL_FLAP)"
      fi
    elif [ "$model_limit" = "1" ]; then
      # 모델별 한도(계정 5h 윈도우 소진과 무관 — 특정 모델만 소진). 사용자 지시(2026-07-11):
      # "다른 모델(Opus)로 전환하여 재개" — 현재 모델이 opus 가 아니면 즉시 opus 로 전환해
      # **신속 재시도**(무진전/백오프 카운트 안 함 — 대기가 아니라 조치로 즉시 해결 가능).
      # 이미 opus 인데도 모델 한도면(폴백 소진) 별 다른 처방이 없어 usage-limit 과 동일하게
      # pin 유지 + 고정 +5h10m 대기(이 문구엔 리셋 시각이 없어 parse_reset_epoch 적용 불가).
      prev_model="${DRAIN_MODEL:-<account-default>}"
      cur_model_lc=$(printf '%s' "$DRAIN_MODEL" | tr '[:upper:]' '[:lower:]')
      NOPROG=0; BACKOFF_STREAK=0
      if [ "$cur_model_lc" != "opus" ]; then
        MODEL_FLAP=$(( MODEL_FLAP + 1 ))
        if [ "$MODEL_FLAP" -ge "$MAX_MODEL_FLAP" ]; then
          # model_invalid 와의 핑퐁(§18.8 재검토 MAJOR) — 임계 도달 시 opus 재전환을 멈추고 계정
          # 기본 모델에서 TTL 유계 대기(무증상 무한 스핀 방지).
          DRAIN_MODEL=""; TTL=$(( TTL - 1 )); MODEL_FLAP=0
          NEXT_FIRE_EPOCH=$(( now + DEFAULT_MINUTES * 60 ))
          log "burst 종료 rc=$rc dur=${dur}s newcommits=$newcommits — 모델전환 핑퐁 ${MAX_MODEL_FLAP}회 감지(이전 model=$prev_model) → 모델전환 이번 백오프 동안 중지(계정 기본 유지 — 리셋 뒤 재발 시 재시도) + +${DEFAULT_MINUTES}m 백오프 (ttl=$TTL)"
        else
          DRAIN_MODEL="opus"
          NEXT_FIRE_EPOCH=$(( now + SHORT_MINUTES * 60 ))
          log "burst 종료 rc=$rc dur=${dur}s newcommits=$newcommits — 모델별 한도 감지(이전 model=$prev_model) → opus 로 자동 전환, +${SHORT_MINUTES}m 재시도 (flap=$MODEL_FLAP/$MAX_MODEL_FLAP)"
        fi
      else
        MODEL_FLAP=0; TTL=$(( TTL - 1 )); NEXT_FIRE_EPOCH=$(( now + DEFAULT_MINUTES * 60 ))
        log "burst 종료 rc=$rc dur=${dur}s newcommits=$newcommits — opus 도 모델별 한도(pin 유지) → 리셋시각 정보 없음, +${DEFAULT_MINUTES}m 폴백 대기 (ttl=$TTL)"
      fi
    elif [ "$usage_limit" = "1" ]; then
      TTL=$(( TTL - 1 )); NOPROG=0; BACKOFF_STREAK=0; MODEL_FLAP=0
      reset_ep=$(parse_reset_epoch "$runlog")
      if [ -n "$reset_ep" ]; then
        NEXT_FIRE_EPOCH=$(( reset_ep + RESET_BUFFER_SEC ))   # CLI 가 알려준 실제 리셋 시각 + 버퍼
        log "burst 종료 rc=$rc dur=${dur}s newcommits=$newcommits — usage-limit 감지(pin 유지) → 실제 리셋 $(date -d "@${reset_ep}" '+%H:%M')+${RESET_BUFFER_SEC}s 재개 (next=$(date -d "@${NEXT_FIRE_EPOCH}" '+%F %T'), ttl=$TTL)"
      else
        NEXT_FIRE_EPOCH=$(( now + DEFAULT_MINUTES * 60 ))    # 폴백: 리셋 시각 파싱 실패 → 고정 +310m
        log "burst 종료 rc=$rc dur=${dur}s newcommits=$newcommits — usage-limit 감지(pin 유지, 리셋시각 파싱 실패) → +${DEFAULT_MINUTES}m 폴백 (ttl=$TTL)"
      fi
    elif [ "$context_dead" = "1" ]; then
      DRAIN_SESSION_ID=""; NEXT_FIRE_EPOCH=$(( now + SHORT_MINUTES * 60 )); NOPROG=0; BACKOFF_STREAK=0; MODEL_FLAP=0
      log "burst 종료 rc=$rc dur=${dur}s newcommits=$newcommits — context 소진(Prompt too long) → pin 해제, 다음 fire 새 세션 +${SHORT_MINUTES}m"
    elif [ "$progressed" = "1" ]; then
      NOPROG=0; BACKOFF_STREAK=0; MODEL_FLAP=0; NEXT_FIRE_EPOCH=$(( now + SHORT_MINUTES * 60 ))
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
