#!/usr/bin/env bash
# =============================================================================
# bin/lib/quiesce.sh — 진행 중 사용자 run quiesce 게이트 (source 전용 라이브러리)
#
# CHG-20260812T200000: `deploy-web.sh` 안에만 있던 게이트를 **여기로 옮겨 단일 정본**으로 만든다.
# 계기 = 2026-08-12 17:30 사고: 게이트웨이가 **배포 스파인 밖에서** recreate 되어 진행 중이던
# 대화가 죽었다(`deploy-web.sh` lock mtime 은 그 시각 이전 값 그대로였고, 배포는 17:49·18:07 에
# 따로 돌았다 = 이 recreate 는 배포 경로가 아니다). 게이트가 배포 스크립트 **안에만** 있으면
# `docker compose up -d` · `make up` · 단일 서비스 재기동 같은 정상적인 운영 동작이 전부
# 사각지대가 된다. 그래서 게이트를 라이브러리로 분리하고 `bin/safe-recreate.sh` 가 같은 것을
# 쓰게 해, **인가된 재생성 경로는 모두 같은 판정**을 통과하게 한다.
#
# 사용법(호출측이 아래를 준비한 뒤 source):
#   log()/warn()/err()/step()  — 미정의 시 기본 구현 주입
#   DC=(docker compose -f docker-compose.yml)      — 필수
#   DC_PROD=("${DC[@]}")                            — 미정의 시 DC 로 대체
#   REPLICAS=(web-a web-b)                          — 미정의 시 기본값
#   replica_cid()/replica_active_streams()          — 미정의 시 기본 구현 주입
#   DRY_RUN / FORCE_BUSY                            — 미정의 시 0
#
# 호출: `quiesce_gate "<라벨>"` → 0 진행 가능 / 1 중단(fail-closed). 말미에 `quiesce_summary`.
# =============================================================================

# ── 호출측이 안 준 것만 기본값으로 채운다(deploy-web.sh 는 자기 것을 그대로 쓴다) ──
declare -F log  >/dev/null 2>&1 || log()  { printf '[quiesce] %s\n' "$*" >&2; }
declare -F warn >/dev/null 2>&1 || warn() { printf '[quiesce] WARN: %s\n' "$*" >&2; }
declare -F err  >/dev/null 2>&1 || err()  { printf '[quiesce] ERROR: %s\n' "$*" >&2; }
declare -F step >/dev/null 2>&1 || step() { printf '\n[quiesce] === %s ===\n' "$*" >&2; }
: "${DRY_RUN:=0}"
: "${FORCE_BUSY:=0}"
if ! declare -p DC >/dev/null 2>&1; then DC=(docker compose -f docker-compose.yml); fi
if ! declare -p DC_PROD >/dev/null 2>&1 || [ "${#DC_PROD[@]}" -eq 0 ]; then DC_PROD=("${DC[@]}"); fi
if ! declare -p REPLICAS >/dev/null 2>&1 || [ "${#REPLICAS[@]}" -eq 0 ]; then REPLICAS=(web-a web-b); fi
declare -F replica_cid >/dev/null 2>&1 || replica_cid() { "${DC_PROD[@]}" ps -q "$1" 2>/dev/null | head -1; }
# 보고 누산 변수 — 라이브러리를 단독으로 source 하는 호출측(safe-recreate.sh · make quiesce-guard)이
# 이걸 초기화하지 않으면 `quiesce_summary` 가 빈 값으로 산술 비교해 깨진다(라이브 검증에서 적발:
# `[: : integer expression expected`). deploy-web.sh 는 자기 것을 이미 갖고 있어 영향 없다.
: "${QUIESCE_REPORT:=}"
: "${QUIESCE_FORCED:=0}"

# ── 진행 중 사용자 run quiesce 게이트 (CHG-20260812T140000) ────────────────────
# 워커·gateway 는 web 과 달리 **실제 상태 신호 없이 눈감고 재는 타이머**(stop_grace_period)로
# 교체돼 왔다. 실측(30일 ask_jobs 363건)은 그 타이머가 분포 안쪽임을 보여준다 —
#   agent run: p50 81s · p95 691s · max 2,024s · **60초 초과 66%**  vs ask-worker drain 60s
#   LLM 라운드: p95 182s                                            vs gateway grace 120s(당시)
# 즉 배포마다 진행 중 사용자 run 의 상당수가 SIGKILL 됐고, `FR-ask-orphan-redeploy-dead-air`
# 의 회수 로직은 **죽은 뒤의 복구**였을 뿐 안 죽이는 장치가 아니었다.
# 반대편 실측: 시스템은 30일 중 **2.1% 만 busy**(363런 × 평균 152초). 조용한 순간을 기다리는
# 것이 현실적이다 → web 의 `predrain` 과 같은 방식(실제 신호 + fail-closed)으로 대칭 적용한다.
QUIESCE_TIMEOUT="${DEPLOY_QUIESCE_TIMEOUT:-900}"        # 조용해지기를 기다리는 상한(초)
QUIESCE_POLL="${DEPLOY_QUIESCE_POLL:-5}"                # 폴링 간격(초)
QUIESCE_HEARTBEAT_FRESH="${DEPLOY_QUIESCE_HEARTBEAT_FRESH:-90}"  # 이보다 오래 heartbeat 끊긴 running = '좀비 의심' 으로 **분리 계상**(제외 아님 — 패널 P1-4)
QUIESCE_SETTLE="${DEPLOY_QUIESCE_SETTLE:-3}"            # 조용함 확인 후 재확인 간격(스냅샷 1장의 착시 방지 — 패널 P1-3)
QUIESCE_PG_SERVICE="${DEPLOY_QUIESCE_PG_SERVICE:-postgres}"
# ── 진행 중 사용자 run 관측 (CHG-20260812T140000) ─────────────────────────────
# 신호 2종을 **합산**한다 — 실행 dispatch 가 worker/inprocess 두 모드라(TASK-0169) 한쪽만 보면
# 다른 모드에서 게이트가 **공허하게 통과**한다(0 을 조용함으로 오독).
#   (a) `ask_jobs.status='running'` — worker 모드의 정본. heartbeat 가 끊긴 좀비는 세지 않는다
#       (안 그러면 죽은 워커 한 줄이 배포를 영구 차단한다).
#   (b) web replica 의 `active_streams` — inprocess 모드의 실행 자체 + worker 모드의 답변 attach
#       long-poll. 다운로드 스트림도 섞여 보수적이지만, 유휴 98% 환경에서 비용이 없다.
_ask_jobs_count() {  # $1 = 추가 술어 → 정수 | "unknown"
  local out
  out="$("${DC[@]}" exec -T "$QUIESCE_PG_SERVICE" sh -lc \
    "psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -tAc \"SELECT count(*) FROM agent_runtime.ask_jobs WHERE status='running' AND $1\"" \
    2>/dev/null | tr -d '[:space:]')"
  case "$out" in (''|*[!0-9]*) echo "unknown" ;; (*) echo "$out" ;; esac
}

running_ask_jobs() {        # heartbeat 신선 = 확실히 살아 있는 run
  _ask_jobs_count "heartbeat_at > now() - interval '${QUIESCE_HEARTBEAT_FRESH} seconds'"
}

# §18.8 패널 P1-4: 오래된 heartbeat 를 "죽었다" 로 **단정하지 않는다**. 살아 있는 워커도 PG 연결이
# 잠깐 흔들리면 heartbeat 를 놓칠 수 있고, 그 사이에도 LLM 호출은 계속된다(worker 모드에서
# `active_streams` 는 그 호출을 대변하지 않는다). 초판은 이 행을 조용히 제외해 "조용함" 으로
# 읽었는데, 그것이 곧 살아 있는 run 을 죽이는 경로다. 별도로 세어 **차단하되 구분해 로그**한다 —
# 진짜 좀비면 stale sweeper 가 곧 pending 으로 되돌리고, 그래도 남으면 사람이 --force-busy 로 판단한다.
stale_running_ask_jobs() {
  _ask_jobs_count "(heartbeat_at IS NULL OR heartbeat_at <= now() - interval '${QUIESCE_HEARTBEAT_FRESH} seconds')"
}

# §18.8 패널 P1-1: `ask_jobs` 는 **worker 모드에서만** 사용자 run 의 정본이다. 코드 기본값은
# `inprocess`(shared/config.py)이고 그 모드에서 `/api/ask` 는 `asyncio.to_thread` 로 web 안에서
# 직접 돌며 **ask_jobs 행을 만들지 않는다**. 게다가 `/livez` 의 `active_streams` 는 CSV export 와
# SSE 프롬프트 자동작성만 세고 `/api/ask` 를 세지 않는다(라이브 코드 확인). 즉 inprocess 모드에서
# 이 게이트는 **아무것도 못 보고 항상 '조용함'** 이 된다 — 있으나 마나가 아니라 더 나쁘다(무중단
# 이라고 믿게 만든다). 그래서 모드를 실측해 worker 가 아니면 통과시키지 않는다.
ask_execution_mode() {  # → worker | <other> | "unknown"
  local svc out rc
  for svc in "${REPLICAS[@]}"; do
    replica_cid "$svc" >/dev/null 2>&1 || continue
    # ⚠ **exec 실패와 "env 미설정" 을 구분한다**(라이브 검증에서 적발): 컨테이너가 재생성 중이면
    # `exec` 가 "is restarting" 으로 실패해 빈 문자열을 준다. 초판은 그것을 "env 미설정 =
    # 코드 기본값 inprocess" 로 읽어 **엉뚱한 사유로 게이트를 막았다**(진단이 오도된다).
    # 실패 = unknown(관측 불가), 성공+빈값 = 실제로 미설정 → 코드 기본값 inprocess.
    out="$("${DC_PROD[@]}" exec -T "$svc" printenv AGENT_ASK_EXECUTION_MODE 2>/dev/null)"; rc=$?
    out="$(printf '%s' "$out" | tr -d '[:space:]')"
    if [ "$rc" -ne 0 ] && [ -z "$out" ]; then continue; fi   # 이 replica 로는 못 읽었다 → 다음 replica
    [ -n "$out" ] && { printf '%s' "$out" | tr 'A-Z' 'a-z'; return 0; }
    echo "inprocess"; return 0
  done
  echo "unknown"
}

# ⚠ `replica_active_streams` 를 그대로 쓰지 않는다 — 그 헬퍼는 **조회 실패도 0 으로** 돌려준다
# (`|| echo 0` + 내부 python 의 fallback). pre-drain 에서는 그 관용이 "스트림이 없다고 보고
# 진행" 이라는 보수적이지 않은 기본값일 뿐이지만, **이 게이트에서는 그것이 곧 vacuous pass** 다
# (조회가 깨진 배포는 항상 '조용함' 으로 통과해 아무것도 지키지 못한다). 그래서 실패를 **명시적
# 비-0 종료**로 구분하는 전용 probe 를 쓰고, 읽지 못한 replica 는 0 이 아니라 unknown 으로 센다.
replica_active_streams_strict() {  # $1 = svc → 정수(성공) | 비-0 종료(조회 실패)
  "${DC_PROD[@]}" exec -T "$1" python -c '
import json,ssl,sys,urllib.request
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
for url in ("https://localhost:8000/livez","http://localhost:8000/livez"):
    try:
        r=urllib.request.urlopen(url,timeout=5,context=ctx if url.startswith("https") else None)
        print(int(json.loads(r.read().decode()).get("active_streams",0))); sys.exit(0)
    except Exception:
        continue
sys.exit(3)   # 두 스킴 모두 실패 = "읽지 못했다"(0 아님)
' 2>/dev/null
}

web_active_streams_total() {  # → 정수 | "unknown"
  local svc n total=0 seen=0 unread=0
  for svc in "${REPLICAS[@]}"; do
    replica_cid "$svc" >/dev/null 2>&1 || continue   # 존재하지 않는 replica 는 셀 대상이 아니다
    if ! n="$(replica_active_streams_strict "$svc")"; then unread=1; continue; fi
    case "$n" in (''|*[!0-9]*) unread=1; continue ;; esac
    total=$(( total + n )); seen=1
  done
  # 존재하는 replica 중 **하나라도 못 읽었으면** 합계를 신뢰할 수 없다 — 못 읽은 쪽에 스트림이
  # 남아 있을 수 있으므로 0 으로 보고하면 안 된다.
  if [ "$unread" -eq 1 ]; then echo "unknown"; return 0; fi
  [ "$seen" -eq 1 ] && echo "$total" || echo "unknown"
}

# ⚠ **fail-closed 결정 지점** — "지금 이 컴포넌트를 내려도 되는가". `predrain` 과 같은 자세다:
# 중단하면 구버전이 계속 서빙해 무중단이 유지되지만, 강행하면 정확히 우리가 고치려는
# "진행 중 사용자 요청이 죽는" 사고가 재현된다. 그래서 timeout·관측불가 모두 **중단**이고,
# 강행은 `--force-busy` 로 사람이 명시할 때만 — 그때도 무엇을 끊는지 로그로 남긴다.
# 한 번의 관측 → "fresh|stale|streams" (각각 정수 또는 unknown).
quiesce_sample() { printf '%s|%s|%s' "$(running_ask_jobs)" "$(stale_running_ask_jobs)" "$(web_active_streams_total)"; }

# 표본이 "확실히 조용함" 인가 — **unknown 은 조용함이 아니다**(§18.8 패널 P1-2).
# 초판은 한쪽이 관측되면 다른 쪽 unknown 을 0 으로 읽었는데, 두 신호는 서로 다른 차원을
# 덮으므로(worker 큐 vs web 스트림) 한쪽으로 다른 쪽을 대신 증명할 수 없다.
quiesce_sample_is_quiet() {  # $1 = "fresh|stale|streams" → 0 조용 / 1 아님(또는 미확인)
  local f s w; IFS='|' read -r f s w <<<"$1"
  case "$f|$s|$w" in (*unknown*) return 1 ;; esac
  [ "$f" -eq 0 ] && [ "$s" -eq 0 ] && [ "$w" -eq 0 ]
}

quiesce_user_runs() {  # $1 = 대상 라벨 → 0 조용함(내려도 됨) / 1 아님(중단)
  local label="$1" deadline=$(( SECONDS + QUIESCE_TIMEOUT )) smp f s w waited=0 last_report=0 mode
  step "quiesce 게이트: 진행 중 사용자 run 이 끝나기를 대기 ($label, 상한 ${QUIESCE_TIMEOUT}s)"
  [ "$DRY_RUN" -eq 1 ] && { log "[dry-run] quiesce skip"; return 0; }
  # 0) 실행 모드 게이트 — ask_jobs 가 정본인 모드인지 먼저 확인한다(패널 P1-1).
  mode="$(ask_execution_mode)"
  if [ "$mode" != "worker" ]; then
    # ⚠ 백틱을 쓰지 않는다 — 큰따옴표 안의 `...` 는 **명령 치환**이라 메시지가 깨지고 엉뚱한
    # 명령이 실행된다(라이브 검증에서 `/livez` 실행 시도로 적발 — 초판의 실제 버그).
    err "$label: 실행 모드가 '$mode' 다 — 이 모드의 /api/ask 는 ask_jobs 행을 만들지 않고"
    err "  /livez 의 active_streams 도 그 요청을 세지 않는다(CSV/SSE 전용). 즉 게이트가 진행 중"
    err "  run 을 **볼 수 없다** — '조용함' 으로 통과시키면 무중단이라고 오인하게 만든다."
    err "  worker 모드(AGENT_ASK_EXECUTION_MODE=worker)로 운영하거나, 인지한 상태에서 --force-busy."
    return 1
  fi
  while :; do
    smp="$(quiesce_sample)"; IFS='|' read -r f s w <<<"$smp"
    if quiesce_sample_is_quiet "$smp"; then
      # 1) settle 재확인 — 한 장의 스냅샷은 "그 순간" 만 말한다. 곧바로 recreate 로 넘어가면
      #    그 사이 들어온 run 이 죽는다(패널 P1-3). 짧은 간격으로 한 번 더 보고 둘 다 조용할
      #    때만 진행한다. **완전한 admission barrier 는 아니다** — 잔여 창은 정직하게 남기고
      #    문서에 명시한다(앱측 fence 는 별 cycle).
      sleep "$QUIESCE_SETTLE"
      smp="$(quiesce_sample)"
      if quiesce_sample_is_quiet "$smp"; then
        log "  $label: 진행 중 run 0 (settle ${QUIESCE_SETTLE}s 재확인, 대기 ${waited}s) — 교체 진행."
        return 0
      fi
      IFS='|' read -r f s w <<<"$smp"
      log "  $label: settle 재확인에서 신규 run 감지(fresh=$f stale=$s streams=$w) — 계속 대기."
    fi
    if [ "$SECONDS" -ge "$deadline" ]; then
      err "$label: quiesce timeout(${QUIESCE_TIMEOUT}s) — ask_jobs fresh=$f · stale=$s · web streams=$w."
      case "$f|$s|$w" in (*unknown*)
        err "  (unknown = 관측 실패. '조용한지 알 수 없다' 를 '조용하다' 로 읽지 않는다.)"
        err "  진단: ${DC[*]} exec -T $QUIESCE_PG_SERVICE sh -lc 'psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -tAc \"select 1\"'" ;;
      esac
      err "  지금 내리면 그 요청들이 끊긴다(= 이 게이트가 막으려는 바로 그 사고). 현 상태 유지 후 재실행(멱등)."
      err "  즉시 진행이 필요하면 --force-busy (끊기는 요청 수를 위 값으로 인지한 상태에서만)."
      return 1
    fi
    # 진행 상황을 30초마다 한 줄 — 조용히 오래 기다리면 '멈춘 배포'로 오인된다.
    if [ $(( waited - last_report )) -ge 30 ] || [ "$waited" -eq 0 ]; then
      log "  $label: ask_jobs fresh=$f · stale=$s · web streams=$w — 대기 중(${waited}s/${QUIESCE_TIMEOUT}s)"
      last_report="$waited"
    fi
    sleep "$QUIESCE_POLL"; waited=$(( waited + QUIESCE_POLL ))
  done
}

quiesce_gate() {  # $1 = 라벨 → 0 진행 가능. --force-busy 면 관측 결과만 남기고 통과.
  if quiesce_user_runs "$1"; then
    QUIESCE_REPORT="${QUIESCE_REPORT}${QUIESCE_REPORT:+ · }$1=quiet"
    return 0
  fi
  if [ "$FORCE_BUSY" -eq 1 ]; then
    warn "$1: --force-busy 지정 — quiesce 미달성 상태로 강행한다. 위에 표시된 진행 중 요청은 끊긴다."
    QUIESCE_REPORT="${QUIESCE_REPORT}${QUIESCE_REPORT:+ · }$1=FORCED(진행 중 요청 끊김)"
    QUIESCE_FORCED=$(( QUIESCE_FORCED + 1 ))
    return 0
  fi
  QUIESCE_REPORT="${QUIESCE_REPORT}${QUIESCE_REPORT:+ · }$1=ABORTED"
  return 1
}

# LRN-20260811T1557("성공 보고 ≠ 무중단")의 직접 적용: 게이트가 통과했는지·강행했는지를
# 배포 말미에 **반드시** 한 줄로 남긴다. 조용히 통과하면 다음 사람이 "무중단이었다" 고
# 읽는데, --force-busy 로 끊고 지나간 배포도 똑같이 "배포 완료" 로 보이기 때문이다.
quiesce_summary() {
  if [ -z "$QUIESCE_REPORT" ]; then
    log "quiesce: 미수행(scope=web — ask-worker/gateway 미접촉)"
  elif [ "$QUIESCE_FORCED" -gt 0 ]; then
    warn "quiesce: $QUIESCE_REPORT — **강행 ${QUIESCE_FORCED}회**. 이 배포는 무중단이 아니었다."
  else
    log "quiesce: $QUIESCE_REPORT — 진행 중 사용자 run 을 끊지 않았다."
  fi
}
