#!/usr/bin/env bash
# =============================================================================
# deploy-web.sh — feature-0014: web 무중단(zero-downtime) 롤링 배포 스파인.
#                 feature-0020: 워커(insight/ask)·bedrock-gateway·caddy 이미지까지
#                 같은 스파인에서 무중단 롤아웃(전 배포 대상 커버리지 완성).
#
# Caddy LB(web-a:8000 web-b:8000) 뒤에서 web replica 를 한 번에 하나씩 재시작해
# 항상 ≥1 healthy upstream 을 유지한다. 고병렬 자동배포(deploy_scope: included)에서
# 무인 실행되도록 직렬화·검증·자동 롤백을 모두 포함한다. web swap + soak 통과 후
# 워커를 build-once 핀 이미지로 순차 recreate(graceful SIGTERM + healthy 게이트 +
# last-good 롤백)하고, bedrock-gateway 는 드리프트 시에만 surge replica 로 무중단
# 교체한다(상세: unit/feature-0020-zd-deploy-all/docs/FUNCTION.md).
#
# === 실행 모델 (중요) ============================================================
# 본 호스트는 docker 그룹 미소속이라 docker 에 sudo 가 필요하다. AGENTS.md §22.12 §1
# (`--dangerously-skip-permissions` 는 sudo 와 병용 불가, wrapper 한정 scoped NOPASSWD
# 만 허용)에 따라 **전체 스크립트를 한 번의 권한 전환으로** 실행한다:
#
#     sudo -E bin/deploy-web.sh [...]
#
# 내부 docker/compose/make 호출은 절대 다시 sudo 하지 않는다(단일 경계). 무인 실행을
# 위해 다음 sudoers 를 1회 설정한다(NEVER `NOPASSWD: ALL`, NEVER `NOPASSWD: docker`):
#     <deploy-user> ALL=(root) NOPASSWD: /abs/path/repo/bin/deploy-web.sh
#
# === 적대적 검증(wf_f176026a) 반영 ============================================
#  - flock 전체 배포 직렬화 + origin/main HEAD 로 coalesce(loser 가 최신 커밋을 누락하지 않음)
#  - 프로덕션 file-set 격리(-f docker-compose.yml only) + web-a/web-b 호스트포트 부재 단언
#  - TLS preflight(SAN/CA/expiry) — 두 replica 공유 cert 의 correlated 실패를 사전 차단
#  - migrate-lint hard gate(expand/contract) → migrate(expand) → swap 순서
#  - build-once(image pin by SHA) + last-good 유지 → 빠른 롤백(재빌드 없음)
#  - one-at-a-time + pre-drain(상대 ready 확인 + 대상 active_streams==0 대기) + /readyz 게이트
#  - quiesce 게이트(CHG-20260812T140000): gateway 교체 **직전**에 진행 중 사용자 run
#    (ask_jobs running + web active_streams)이 0 이 되기를 기다린다. 종전엔 실제 상태를 보지 않고
#    stop_grace 타이머로 죽였는데 실측 run 의 66%가 그 예산보다 길었다. web 의 pre-drain 과 같은
#    fail-closed 자세 — 못 기다리면 강행이 아니라 **중단**(구버전이 계속 서빙 = 무중단 유지).
#  - ask-worker surge 교대(CHG-20260814T120000): ask-worker 는 위 게이트를 **쓰지 않는다**.
#    전역 정적을 기다리는 방식은 바쁜 시간대에 창이 열리지 않아 배포가 완결되지 못했고(실측:
#    유입 7~10분 간격 + run p95 691s → 상한 900s 안에 정적 창 없음), 순차 롤아웃이라 뒤 워커까지
#    연쇄로 묶였다. ask-worker 는 HTTP 소켓이 아니라 **PG 큐 소비자**라 신규 job 을 받는 쪽을
#    먼저 세울 수 있다 — surge 기동 → 본체는 자기 in-flight 만 완주 → 본체 교체 → surge 정리.
#    "조용해지기를 기다린다" 가 아니라 "받는 쪽을 먼저 세운다".
#  - 워커 실패 격리 + 완결 판정: 한 워커의 미교체가 무관한 워커를 막지 않는다. 대신 배포 말미에
#    **컨테이너에서 GIT_COMMIT 을 다시 읽어** 전부 도달했을 때만 완결로 기록한다(부분 완료를
#    완료로 보고하지 않는다 — 그것이 다음 배포의 멱등 skip 을 오염시킨다).
#  - post-cutover soak(RestartCount/edge 감시) + 자동 롤백; bad-image vs dependency-down 구분
#  - web 롤링 자체는 web-a/web-b 만 지정(--no-deps). 워커 롤아웃은 soak 통과 후
#    별도 phase 에서 수행(feature-0020 — 구 "worker 미접촉 + WARN-only" 를 대체)
#
# Usage:
#   sudo -E bin/deploy-web.sh                 # origin/main HEAD 로 전체 롤아웃(web+워커+gateway)
#   sudo -E bin/deploy-web.sh --web-only      # web(+caddy reconcile)만 — 기존 feature-0014 범위
#   sudo -E bin/deploy-web.sh --workers-only  # 워커+gateway 만 (마이그 없는 워커 코드/설정 변경 전용)
#   sudo -E bin/deploy-web.sh --force-gateway # gateway 드리프트 무관 surge 교체 강제
#   sudo -E bin/deploy-web.sh --force-busy    # gateway quiesce 미달성에도 강행(진행 중 요청이 끊길 수 있음)
#                                             # ask-worker 는 surge 교대라 이 플래그와 무관하다.
#   sudo -E bin/deploy-web.sh --rollback      # last-good 이미지로 롤백(web + 워커)
#   sudo -E bin/deploy-web.sh --dry-run       # 명령만 출력(상태 변경 없음)
#   sudo -E bin/deploy-web.sh --help
#
# Exit codes: 0 성공/no-op, 1 실패(배포 안 됨 또는 롤백됨), 2 usage/preflight 차단.
#
# Requires: bash>=4, git, docker(+compose v2), flock, openssl, awk, grep, sed.
# =============================================================================
set -euo pipefail

# ── 경로/상수 ────────────────────────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="$(cd "$REPO_ROOT/.." && pwd)"
cd "$REPO_ROOT"

ARTIFACTS="$PROJECT_ROOT/artifacts"
LOCK_DIR="$ARTIFACTS/locks"
STATE_DIR="$ARTIFACTS/deploy"
CERT_ROOT="$ARTIFACTS/certs"
LOCK_FILE="$LOCK_DIR/deploy-web.lock"
STATE_FILE="$STATE_DIR/deploy-web.state"
LASTGOOD_FILE="$STATE_DIR/deploy-web.last-good"
PIN_FILE="$STATE_DIR/docker-compose.deploy-pin.yml"

IMAGE_REPO="mysql-ai-web"
REPLICAS=(web-a web-b)
BASE_BRANCH="origin/main"
LOCK_WAIT_SECONDS="${DEPLOY_WEB_LOCK_WAIT:-600}"
READY_TIMEOUT="${DEPLOY_WEB_READY_TIMEOUT:-120}"
# feature-0045: 90 → 180. 종전 값은 SSE/CSV 스트림만 기다리던 시절의 예산이다. 이제 개인 AI 의
# 도구 호출 왕복(MCP→web `EXT_TOOL_TIMEOUT_SEC=120`)까지 기다리므로, 상한이 그보다 작으면
# **가장 오래 걸리는 조사가 항상 잘리는** 예산이 된다. in-flight 가 0 이면 즉시 통과하므로
# 유휴 시 배포 시간에는 영향이 없다(실측: 시스템은 대부분 조용하다).
PREDRAIN_TIMEOUT="${DEPLOY_WEB_PREDRAIN_TIMEOUT:-180}"
SOAK_SECONDS="${DEPLOY_WEB_SOAK:-90}"
EDGE_FLAP_MAX="${DEPLOY_WEB_EDGE_FLAP_MAX:-4}"   # soak 창 내 비연속 edge 실패 누적 임계(하드닝 2026-07-11, 패널 MINOR-1)
IMAGE_KEEP="${DEPLOY_WEB_IMAGE_KEEP:-3}"
EDGE_AVAIL_TIMEOUT="${DEPLOY_WEB_EDGE_AVAIL_TIMEOUT:-60}"   # 엣지 후보 복귀 대기 상한(2026-08-11, no-upstreams-503 근본수정)
EDGE_DEGRADE_FLOOR="${DEPLOY_WEB_EDGE_DEGRADE_FLOOR:-30}"   # admin 조회 불가 시 최소 대기(관측된 최악 fail_duration)
CADDY_ADMIN_URL="${DEPLOY_WEB_CADDY_ADMIN_URL:-http://127.0.0.1:2019}"  # Caddy admin API(컨테이너 loopback 전용)

# feature-0020: 워커·gateway 롤아웃 상수
AGENT_IMAGE_REPO="mysql-ai-agent"                # insight/ask/ops 워커 공용 이미지(동일 Dockerfile build-once)
# feature-0039: ops-scheduler 도 같은 agent 이미지를 쓰므로 워커 롤아웃 대상에 포함한다.
# 빠지면 정기 잡(백업·복원 리허설·그래프 sync)이 배포 후에도 구 이미지로 계속 돈다 —
# "배포는 됐는데 잡만 stale" 은 조용히 오래 가는 종류의 결함이다.
# feature-0041: ext-tool-mcp(외부 AI 도구 표면 MCP HTTP 전송) 도 같은 agent 이미지를 쓴다.
#   롤아웃 대상에서 빠지면 이미지만 새로 빌드되고 이 컨테이너는 **구코드로 계속 도는**
#   드리프트가 생긴다(서비스별 GIT_COMMIT 불일치 — 배포 완료 판정의 근거가 흔들린다).
# feature-0045: 그 MCP 표면을 WORKERS 에서 **분리**한다. 워커 롤아웃은 `up -d --force-recreate`
#   한 방이라 단일 컨테이너였던 이 서비스는 배포마다 통째로 끊겼다 — 개인 AI 가 붙어 있는
#   바로 그 연결이다. 이제 web 과 같은 2 replica 구조라 one-at-a-time 롤링을 따로 받는다.
WORKERS=(insight-worker ask-worker ops-scheduler)
# 브리지 MCP 표면 replica. Caddy LB(`/api/ai/mcp`) 뒤에서 한 번에 하나씩 교체한다.
MCP_REPLICAS=(ext-tool-mcp-a ext-tool-mcp-b)
# 구 단일 서비스명 — compose 에서 사라졌으므로 남은 컨테이너를 배포가 정리한다.
MCP_LEGACY_SERVICE="ext-tool-mcp"
# feature-0020 zd-ask-rollout: ask-worker 는 큐 소비자라 surge 교대가 성립한다(상세는
# rollout_ask_worker_via_surge 헤더). 전역 정적(quiesce) 대기를 대체한다.
ASK_WORKER_SERVICE="ask-worker"
ASK_WORKER_SURGE="ask-worker-surge"
# 본체/surge 를 내릴 때 주는 **완주 예산**. compose stop_grace_period(1830s)보다 작아야
# 반납 로직이 SIGKILL 전에 끝난다. 실측 run max 2,024s 를 전부 덮지는 않는다 — 덮지 못한
# 꼬리는 종전과 동일하게 재큐되고, 그 사실은 배포 말미에 보고된다(조용히 넘기지 않는다).
ASK_DRAIN_TIMEOUT="${DEPLOY_ASK_DRAIN_TIMEOUT:-1800}"
AGENT_LASTGOOD_FILE="$STATE_DIR/deploy-agent.last-good"
WORKER_READY_TIMEOUT="${DEPLOY_WORKER_READY_TIMEOUT:-300}"    # insight 최악 unhealthy 확정(start 60s+60s×3=240s)보다 여유(리뷰 m-3 — 경계 동률 false-fail 방지)
GATEWAY_READY_TIMEOUT="${DEPLOY_GATEWAY_READY_TIMEOUT:-180}"
GATEWAY_SERVICE="bedrock-gateway"
GATEWAY_SURGE="bedrock-gateway-surge"
GATEWAY_CONFIG_FILE="unit/feature-0007-bedrock-llm-provider/src/config/litellm_config.yaml"

# ── 진행 중 사용자 run quiesce 게이트 ─────────────────────────────────────────
# CHG-20260812T200000: 구현을 `bin/lib/quiesce.sh` 로 옮겼다 — **배포 스파인 밖의 재생성**
# (수동 `docker compose up -d`·`make up`·단일 서비스 재기동)도 같은 게이트를 통과해야 하는데,
# 게이트가 이 스크립트 안에만 있으면 그 경로 전부가 사각지대다(2026-08-12 17:30 사고가 정확히
# 그 경로였다). `bin/safe-recreate.sh` 가 같은 라이브러리를 쓴다 — 판정이 갈라지지 않는다.
# knob(DEPLOY_QUIESCE_*) 정의와 게이트 함수는 그 파일이 소유한다.
_QUIESCE_LIB="$(dirname "${BASH_SOURCE[0]}")/lib/quiesce.sh"
[ -r "$_QUIESCE_LIB" ] || { printf '[deploy-web] ERROR: quiesce 라이브러리 없음(%s) — 게이트 없이 배포하지 않는다.\n' "$_QUIESCE_LIB" >&2; exit 2; }


DRY_RUN=0
MODE="deploy"   # deploy | rollback
SCOPE="all"     # all | web | workers (feature-0020)
FORCE_GATEWAY=0
FORCE_BUSY=0    # --force-busy: quiesce 미달성에도 강행(진행 중 run 이 끊길 수 있음)
QUIESCE_REPORT=""   # 게이트별 결과(quiet|FORCED|ABORTED) — 배포 말미 정직 보고용
QUIESCE_FORCED=0    # 강행 횟수(>0 이면 이 배포는 무중단이 아니다)
# feature-0045: pre-drain 이 상한 안에 조용해지지 못해 **진행 중인 브리지 왕복을 끊고** 간 횟수.
# >0 이면 배포 말미에 점유 회수(`reclaim_bridge_claims`)를 돌린다 — 평상시엔 돌지 않는다.
PREDRAIN_FORCED=0
# 배포 창의 시작(epoch). 점유 회수는 **이 시각 이후에 점유된 것만** 되돌린다 — 상한만 두면
# 배포와 무관하게 오래 조사 중이던 작업까지 대기열로 되돌려, 다른 세션이 재점유하는 순간
# 원 소유자의 제출이 거절된다(끊기지도 않은 작업을 배포가 버리는 셈).
DEPLOY_WINDOW_START="$(date +%s)"
# 드레인을 **걸지 못한 채** 진행한 횟수(probe 실패 → 기존 게이트로 대체). 끊김이 없었다고
# 단정할 수 없는 상태이므로 보고에 남긴다 — "무중단이었다" 를 기본값으로 두지 않는다.
PREDRAIN_UNVERIFIED=0

# base file-set ONLY — dev override(override.yml)/self-TLS/호스트포트를 머지하지 않는다.
DC=(docker compose -f docker-compose.yml)

# ── 로깅 ─────────────────────────────────────────────────────────────────────
log()  { printf '[deploy-web] %s\n' "$*" >&2; }
step() { printf '\n[deploy-web] === %s ===\n' "$*" >&2; }
warn() { printf '[deploy-web] WARN: %s\n' "$*" >&2; }
err()  { printf '[deploy-web] ERROR: %s\n' "$*" >&2; }
die()  { err "$*"; exit 1; }
die2() { err "$*"; exit 2; }

run() {  # dry-run 인지 명령 실행 래퍼
  if [ "$DRY_RUN" -eq 1 ]; then printf '[dry-run] %s\n' "$*" >&2; return 0; fi
  "$@"
}

usage() { sed -n '2,62p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --rollback)      MODE="rollback"; shift ;;
    --dry-run)       DRY_RUN=1; shift ;;
    --web-only)      SCOPE="web"; shift ;;
    --workers-only)  SCOPE="workers"; shift ;;
    --force-gateway) FORCE_GATEWAY=1; shift ;;
    --force-busy)    FORCE_BUSY=1; shift ;;
    --help|-h)       usage 0 ;;
    *) die2 "알 수 없는 인자: $1" ;;
  esac
done
[ "$SCOPE" = "workers" ] && [ "$MODE" = "rollback" ] && die2 "--workers-only 와 --rollback 병용 불가 (롤백은 web+워커 일괄)."

# base file-set + surge profile (gateway surge 서비스 조작 전용 — 다른 서비스에 영향 없음)
DC_SURGE=(docker compose -f docker-compose.yml --profile deploy-surge)

# ── WEB_PUBLIC_HOST 로드 (.env, sudo -E 로 env 전달되면 그쪽 우선) ──────────────
WEB_PUBLIC_HOST="${WEB_PUBLIC_HOST:-$(sed -n 's/^WEB_PUBLIC_HOST=//p' .env 2>/dev/null | tail -1)}"
[ -n "${WEB_PUBLIC_HOST:-}" ] || die2 "WEB_PUBLIC_HOST 를 결정할 수 없습니다 (.env 또는 env)."
LEAF_CERT="$CERT_ROOT/$WEB_PUBLIC_HOST/fullchain.pem"
ROOT_CA="$CERT_ROOT/rootCA.pem"
CADDYFILE="unit/feature-0006-lan-proxy-access/src/caddy/Caddyfile"  # feature-0016: reconcile 대상

# ── preflight: 권한/소유권 ─────────────────────────────────────────────────────
preflight_privilege() {
  step "preflight: 권한"
  # 무인(headless/cron)에서 sudo 비밀번호 프롬프트로 hang 되지 않도록 사전 비대화 확인.
  if ! docker ps >/dev/null 2>&1; then
    die2 "docker 데몬 접근 불가. 'sudo -E bin/deploy-web.sh' 로 실행하거나 scoped NOPASSWD sudoers 를 설정하세요 (헤더 참조). NEVER 'NOPASSWD: ALL'."
  fi
  mkdir -p "$LOCK_DIR" "$STATE_DIR"
}

# 스크립트가 root 로 쓴 artifacts 산출물을 deploy-user 소유로 정규화(다음 non-root 실행 차단 방지).
normalize_ownership() {
  local owner
  owner="$(stat -c '%u:%g' "$ARTIFACTS" 2>/dev/null || echo '')"
  if [ -n "$owner" ] && [ "$DRY_RUN" -ne 1 ]; then
    chown -R "$owner" "$LOCK_DIR" "$STATE_DIR" 2>/dev/null || true
  fi
}

# ── preflight: 프로덕션 file-set 격리 ──────────────────────────────────────────
preflight_fileset() {
  step "preflight: 프로덕션 file-set 격리 (-f docker-compose.yml only)"
  # 하드닝(2026-07-11, feature-0014): `docker compose config` 가 간헐 실패하거나 불완전
  # 출력을 내는 flake 실측(같은 날 6회 중 3회 — 수동 프로브는 전건 통과, stderr 는
  # 2>/dev/null 로 유실돼 진단 불가였음. worktree 재현에서 env_file 대상 부재 같은 원인이
  # stderr 에만 나타남을 확인). ① stderr 포획 ② rc≠0 또는 web-a/b 미검출이면 2s backoff
  # 최대 3회 재시도 ③ 최종 실패 시 stderr·출력 헤더 덤프. 진짜 실패는 여전히 die.
  local cfg cfg_err rc attempt
  cfg_err="$(mktemp)"
  for attempt in 1 2 3; do
    cfg="$("${DC[@]}" config 2>"$cfg_err")" && rc=0 || rc=$?
    # 근본수정(2026-07-11 flake 진단 확정): `printf 145KB | grep -q` 는 grep 조기 종료가
    # printf 에 SIGPIPE 를 보내 pipefail 하에서 파이프라인이 141 로 실패 — 출력이 완전해도
    # "미검출"로 오판되는 타이밍 race(부하 의존 = 간헐성의 정체, 하드닝 진단 덤프
    # bytes=145878·서비스 29개 실측으로 특정). 파이프 대신 bash 부분문자열 매칭 사용.
    if [ "$rc" -eq 0 ] && [[ "$cfg" == *$'\n'"  web-a:"* ]] && [[ "$cfg" == *$'\n'"  web-b:"* ]]; then
      break
    fi
    if [ "$attempt" -lt 3 ]; then
      warn "compose config 이상(attempt=$attempt rc=$rc bytes=${#cfg}) — 2s 후 재시도. stderr: $(head -c 200 "$cfg_err" | tr '\n' ' ')"
      sleep 2
    fi
  done
  if [ "$rc" -ne 0 ]; then
    err "compose config 최종 실패(rc=$rc). stderr: $(head -c 400 "$cfg_err" | tr '\n' ' ')"
    rm -f "$cfg_err"
    die "docker compose config 실패 (base file-set)."
  fi
  # web-a/web-b 섹션에 published 포트가 있으면 --scale/replica 충돌 → 차단.
  local web_block
  web_block="$(printf '%s\n' "$cfg" | awk '/^  web-[ab]:/{f=1} /^  [a-z]/&&!/web-[ab]/{if(f&&!/^  web-[ab]/)f=0} f{print}')"
  if [[ "$web_block" == *"published:"* ]]; then
    die "web-a/web-b 에 호스트 포트(published)가 있습니다. 프로덕션은 Caddy :443 단일 진입이어야 합니다 (dev override 가 머지되었는지 확인). :18080 직접 문은 폐기되었습니다."
  fi
  if [[ "$cfg" != *$'\n'"  web-a:"* ]] || [[ "$cfg" != *$'\n'"  web-b:"* ]]; then
    err "config 출력 진단: bytes=${#cfg} head=[$(printf '%s' "$cfg" | head -3 | tr '\n' '|')] 서비스라인=$(printf '%s\n' "$cfg" | grep -c '^  [a-z][a-z-]*:' || true) stderr(3차)=$(head -c 200 "$cfg_err" | tr '\n' ' ')"
    rm -f "$cfg_err"
    die "web-a/web-b 서비스가 base compose 에 없습니다 (토폴로지 미적용 — 3회 재시도 후에도 미검출)."
  fi
  rm -f "$cfg_err"
  log "OK — web-a/web-b 호스트포트 없음, 두 replica 정의 확인."
}

# ── preflight: TLS (공유 cert correlated 실패 사전 차단) ────────────────────────
preflight_tls() {
  step "preflight: TLS (leaf SAN / CA / expiry)"
  [ -f "$LEAF_CERT" ] || die "leaf cert 없음: $LEAF_CERT"
  [ -f "$ROOT_CA" ]   || die "rootCA 없음: $ROOT_CA"
  # (1) SAN 에 WEB_PUBLIC_HOST 포함 (Caddy 가 SNI/검증명으로 사용)
  if ! openssl x509 -in "$LEAF_CERT" -noout -ext subjectAltName 2>/dev/null | grep -q "DNS:$WEB_PUBLIC_HOST"; then
    die "leaf SAN 에 DNS:$WEB_PUBLIC_HOST 없음 → Caddy→web TLS 검증이 두 replica 모두에서 실패(502). cert 재생성 필요. (이미지 롤백으로 해결 안 됨 — ABORT, OLD 유지)"
  fi
  # (2) leaf 가 마운트된 rootCA 로 검증되는가
  if ! openssl verify -CAfile "$ROOT_CA" "$LEAF_CERT" >/dev/null 2>&1; then
    die "leaf 가 rootCA($ROOT_CA)로 검증되지 않음 → CA 회전 불일치 가능. ABORT (OLD 유지)."
  fi
  # (3) 만료 여유 (>14d) — 두 replica 동시 만료 time-bomb 방지
  if ! openssl x509 -in "$LEAF_CERT" -checkend 1209600 >/dev/null 2>&1; then
    warn "leaf cert 가 14일 내 만료. 곧 두 replica 동시 만료 위험 — 갱신 권장. (배포는 계속)"
  fi
  # (4) Caddy 컨테이너가 보는 rootCA 가 호스트와 동일한가 (회전 후 reload 누락 감지) — best-effort
  # feature-0020 수정: 구 가드 `ps caddy`(컨테이너 0개여도 exit 0)는 caddy 미기동 호스트에서
  # 블록에 진입시키고, 부재 컨테이너 exec 파이프라인이 pipefail+set-e 로 **무메시지 exit 1**
  # 을 냈다(잠복 — cold host/worktree dry-run 실측). ps -q 비어있음으로 실존 확인.
  if [ -n "$("${DC[@]}" ps -q caddy 2>/dev/null)" ]; then
    local host_ca caddy_ca caddy_pem
    # ⚠ 양쪽을 **같은 방식으로** 해시한다. `$( )` 는 후행 개행을 지우므로, 한쪽만 파일에서
    #   직접 해시하면 내용이 같아도 값이 갈린다(그 자체가 또 다른 오진단이 된다).
    host_ca="$(printf '%s' "$(cat "$ROOT_CA" 2>/dev/null)" | sha256sum 2>/dev/null | awk '{print $1}')"
    # ⚠ **exec 이 실패하면 판정하지 않는다** (라이브 실측 2026-09-02).
    #
    # `docker compose exec` 는 실패 메시지를 **stdout 으로** 뱉는다. 종전 코드는 `2>/dev/null`
    # 로 stderr 만 막고 그 stdout 을 그대로 해시했다 — 그래서 컨테이너가 exec 을 못 여는 상태
    # (`procReady not received`, 장기 기동 컨테이너에서 실재)에서 **"OCI runtime exec failed…"
    # 라는 97바이트 텍스트가 CA 인증서로 취급되어** 호스트 해시와 달랐고, 배포가
    # 「CA 회전 불일치」라는 **사실이 아닌 사유**로 중단됐다. 실제로 CA 는 동일했고 서비스도
    # 정상(HTTPS 200)이었다 — 운영자를 멀쩡한 것을 고치러 보내는 오진단이다.
    #
    # 이 검사는 스스로 best-effort 라고 적어 두었으므로 **판정 불가는 skip 이 옳다.**
    # 내용이 PEM 인지 먼저 확인해, 「읽지 못했다」와 「달랐다」를 가른다.
    caddy_pem="$("${DC[@]}" exec -T caddy cat /certs/rootCA.pem 2>/dev/null || true)"
    if ! printf '%s' "$caddy_pem" | head -1 | grep -q -- "-----BEGIN CERTIFICATE-----"; then
      warn "Caddy 컨테이너의 rootCA 를 읽지 못했다(exec 불가 등) — CA 대조 skip. 배포는 계속."
      caddy_ca=""
    else
      caddy_ca="$(printf '%s' "$caddy_pem" | sha256sum 2>/dev/null | awk '{print $1}' || true)"
    fi
    if [ -n "$caddy_ca" ] && [ "$host_ca" != "$caddy_ca" ]; then
      die "Caddy 컨테이너의 rootCA 가 호스트와 불일치(회전 후 reload 누락). 'docker compose exec caddy ... reload' 또는 caddy 재시작 필요. ABORT."
    fi
  fi
  log "OK — leaf SAN/CA/expiry 정상 (두 replica 공유 cert)."
}

# ── 배포 대상 SHA 결정 (origin/main 으로 coalesce) ─────────────────────────────
resolve_target_sha() {
  step "배포 대상 SHA 결정 (origin/main coalesce)"
  if [ "$DRY_RUN" -ne 1 ]; then
    git fetch origin --quiet 2>/dev/null || warn "git fetch 실패 — 로컬 origin/main 기준으로 진행."
  fi
  TARGET_SHA="$(git rev-parse --short "$BASE_BRANCH" 2>/dev/null || git rev-parse --short HEAD)"
  [ -n "$TARGET_SHA" ] || die "배포 대상 SHA 를 결정할 수 없습니다."
  log "배포 대상 = $BASE_BRANCH HEAD = $TARGET_SHA (caller worktree commit 아님 — 최신 커밋 누락 방지)"
  # build_image 는 working tree 를 빌드하므로 배포 호스트가 origin/main HEAD 에 있어야 SHA 라벨이
  # 정직하다(아니면 stale/uncommitted 코드를 $TARGET_SHA 로 mislabel — /readyz git_commit 게이트
  # 가 거짓 통과). 보안 리뷰 should-fix.
  local head_sha; head_sha="$(git rev-parse --short HEAD)"
  if [ "$head_sha" != "$TARGET_SHA" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      warn "HEAD($head_sha) != $BASE_BRANCH($TARGET_SHA). 실배포면 ABORT (dry-run 이라 계속). 배포 호스트에서 'git pull --ff-only origin main' 선행 필요."
    else
      die "배포 호스트 HEAD($head_sha) != $BASE_BRANCH($TARGET_SHA). 'git pull --ff-only origin main' 후 재실행 (build 가 working tree 를 쓰므로 stale 코드 mislabel 방지)."
    fi
  fi
}

current_deployed_sha() { [ -f "$STATE_FILE" ] && sed -n 's/^current=//p' "$STATE_FILE" | tail -1 || true; }
lastgood_sha()         { [ -f "$LASTGOOD_FILE" ] && cat "$LASTGOOD_FILE" 2>/dev/null | tr -d '[:space:]' || true; }
agent_lastgood_sha()   { [ -f "$AGENT_LASTGOOD_FILE" ] && cat "$AGENT_LASTGOOD_FILE" 2>/dev/null | tr -d '[:space:]' || true; }

# feature-0020: STATE_FILE 을 key=value 다중 라인으로 확장(current= / agent_current= /
# gateway_config_sha=). 기존 단일-라인 overwrite(echo > file)는 다른 키를 파괴하고,
# dry-run 에서도 실기록되는 결함이 있어 state_set 으로 일원화(dry-run 무기록).
state_get() { [ -f "$STATE_FILE" ] && sed -n "s/^$1=//p" "$STATE_FILE" | tail -1 || true; }
state_set() {  # $1=key $2=value — 다른 키 보존 rewrite
  if [ "$DRY_RUN" -eq 1 ]; then log "[dry-run] state $1=$2"; return 0; fi
  local tmp; tmp="$(mktemp)"
  { [ -f "$STATE_FILE" ] && grep -v "^$1=" "$STATE_FILE" 2>/dev/null || true; printf '%s=%s\n' "$1" "$2"; } > "$tmp"
  mv "$tmp" "$STATE_FILE"
}

# ── migrate 게이트 + 적용 (expand 먼저, swap 전) ───────────────────────────────
migrate_phase() {  # $1 = alembic 실행 이미지 (기본 web 이미지; workers-only 는 agent 이미지 — 리뷰 M-5)
  local mig_img="${1:-$IMAGE_REPO:$TARGET_SHA}"
  step "마이그레이션: expand/contract 게이트 + 적용 (swap 전, image=$mig_img)"
  if [ -x bin/migrate-lint.sh ]; then
    if ! run bash bin/migrate-lint.sh --base "$BASE_BRANCH"; then
      die "migrate-lint 차단: 비가산(contract) 마이그레이션. expand/contract 2-phase 또는 서명 annotation 필요 (CONVENTIONS §12). ABORT (스키마/컨테이너 무변경)."
    fi
  else
    warn "bin/migrate-lint.sh 없음 — 마이그레이션 안전 게이트 skip(권장 안 함)."
  fi
  # expand 마이그레이션 적용. contract 는 게이트가 이미 차단했으므로 여기 적용분은 backward-compatible.
  if [ -x bin/alembic-migrate.sh ]; then
    # [feature-0014-migrate-fresh-image + feature-0017-deploy-migrate-gate 결합]
    # (1) fresh 이미지: main 이 build_image 를 migrate_phase 앞으로 부르므로 $IMAGE_REPO:$TARGET_SHA
    #     (신규 alembic 마이그 파일 포함)가 이미 존재한다. MIGRATE_ALEMBIC_IMAGE 로 그 이미지를 넘겨
    #     `docker compose run agent`(stale 기본 이미지 → head 오판 → 신규 마이그 no-pending silent-skip,
    #     2026-07-02 마이그 0030 실측 회귀)를 우회한다. run 래퍼는 "$@" 를 그대로 실행하므로 env 로
    #     자식 bash 에 확실히 주입(_mig_env 배열).
    # (2) race 관용: snap-docker `docker run`/`compose run` 은 build 와 동일한 metadata-file race 로
    #     작업 성공에도 exit≠0 를 낼 수 있다. **정합 근거 = head 도달**: alembic-migrate.sh 는 멱등이고
    #     그 upgrade 는 라이브 alembic_version 이 실제 head 일 때만 exit 0(no-pending 은 live_current head
    #     확인, apply 는 ON_ERROR_STOP=1 psql 성공 후 fall-through). fresh 이미지(1)로 head 감지가 정확해져
    #     이 head-anchored 안전 논리가 성립한다. 1차 exit≠0 이면 backoff 후 1회 멱등 재시도 — 재시도 exit 0
    #     = head 도달로 판정(race/transient 무관 swap 안전). 재시도도 실패 = 진짜 실패 → ABORT(미적용 미배포).
    _mig_env=(env "MIGRATE_ALEMBIC_IMAGE=$mig_img")
    if ! run "${_mig_env[@]}" bash bin/alembic-migrate.sh upgrade; then
      warn "alembic-migrate 1차 exit≠0 — snap-docker docker-run race/일시 blip 가능성. ${MIGRATE_RETRY_BACKOFF:-5}s backoff 후 멱등 재시도로 head 도달 판정."
      [ "$DRY_RUN" -eq 1 ] || sleep "${MIGRATE_RETRY_BACKOFF:-5}"   # 같은 race window 재적중 완화(dry-run 은 skip)
      run "${_mig_env[@]}" bash bin/alembic-migrate.sh upgrade \
        || die "마이그레이션 적용 실패(재시도도 실패 — 진짜 실패). ABORT (swap 안 함, 마이그레이션 미적용 상태 미배포)."
      log "재시도 exit 0 = 라이브 alembic_version head 도달 확인 — 1차 exit≠0 은 docker-run race/transient 양성으로 무시(swap 안전)."
    fi
  else
    warn "bin/alembic-migrate.sh 없음 — 마이그레이션 적용 skip."
  fi
}

# ── 이미지 빌드 (build-once, SHA 핀, last-good 회전) ────────────────────────────
write_pin_overlay() {  # $1 = web image ref, $2 = agent image ref ("" 또는 생략 → 워커 핀 생략)
  local web_img="$1" agent_img="${2:-}"
  if [ "$DRY_RUN" -eq 1 ]; then log "[dry-run] write pin overlay → web=$web_img agent=${agent_img:-<none>}"; return 0; fi
  {
    echo "# feature-0014/0020 deploy-web.sh 자동 생성 — 빌드 결과 이미지 핀(롤백 즉시성)."
    echo "services:"
    printf '  web-a:\n    image: %s\n  web-b:\n    image: %s\n' "$web_img" "$web_img"
    if [ -n "$agent_img" ]; then
      # feature-0045: `MCP_REPLICAS` 도 같은 agent 이미지를 쓴다. 여기서 빠지면 그 서비스는
      # compose 정의에 `image:` 가 없어(anchor 는 `build:` 만 갖는다) **참조할 이미지 자체가
      # 없다** — `--no-build` 기동이 pull 을 시도해 실패하거나 stale 로컬 이미지로 떠서
      # GIT_COMMIT 불일치로 완결 판정에 걸린다. 그 결과 모든 배포가 워커 단계에서 실패한다.
      local w; for w in "${WORKERS[@]}" "${MCP_REPLICAS[@]}"; do printf '  %s:\n    image: %s\n' "$w" "$agent_img"; done
      # surge 도 **같은 핀**을 받아야 한다 — 안 그러면 compose 가 build 정의로 되돌아가
      # surge 만 다른(대개 stale) 이미지로 떠서, 교체 창 동안 신규 job 이 구 코드로 처리된다.
      printf '  %s:\n    image: %s\n' "$ASK_WORKER_SURGE" "$agent_img"
    fi
  } > "$PIN_FILE"
}

DC_PROD=()        # base + pin overlay
DC_SURGE_PROD=()  # base + pin overlay + surge profile (ask-worker surge 조작 전용)
set_dc_prod() {
  DC_PROD=(docker compose -f docker-compose.yml -f "$PIN_FILE")
  DC_SURGE_PROD=(docker compose -f docker-compose.yml -f "$PIN_FILE" --profile deploy-surge)
}

rotate_lastgood() {  # $1=image repo, $2=직전 배포 sha(빈 값 허용 — 첫 배포), $3=last-good 기록 파일
  local repo="$1" prev="$2" f="$3"
  [ -n "$prev" ] || return 0
  run bash -c "echo '$prev' > '$f'"; log "last-good($repo) = $prev"
  # :current → :last-good 태그 회전. sha 태그가 keep-N prune 으로 지워져도 last-good 이미지는
  # 이 안정 태그로 보존되어 롤백이 항상 가능(백엔드 리뷰 note).
  if [ "$DRY_RUN" -ne 1 ] && docker image inspect "$repo:current" >/dev/null 2>&1; then
    docker tag "$repo:current" "$repo:last-good" || true
  fi
}

build_service_image() {  # $1 = sha, $2 = image repo, $3 = compose build 서비스 (build-once 대표)
  local sha="$1" repo="$2" bsvc="$3"
  # $bsvc 하나만 빌드하면 pin overlay 의 image:$repo:$sha 로 태깅됨 → 동일 이미지 서비스가 재사용(build-once).
  # feature-0017: build 게이트는 exit code 만 신뢰하지 않는다(snap-docker 의 metadata-file race —
  # docker 29.3.1/compose v5.1.1/buildx v0.31.1 가 `naming...done` 후 /tmp metadata 파일을 confinement
  # 다른 mount ns 에서 못 찾아 EXIT 1 을 반환하나 이미지는 정상 산출·태깅됨, dc-build 동일 우회).
  # 판정: 이미지 존재 + GIT_COMMIT 라벨==sha 로 정합 확인. EXIT≠0 은 **로그에 metadata-file race 마커가
  # 있을 때만** 양성 무시 — 진짜 빌드 실패(컴파일 에러 등, 마커 없음/이미지 부재)는 여전히 ABORT.
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] build $bsvc (GIT_COMMIT=$sha → $repo:$sha)"
  else
    local _blog _brc
    _blog="$(mktemp)"
    set +e +o pipefail
    GIT_COMMIT="$sha" "${DC_PROD[@]}" build "$bsvc" 2>&1 | tee "$_blog"
    _brc=${PIPESTATUS[0]}
    set -e -o pipefail
    local _img_commit
    _img_commit="$(docker image inspect "$repo:$sha" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | sed -n 's/^GIT_COMMIT=//p' | head -1)"
    if [ "$_brc" -eq 0 ] && [ "$_img_commit" = "$sha" ]; then
      :  # 정상 빌드
    elif [ "$_brc" -ne 0 ] && [ "$_img_commit" = "$sha" ] && \
         grep -qiE 'compose-build-metadataFile|metadataFile.*no such file|metadata file.*no such file' "$_blog"; then
      warn "compose build EXIT=$_brc 이나 이미지($repo:$sha, GIT_COMMIT 일치) 정상 산출 — snap-docker metadata-file race 양성 무시(dc-build 동일 우회)."
    else
      log "--- build log tail ---"; tail -15 "$_blog" >&2; rm -f "$_blog"
      die "이미지 빌드 실패 — $repo:$sha 부재 또는 GIT_COMMIT('$_img_commit')≠$sha (EXIT=$_brc, metadata-race 마커 없음). 진짜 빌드 실패 — ABORT."
    fi
    rm -f "$_blog"
  fi
  # 새 이미지를 안정 태그 :current 로 (다음 배포가 :last-good 로 회전).
  if [ "$DRY_RUN" -ne 1 ]; then docker tag "$repo:$sha" "$repo:current" || true; fi
  # keep-N prune (오래된 SHA 태그 정리)
  if [ "$DRY_RUN" -ne 1 ]; then
    docker images "$repo" --format '{{.Tag}} {{.ID}}' 2>/dev/null \
      | grep -vE '^(current|last-good) ' | awk '{print $1}' | tail -n +"$((IMAGE_KEEP+1))" \
      | while read -r t; do [ -n "$t" ] && docker rmi "$repo:$t" 2>/dev/null || true; done
  fi
}

build_image() {  # $1 = sha — web 이미지 build-once (pin overlay 는 main 이 선기록)
  local sha="$1"
  step "web 이미지 빌드 (build-once, GIT_COMMIT=$sha → $IMAGE_REPO:$sha)"
  rotate_lastgood "$IMAGE_REPO" "$(current_deployed_sha)" "$LASTGOOD_FILE"
  build_service_image "$sha" "$IMAGE_REPO" web-a
}

build_agent_image() {  # $1 = sha — 워커 공용 agent 이미지 build-once (feature-0020)
  local sha="$1"
  step "agent(워커) 이미지 빌드 (build-once, GIT_COMMIT=$sha → $AGENT_IMAGE_REPO:$sha)"
  if [ "$(state_get agent_current)" = "$sha" ] && [ "$DRY_RUN" -ne 1 ] \
     && docker image inspect "$AGENT_IMAGE_REPO:$sha" >/dev/null 2>&1; then
    log "agent 이미지 이미 $sha — 빌드/last-good 회전 skip(멱등)."
    return 0
  fi
  rotate_lastgood "$AGENT_IMAGE_REPO" "$(state_get agent_current)" "$AGENT_LASTGOOD_FILE"
  build_service_image "$sha" "$AGENT_IMAGE_REPO" insight-worker
}

# ── replica 헬퍼 ──────────────────────────────────────────────────────────────
# CHG-20260812T200000: 인가된 재생성 스탬프 — `bin/recreate-audit.sh` 가 컨테이너 StartedAt 과
# 대조해 **스탬프 없는(우회) 재생성**을 사후 적발한다. raw `docker compose` 는 막을 수 없으니
# 막을 수 없는 것을 보이게 만든다. safe-recreate.sh 와 **같은 파일**에 남겨 기준을 하나로 둔다.
RECREATE_STAMP_FILE="${SAFE_RECREATE_STAMP_FILE:-$STATE_DIR/recreate-sanctioned.log}"
stamp_sanctioned_recreate() {  # $1 = svc
  [ "$DRY_RUN" -eq 1 ] && return 0
  mkdir -p "$(dirname "$RECREATE_STAMP_FILE")" 2>/dev/null || return 0
  printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "deploy-web" >> "$RECREATE_STAMP_FILE" || true
}

replica_cid() { "${DC_PROD[@]}" ps -q "$1" 2>/dev/null | head -1; }

# 컨테이너 내부에서 /readyz 를 조회해 "READY <git_commit>" 출력(200) 또는 비-0.
replica_readyz() {  # $1 = svc
  "${DC_PROD[@]}" exec -T "$1" python -c '
import json,ssl,sys,urllib.request
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
for url in ("https://localhost:8000/readyz","http://localhost:8000/readyz"):
    try:
        r=urllib.request.urlopen(url,timeout=5,context=ctx if url.startswith("https") else None)
        d=json.loads(r.read().decode());
        print("READY", d.get("git_commit","?"), d.get("active_streams",0))
        sys.exit(0 if getattr(r,"status",0)==200 else 1)
    except Exception:
        continue
sys.exit(1)
' 2>/dev/null
}

replica_active_streams() {  # $1 = svc → 정수(실패 시 큰 수로 보수적 처리)
  "${DC_PROD[@]}" exec -T "$1" python -c '
import json,ssl,sys,urllib.request
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
for url in ("https://localhost:8000/livez","http://localhost:8000/livez"):
    try:
        r=urllib.request.urlopen(url,timeout=5,context=ctx if url.startswith("https") else None)
        print(json.loads(r.read().decode()).get("active_streams",0)); sys.exit(0)
    except Exception:
        continue
print(0); sys.exit(0)
' 2>/dev/null || echo 0
}

# ── 브리지 축 드레인 probe (feature-0045) ─────────────────────────────────────
# 대상 replica 를 **lame-duck** 으로 만들고 현재 in-flight 를 돌려준다. 멱등이므로 폴링하며
# 반복 호출한다. 출력: "<active_streams> <bridge_inflight> <bridge_waiters>" (성공) | 비-0 종료.
#
# ⚠ `/livez` 를 쓰지 않는다 — 드레인 중 `/livez` 는 **503** 이다(그게 Caddy 를 후보에서
#   빼는 수단이다). 같은 창구로 카운터를 읽으면 게이트가 자기가 만든 503 에 걸려 조회 실패로
#   읽는다. 그래서 드레인 제어·관측은 전용 창구(`/internal/bridge-drain`, loopback 전용)로 분리했다.
replica_drain_probe() {  # $1 = svc, $2 = "release"(선택) → 위 3-정수 | 비-0
  local q=""; [ "${2:-}" = "release" ] && q="?release=1"
  "${DC_PROD[@]}" exec -T "$1" python -c '
import json,ssl,sys,urllib.request
q=sys.argv[1] if len(sys.argv)>1 else ""
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
for base in ("https://localhost:8000","http://localhost:8000"):
    try:
        req=urllib.request.Request(base+"/internal/bridge-drain"+q, data=b"", method="POST")
        r=urllib.request.urlopen(req,timeout=5,context=ctx if base.startswith("https") else None)
        d=json.loads(r.read().decode())
        print(int(d.get("active_streams",0)), int(d.get("bridge_inflight",0)),
              int(d.get("bridge_waiters",0)))
        sys.exit(0)
    except Exception:
        continue
sys.exit(1)
' "$q" 2>/dev/null
}

# 현재 드레인을 건 replica(있으면). 비정상 종료(INT/TERM/크래시) 시 EXIT trap 이 이것을 보고
# 되돌린다 — 드레인된 replica 가 문이 닫힌 채 남으면 실질 용량이 절반이 되는데, `/readyz` ·
# `/healthz` · `container_health` 어느 신호도 그것을 말하지 않아 **무증상으로 오래 간다**.
DRAINED_SVC=""

# 드레인을 되돌린다. **배포가 replica 를 못 내리고 중단하는 모든 경로**에서 불러야 한다 —
# 안 그러면 그 replica 는 문이 닫힌 채(LB 후보 밖) 계속 살아 있고, 다음 배포가 상대를
# 내리는 순간 available upstream 이 0 이 된다. 실패해도 배포 판단을 바꾸지 않는다(경고만).
replica_release_drain() {  # $1 = svc
  [ "$DRY_RUN" -eq 1 ] && return 0
  replica_drain_probe "$1" release >/dev/null 2>&1 \
    || warn "$1 드레인 해제 실패 — 이 replica 는 LB 후보 밖일 수 있다. 확인: docker compose -f docker-compose.yml exec -T $1 python -c \"import urllib.request;print(urllib.request.urlopen('http://localhost:8000/livez').status)\""
}

# quiesce 게이트 적재 — 위 log/warn/err/step · DC/DC_PROD/REPLICAS · replica_cid 정의 **뒤**에서
# source 해야 라이브러리가 그것들을 그대로 쓴다(라이브러리는 미정의분만 기본값으로 채운다).
# shellcheck source=lib/quiesce.sh
. "$_QUIESCE_LIB"

wait_ready() {  # $1 = svc, $2 = expected sha → 0 성공
  [ "$DRY_RUN" -eq 1 ] && { log "[dry-run] wait_ready $1 (기대 $2) skip"; return 0; }
  local svc="$1" want="$2" deadline=$(( SECONDS + READY_TIMEOUT )) out got
  while [ "$SECONDS" -lt "$deadline" ]; do
    out="$(replica_readyz "$svc" || true)"
    if printf '%s' "$out" | grep -q '^READY '; then
      got="$(printf '%s' "$out" | awk '{print $2}')"
      if [ "$got" = "$want" ]; then log "  $svc ready (git_commit=$got)"; return 0; fi
      log "  $svc ready 이지만 git_commit=$got (기대=$want) — 대기"
    fi
    sleep 2
  done
  return 1
}

predrain() {  # $1 = recreate 대상 svc, $2 = 상대(살아있어야 함) svc → 1 = 내리면 안 됨(중단)
  local target="$1" other="$2" deadline=$(( SECONDS + PREDRAIN_TIMEOUT )) n
  step "pre-drain: $other 건강 확인 + $target 진행 스트림 종료 대기"
  [ "$DRY_RUN" -eq 1 ] && { log "[dry-run] pre-drain skip"; return 0; }
  # ⚠ **fail-closed 결정 지점 3단** — "지금 $target 을 내려도 되는가" 에 답하는 자리.
  # 세 조건이 모두 성립해야 내린다. 어느 하나라도 아니면 **내리지 않고 중단**한다 —
  # 중단하면 $target(구버전)이 계속 서빙하므로 무중단이 유지되지만, 강행하면 upstream 이 0 이 된다.
  # (초기 배포 = 양 replica 부재는 main 이 별도 분기로 처리하므로 여기 오지 않는다.
  #  여기서 상대가 없다는 것은 "한쪽만 살아 있는 비정상 상태" 이고, 그 유일한 replica 를
  #  내리는 것이 정확히 전면 다운이다.)
  local other_cid
  other_cid="$(replica_cid "$other" 2>/dev/null || true)"
  if [ -z "$other_cid" ]; then
    err "$other 컨테이너가 없다 — $target 이 유일 replica 다. 지금 내리면 upstream 0(전면 다운)."
    err "  복구: docker compose -f docker-compose.yml up -d --no-deps $other  → 양 replica 확보 후 재실행(멱등)."
    return 1
  fi
  if ! replica_readyz "$other" >/dev/null 2>&1; then
    err "$other 가 ready 아님 — 지금 $target 을 내리면 healthy upstream 이 0 이 된다. 중단."
    err "  진단: docker compose -f docker-compose.yml logs --tail 50 $other"
    return 1
  fi
  # 앱은 살아 있어도 엣지 passive 격리 중이면 LB 후보가 아니다(= 2026-08-11 사고 기전).
  if ! wait_edge_available "$other"; then
    err "$other 가 엣지 후보로 복귀하지 않았다 — 지금 $target 을 내리면 available upstream 0(전면 503)."
    err "  진단: docker compose -f docker-compose.yml exec -T caddy wget -qO- $CADDY_ADMIN_URL/reverse_proxy/upstreams"
    err "  현재 상태 유지(=$target 이 계속 서빙) 후 원인 해결하고 재실행(멱등)."
    return 1
  fi
  # ── 드레인 + 진행 중 작업 대기 (feature-0045 로 브리지 축까지 확장) ────────────
  # 종전에는 `active_streams`(SSE 프롬프트 자동작성 + CSV export)만 봤다. 그 카운터는
  # **브리지 축을 세지 않는다** — 개인 AI 가 붙들고 있는 55초 블로킹 대기도, 그 AI 가
  # 조사 중인 도구 호출도. 그래서 브리지로 요청을 주고받는 바로 그 중에도 이 게이트는
  # "조용함(0)" 으로 읽고 replica 를 내렸다.
  #
  # 이제 두 가지를 순서대로 한다:
  #   1) **문을 닫는다**(드레인). `/livez` 가 503 → Caddy active health(2s)가 이 replica 를
  #      후보에서 뺀다 → 신규 유입 정지. 대기 중이던 롱폴은 즉시 정상 반환하고 남은
  #      replica 로 다시 붙는다(오류가 아니므로 러너의 백오프 경로를 타지 않는다).
  #   2) **진행 중인 것만 기다린다**. `active_streams`(SSE/CSV) + `bridge_inflight`
  #      (개인 AI 의 도구 호출 왕복). 대기(`bridge_waiters`)는 1) 로 즉시 비므로 기다리지 않는다.
  local probe as bi bw
  while [ "$SECONDS" -lt "$deadline" ]; do
    if ! probe="$(replica_drain_probe "$target")"; then
      # 조회 실패를 "조용함" 으로 읽지 않는다(vacuous pass 방지).
      # ⚠ 대체 게이트로 `replica_active_streams` 를 쓰면 안 된다 — 그 헬퍼는 **조회 실패도 0**
      #   으로 돌려주고(`|| echo 0` + 내부 fallback), 드레인 중 `/livez` 는 우리가 만든 503 이라
      #   항상 실패한다. 즉 "드레인을 걸고 나면 대체 게이트가 항상 통과" 라는 최악의 조합이다.
      #   strict probe(실패를 비-0 종료로 구분)를 쓰고, 못 읽으면 **기다린다**.
      if n="$(replica_active_streams_strict "$target")" && [ "${n:-1}" -eq 0 ] 2>/dev/null; then
        warn "  $target 드레인 probe 실패 — 기존 게이트로 대체(active_streams=0). 브리지 축은 미확인."
        PREDRAIN_UNVERIFIED=$(( PREDRAIN_UNVERIFIED + 1 ))
        return 0
      fi
      warn "  $target 드레인 probe 실패 + active_streams 미확인/비-0 — 대기(조용한지 알 수 없다)."
      sleep 3; continue
    fi
    read -r as bi bw <<<"$probe"
    DRAINED_SVC="$target"   # 이 시점부터 EXIT trap 의 회수 대상이다
    if [ "${as:-0}" -eq 0 ] 2>/dev/null && [ "${bi:-0}" -eq 0 ] 2>/dev/null; then
      log "  $target 조용함(active_streams=0 bridge_inflight=0, 드레인된 대기=$bw) — recreate 진행"
      return 0
    fi
    log "  $target active_streams=${as:-?} bridge_inflight=${bi:-?} (대기 $bw 는 드레인됨) — 종료 대기"
    sleep 3
  done
  warn "$target pre-drain timeout(${PREDRAIN_TIMEOUT}s) — 진행 중인 작업이 남았지만 계속 진행."
  warn "  끊긴 브리지 작업은 점유 lease 가 만료되어 대기열로 돌아간다(배포 말미 reclaim_bridge_claims)."
  PREDRAIN_FORCED=$(( PREDRAIN_FORCED + 1 ))
}

# ── 끊긴 브리지 점유 회수 (feature-0045) ──────────────────────────────────────
# **pre-drain 이 강행했을 때만** 돈다. 진행 중이던 왕복이 끊겼다면 그 질문은 "가져갔는데 답이
# 없는" 상태로 최대 30분(lease) 갇힌다 — 사용자에게는 배포가 질문을 삼킨 것으로 보인다.
# 회수는 `ClaimedBy` 를 지우지 않고 lease 만 만료시킨다(살아남은 러너의 제출은 그대로 성공).
# 상세 근거는 `/internal/bridge-reclaim` docstring.
reclaim_bridge_claims() {
  [ "$DRY_RUN" -eq 1 ] && { log "[dry-run] reclaim_bridge_claims skip"; return 0; }
  # 강행했거나(끊었다) 드레인을 확인하지 못한 채 진행했으면(끊었을 수 있다) 회수한다.
  [ "$PREDRAIN_FORCED" -gt 0 ] || [ "$PREDRAIN_UNVERIFIED" -gt 0 ] || return 0
  step "브리지 점유 회수 (강행 ${PREDRAIN_FORCED}회 · 미확인 ${PREDRAIN_UNVERIFIED}회 — 끊겼을 수 있는 작업을 대기열로)"
  local svc out
  for svc in "${REPLICAS[@]}"; do
    [ -n "$(replica_cid "$svc" 2>/dev/null)" ] || continue
    out="$("${DC_PROD[@]}" exec -T "$svc" python -c '
import json,ssl,sys,urllib.request
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
for base in ("https://localhost:8000","http://localhost:8000"):
    try:
        req=urllib.request.Request(base+"/internal/bridge-reclaim?grace_sec=60&since_epoch="+sys.argv[1],
                                   data=b"", method="POST")
        r=urllib.request.urlopen(req,timeout=10,context=ctx if base.startswith("https") else None)
        print(json.loads(r.read().decode()).get("released",0)); sys.exit(0)
    except Exception:
        continue
sys.exit(1)
' "$DEPLOY_WINDOW_START" 2>/dev/null)" && { log "  점유 회수 ${out}건 — 대기열로 되돌렸다(원 소유자가 살아 있으면 그대로 제출된다)."; return 0; }
  done
  warn "  점유 회수 호출 실패 — 끊긴 작업은 lease(30분) 만료로 자연 회수된다."
}

# 종료 시 정리 — 소유권 정규화 + **드레인 회수**. 어느 경로로 끝나든(성공·die·INT/TERM) 실행된다.
on_exit_cleanup() {
  local rc=$?
  normalize_ownership
  if [ -n "$DRAINED_SVC" ]; then
    warn "드레인된 replica 가 남아 있다($DRAINED_SVC) — 회수한다. 그대로 두면 LB 후보가 절반이 된다."
    replica_release_drain "$DRAINED_SVC"
    DRAINED_SVC=""
  fi
  return "$rc"
}

# 배포가 브리지 축에 무엇을 했는지 **정직하게** 보고한다(quiesce_summary 와 같은 자세).
# "무중단이었다" 를 기본값으로 두지 않는다 — 강행이 있었으면 그 사실이 로그에 남아야 한다.
bridge_continuity_summary() {
  if [ "$PREDRAIN_UNVERIFIED" -gt 0 ]; then
    warn "브리지 연속성: 드레인을 걸지 못한 채 진행 ${PREDRAIN_UNVERIFIED}회 — 그 replica 의 브리지"
    warn "  in-flight 를 **확인하지 못했다**. 끊김이 없었다고 단정할 수 없다(구 이미지 replica 이거나"
    warn "  /internal/bridge-drain 이 응답하지 않았다). 배포 후 대기 말풍선이 남아 있는지 확인한다."
  fi
  if [ "$PREDRAIN_FORCED" -gt 0 ]; then
    warn "브리지 연속성: pre-drain 강행 ${PREDRAIN_FORCED}회 — 진행 중이던 개인 AI 왕복이 끊겼을 수 있다."
    warn "  끊긴 작업의 점유는 회수되어 대기열로 돌아갔다(중복 처리는 '먼저 끝내는 쪽이 이긴다')."
    warn "  반복되면 DEPLOY_WEB_PREDRAIN_TIMEOUT(현재 ${PREDRAIN_TIMEOUT}s)을 늘리거나 유입이 적은 시각으로 옮긴다."
  else
    log "브리지 연속성: 대기는 드레인으로 교대했고 진행 중 왕복은 완주했다(끊김 0)."
  fi
}

# 이전 배포가 중단되며 남긴 드레인을 청소한다(feature-0045). 드레인은 프로세스 로컬이라
# recreate 되면 사라지지만, **내려가지 못한 replica** 는 문이 닫힌 채로 계속 살아 있다.
# 그 상태에서 상대를 내리면 available upstream 이 0 이다 — 롤링 시작 전에 반드시 확인한다.
clear_stale_drain() {
  [ "$DRY_RUN" -eq 1 ] && return 0
  local svc
  for svc in "${REPLICAS[@]}"; do
    [ -n "$(replica_cid "$svc" 2>/dev/null)" ] || continue
    replica_drain_probe "$svc" release >/dev/null 2>&1 \
      || warn "$svc 드레인 상태 확인 실패(구버전 이미지면 정상 — 이 엔드포인트가 없다)."
  done
}

# ── 엣지(Caddy) 후보 복귀 게이트 (2026-08-11 — `no upstreams available` 503 근본수정) ──
# `wait_ready` 는 **컨테이너 내부** /readyz 만 본다. 그것은 "앱이 떴다" 이지 "엣지가 이 replica 를
# 다시 LB 후보로 쓴다" 가 아니다. Caddy 는 passive health(max_fails/fail_duration)로 방금 실패한
# upstream 을 일정 시간 후보에서 제외하는데, 그 격리가 풀리기 전에 상대 replica 를 내리면
# **available upstream 0** 이 되어 전 요청이 lb_try_duration 소진 후 503 을 받는다.
#
# 라이브 실측(2026-08-11): 롤링 간격 ≈10s < 당시 fail_duration 30s → 배포 1회당 12~17초 전면 503,
# 6시간 창에 엣지 에러 `no upstreams available` 71건. 그 창에서 active health 는 양 replica 모두
# `host is up` 이었다(= passive 격리가 유일 원인). 503 종료 시각이 매번 "먼저 내린 replica 의 첫
# 실패 + fail_duration" 과 일치.
#
# **게이트 배치 — 두 층 (적대 검증 P1 반영)**:
#   (a) `recreate_replica` 말미 — 방금 올린 replica 의 복귀를 **선제 대기**(비차단). 롤백 경로도
#       이 층을 타므로 롤백이 게이트 때문에 멈추지 않는다(롤백은 완주가 우선).
#   (b) `predrain <target> <other>` — **다음 replica 를 내리기 직전**, 상대(`other`)가 엣지 후보로
#       복귀했는지 확인하고 아니면 **배포를 중단**한다(fail-closed). 여기가 결정 지점인 이유:
#       "내려도 되는가" 라는 질문에 답하는 자리이고, 중단하면 기존 replica 가 계속 서빙해
#       **무중단이 유지**되지만 강행하면 정확히 우리가 고치려는 전면 503 이 재현되기 때문이다.
#       초판은 (a) 만 두고 비차단이었는데, 그러면 timeout 후 그대로 다음 replica 를 내려
#       게이트가 무의미해진다(적대 검증 P1 지적 — 정확).
# 판정 순서:
#   1순위 Caddy admin API 의 upstream 별 `fails` 카운터(정확·즉시)
#   2순위 조회 불가 시 fail_duration 만큼 고정 대기(degrade). 이때 기준값은 **실행 중 Caddy 의
#         설정과 repo 소스 중 큰 값** — 배포로 Caddyfile 이 바뀌는 창에서는 라이브가 아직 옛 값
#         이므로 repo 값만 믿으면 덜 기다린다(적대 검증 P1 지적).
# ⚠ **주장 범위 (정직 표기)**: 게이트는 두 축을 본다 — ① passive fail 카운터 해제(`fails==0`)
#   ② **Caddy 네트워크에서의 실도달**(`edge_peer_live` — Caddy 컨테이너에서 그 replica 의
#   health_uri 를 직접 200 확인, active health probe 와 동일 조건). ①만 보면 active health 가
#   제외한 replica 를 복귀로 오판한다(적대 검증 P1). 남는 갭: Caddy 내부 healthy 플래그 자체는
#   admin API 가 노출하지 않으므로 "방금 실패를 기록해 아직 unhealthy 마킹 중이나 지금은 200"
#   인 최대 `health_interval`(2s) 창은 우리 폴링(1s)이 흡수한다.
caddy_fail_duration_s() {  # 실행 중 Caddy 설정과 repo 소스 중 **큰** fail_duration(초). 미상이면 30.
  local from_file from_live v out=0
  from_file="$(sed -n 's/^[[:space:]]*fail_duration[[:space:]]\{1,\}\([0-9]\{1,\}\)s.*/\1/p' "$CADDYFILE" 2>/dev/null | head -1 || true)"
  # 라이브 값 — 배포가 Caddyfile 을 바꾸는 창에서는 컨테이너가 아직 옛 설정으로 돌고 있다.
  from_live="$(timeout -k 5 10 "${DC[@]}" exec -T caddy cat /etc/caddy/Caddyfile 2>/dev/null \
    | sed -n 's/^[[:space:]]*fail_duration[[:space:]]\{1,\}\([0-9]\{1,\}\)s.*/\1/p' | head -1 || true)"
  for v in "$from_file" "$from_live"; do
    case "$v" in ''|*[!0-9]*) continue ;; esac
    [ "$v" -gt "$out" ] && out="$v"
  done
  [ "$out" -gt 0 ] || out=30      # 양쪽 다 미상 → 관측된 최악값(30s)을 보수적으로 가정
  printf '%s' "$out"
}

edge_peer_live() {  # $1 = svc → 0 = **Caddy 네트워크에서** 그 replica 의 health_uri 가 200
  # Caddy 의 active health probe 를 그대로 재현한다 — 같은 컨테이너·같은 경로·같은 Host·같은 TLS
  # 조건. passive `fails` 만 보면 active health 가 제외한 replica 를 "복귀" 로 오판할 수 있다
  # (적대 검증 P1): 컨테이너 내부 /readyz 는 200 이고 fails 도 0 인데 Caddy→replica 도달이
  # 끊긴 상태가 성립하며, 그 상대를 믿고 다음 replica 를 내리면 다시 upstream 0 이 된다.
  # Host 는 실 트래픽과 동일하게 공개 호스트로 — 앱 TrustedHost 가 내부 서비스명을 400 거부한다.
  # ⚠ **http fallback 을 두지 않는다** — Caddyfile 의 transport 는 `tls` 고정이라 엣지는 https 로만
  # 붙는다. web 이 TLS 없이 같은 포트에 HTTP 로 떴다면 Caddy 는 그 replica 를 제외하는데, http 로
  # 폴백하는 probe 는 200 을 받아 **false-pass** 한다(적대 검증 P1, 4R).
  # 한계와 그 전제(5R 적대 검증 — 수용된 잔여 리스크): caddy 이미지의 busybox wget 은 CA 를
  # 지정할 수 없어 `--no-check-certificate` 로 붙는다. 즉 이 probe 는 "TLS 로 도달해 200 을
  # 받는가" 까지이고 CA/SAN 검증은 하지 못한다. 그래서 "Caddy 는 CA 검증 실패로 제외했는데
  # probe 만 200" 인 false-pass 가 이론상 가능하다.
  #   그 시나리오가 성립하려면 **replica 마다 다른 leaf** 를 제시해야 하는데, 이 구성은
  #   `x-web-extra` 가 양 replica 에 **동일한 `../artifacts/certs` 마운트 + 동일 WEB_TLS_CERT_FILE**
  #   을 주므로 성립하지 않는다(둘은 항상 같은 cert 를 제시한다). cert 를 교체했는데 Caddy 가
  #   옛 CA 를 들고 있으면 **양쪽이 동시에** 제외되어 배포 이전에 이미 전면 503 이고, 그 축은
  #   `preflight_tls` 의 (2) rootCA 검증·(4) 컨테이너 CA 대조가 배포 시작 전에 ABORT 시킨다.
  #   실제로 한쪽만 TLS 도달 불가가 되는 경우(예: 그 replica 가 cert 를 못 읽어 평문 기동)는
  #   http 폴백이 없으므로 handshake 실패 → probe 실패로 이 게이트가 잡는다.
  #   ⚠ 전제(단일 cert 소스 공유)가 깨지면 위 논거가 무너진다 —
  #     `test_edge_rolling_gate.py::test_g10_replicas_share_a_single_cert_source` 가 그것을 잠근다.
  local svc="$1"
  timeout -k 5 15 "${DC[@]}" exec -T caddy wget -q -T 3 --no-check-certificate \
    --header="Host: $WEB_PUBLIC_HOST" -O /dev/null "https://$svc:8000/livez" 2>/dev/null
}

edge_upstream_fails() {  # $1 = svc → 그 upstream 의 passive fail 카운터. 조회·파싱 불가 시 빈 출력.
  local svc="$1" json rest obj v
  # `timeout` 2겹: wget 자체(-T)와 docker exec 전체. 어느 한쪽이 응답 없이 멈추면 while 루프가
  # deadline 을 재검사하지 못해 **배포가 flock 을 쥔 채 무기한 정지**한다(적대 검증 P1 지적).
  json="$(timeout -k 5 15 "${DC[@]}" exec -T caddy wget -q -T 5 -O- "$CADDY_ADMIN_URL/reverse_proxy/upstreams" 2>/dev/null || true)"
  [ -n "$json" ] || return 0
  # 순수 bash 문자열 연산으로 파싱한다 — 호스트 python3 의존을 만들지 않고, `printf | grep`
  # 파이프라인이 pipefail 하에서 SIGPIPE(141)로 오판되던 기존 함정(preflight_fileset 주석)도 피한다.
  # 응답 형식: [{"address":"web-a:8000","num_requests":N,"fails":M},...]
  rest="${json#*\"${svc}:8000\"}"
  [ "$rest" = "$json" ] && return 0            # 해당 upstream 미검출(설정 변경 등) → degrade
  obj="${rest%%\}*}"                            # 같은 객체 범위로 한정(다른 upstream 의 fails 오독 방지)
  case "$obj" in *'"fails":'*) : ;; *) return 0 ;; esac
  v="${obj#*\"fails\":}"
  v="${v#"${v%%[![:space:]]*}"}"                # 선행 공백 제거(compact JSON 이 아닌 경우 방어)
  v="${v%%[!0-9]*}"                             # 선행 숫자만
  [ -n "$v" ] && printf '%s' "$v"
  return 0
}

wait_edge_available() {  # $1 = svc → 0 = 복귀 확인(또는 게이트 무의미), 1 = **미확인**(호출자가 판단)
  local svc="$1" deadline f probed=0 w cid ps_rc=0
  [ "$DRY_RUN" -eq 1 ] && { log "[dry-run] wait_edge_available $svc skip"; return 0; }
  # caddy 실존 확인 — **조회 실패와 "정말 없음" 을 구분**한다. 둘을 빈 문자열로 합치면 일시적
  # docker stall 이 게이트 우회(즉시 성공)로 둔갑한다(적대 검증 P2 지적).
  cid="$(timeout -k 5 15 "${DC[@]}" ps -q caddy 2>/dev/null)" || ps_rc=$?
  if [ "$ps_rc" -eq 0 ] && [ -z "$cid" ]; then
    warn "caddy 미기동 — 엣지가 없으므로 '무중단' 개념 자체가 성립하지 않는다(서비스는 이미 중단 상태). 게이트 skip 후 진행하되, 롤아웃 뒤 caddy 기동을 확인할 것."
    return 0
  fi
  if [ "$ps_rc" -ne 0 ]; then
    warn "caddy 상태 조회 실패(rc=$ps_rc) — '미기동' 으로 단정하지 않고 degrade 대기로 진행한다."
  fi
  step "엣지 후보 복귀 대기: $svc (Caddy passive 격리 해제 확인)"
  deadline=$(( SECONDS + EDGE_AVAIL_TIMEOUT ))
  while [ "$SECONDS" -lt "$deadline" ]; do
    f="$(edge_upstream_fails "$svc")"
    [ -n "$f" ] || break                        # 조회 불가 → degrade 경로
    probed=1
    if [ "$f" -eq 0 ] 2>/dev/null; then
      # passive 격리 해제(fails=0) **와** active 축(Caddy→replica 실도달)을 모두 본다.
      if edge_peer_live "$svc"; then
        log "  $svc 엣지 후보 복귀 확인(fails=0 + Caddy→$svc /livez 200)"; return 0
      fi
      log "  $svc fails=0 이나 Caddy→$svc /livez 미응답 — active health 제외 상태로 보고 대기"
    else
      log "  $svc 엣지 passive fails=$f — 격리 해제 대기"
    fi
    sleep 1
  done
  if [ "$probed" -eq 0 ]; then
    # 조회 자체가 불가 — 관측이 없으니 "복귀했다"고 단정할 수 없다. 설정 파일에서 읽은 값만큼
    # 기다린 뒤 **확인됨이 아니라 degrade 성공**으로 처리한다.
    #
    # ⚠ **floor 30s** — 파일에서 읽은 값은 "Caddy 프로세스가 지금 적용 중인 값" 이 아니다.
    # bind mount 파일이 이미 새 값으로 갱신됐어도 프로세스는 reload 전까지 옛 값으로 돈다
    # (적대 검증 P1 지적). admin API 를 못 읽는 상황에서는 런타임 값을 확인할 수단 자체가 없으므로,
    # **관측된 최악값(30s) 이상**을 기다린다. 덜 기다린 대가는 전면 503 이고, 더 기다린 대가는
    # 배포 30초다 — 비대칭이 명백하다.
    w="$(caddy_fail_duration_s)"
    [ "$w" -lt "$EDGE_DEGRADE_FLOOR" ] && w="$EDGE_DEGRADE_FLOOR"
    w=$(( w + 2 ))
    warn "Caddy admin API($CADDY_ADMIN_URL) 조회 불가 — 런타임 fail_duration 확인 불가로 ${w}s 고정 대기(floor=${EDGE_DEGRADE_FLOOR}s). 정확도↓·안전성 유지."
    sleep "$w" || true
    # 대기만 하고 통과시키면 **active 축이 통째로 우회**된다(적대 검증 P1, 4R): admin 조회는
    # 실패하는데 Caddy→replica 연결도 끊긴 상태가 성립하고, 그 상대를 믿고 다음 replica 를 내리면
    # 다시 upstream 0 이다. admin 실패와 exec 실패는 서로 다른 고장이므로 probe 는 여전히 유의미하다.
    if edge_peer_live "$svc"; then
      log "  $svc degrade 대기 후 Caddy→$svc /livez 200 확인."
      return 0
    fi
    warn "$svc degrade 대기 후에도 Caddy→$svc /livez 미응답 — 복귀로 단정하지 않는다."
    return 1
  fi
  # 격리를 **실제로 관측**했는데 상한까지 안 풀렸다 — 여기서 진행하면 게이트가 방지하려던 전면
  # 503 을 그대로 재현한다. 판단은 호출자에게 넘긴다(predrain 은 중단, recreate 말미는 경고).
  warn "$svc 엣지 후보 복귀가 ${EDGE_AVAIL_TIMEOUT}s 내 확인되지 않음(마지막 fails=${f:-?})."
  return 1
}

recreate_replica() {  # $1 = svc, $2 = expected sha
  local svc="$1" want="$2"
  step "recreate $svc → $want (one-at-a-time)"
  run "${DC_PROD[@]}" up -d --no-deps --no-build --force-recreate "$svc" || return 1
  stamp_sanctioned_recreate "$svc"   # CHG-20260812T200000: 감사 대조용(우회 재생성 적발)
  wait_ready "$svc" "$want" || { err "$svc 가 ${READY_TIMEOUT}s 내 ready+correct-commit 실패."; return 1; }
  # 선제 대기(비차단). 앱 ready 와 엣지 후보 복귀는 다른 층이라 여기서 미리 기다려 두면 다음
  # predrain 이 즉시 통과한다. **여기서 실패해도 배포를 끊지 않는다** — 이 replica 는 이미 올라와
  # 있고, 위험한 것은 "다음 replica 를 내리는 것" 이라 그 판단은 predrain 이 fail-closed 로 한다
  # (롤백 경로도 이 함수를 타므로 여기서 끊으면 롤백이 중단된다).
  wait_edge_available "$svc" || warn "$svc 엣지 복귀 미확인 — 다음 replica 를 내리기 전 predrain 이 재확인한다."
  # feature-0045: 새 프로세스는 드레인이 꺼진 상태로 떴다 — 추적 대상에서 뺀다(EXIT trap 이
  # 이미 교체된 replica 에 불필요한 해제 호출을 하지 않도록).
  [ "$DRAINED_SVC" = "$svc" ] && DRAINED_SVC=""
  return 0
}

# ── 공개 edge 검증 (Caddy 경유) ────────────────────────────────────────────────
edge_ok() {  # 0 = /healthz 200 via Caddy
  if [ "$DRY_RUN" -eq 1 ]; then return 0; fi
  curl -sk -o /dev/null -w '%{http_code}' --max-time 8 \
    --resolve "$WEB_PUBLIC_HOST:443:127.0.0.1" "https://$WEB_PUBLIC_HOST/healthz" 2>/dev/null | grep -q '^200$'
}

restart_count() {  # $1 = svc
  local cid; cid="$(replica_cid "$1")"
  [ -n "$cid" ] && docker inspect -f '{{.RestartCount}}' "$cid" 2>/dev/null || echo 0
}

# ── Caddyfile 변경 reconcile (feature-0016) ──────────────────────────────────
# 호스트 Caddyfile 과 실행 caddy 컨테이너가 보는 파일의 sha 를 비교. 다르면(= 배포로 Caddyfile
# 이 바뀌었거나 git merge 가 inode 를 교체해 bind-mount 가 stale) caddy 를 recreate 해 현재 inode 를
# 재바인딩한다. (caddy reload 는 inode-stale 시 옛 내용을 다시 읽어 무효 — feature-0014 라이브 적발.)
# 변경 없으면 caddy 무접촉(blip 0). 변경 시에만 sub-second recreate.
reconcile_caddy() {
  step "Caddyfile reconcile (변경 시에만 caddy recreate)"
  [ -f "$CADDYFILE" ] || { warn "Caddyfile 없음($CADDYFILE) — reconcile skip"; return 0; }
  if [ -z "$("${DC[@]}" ps -q caddy 2>/dev/null)" ]; then
    log "caddy 미기동 — up -d caddy"; run "${DC[@]}" up -d --no-deps caddy; return 0
  fi
  local host_sha cont_sha
  host_sha="$(sha256sum "$CADDYFILE" 2>/dev/null | awk '{print $1}')"
  cont_sha="$("${DC[@]}" exec -T caddy cat /etc/caddy/Caddyfile 2>/dev/null | sha256sum 2>/dev/null | awk '{print $1}')"
  if [ -n "$cont_sha" ] && [ "$host_sha" = "$cont_sha" ]; then
    # feature-0020: config 무변경이어도 caddy 이미지 태그 갱신(caddy:2 re-pull)은 recreate 필요.
    # 단일 edge 라 recreate 는 수초 blip — 이미지 업그레이드 시에만 발생(평시 blip 0 유지).
    local ccid cimg_run cimg_local
    ccid="$("${DC[@]}" ps -q caddy 2>/dev/null | head -1)"
    cimg_run="$(docker inspect -f '{{.Image}}' "$ccid" 2>/dev/null || true)"
    cimg_local="$(docker image inspect "$(docker inspect -f '{{.Config.Image}}' "$ccid" 2>/dev/null)" -f '{{.Id}}' 2>/dev/null || true)"
    if [ -n "$cimg_run" ] && [ -n "$cimg_local" ] && [ "$cimg_run" != "$cimg_local" ]; then
      warn "Caddyfile 무변경이나 caddy 이미지 태그 갱신 감지 — recreate(수초 edge blip, 업그레이드 시에만)."
      run "${DC[@]}" up -d --no-deps --force-recreate caddy || die "caddy recreate 실패."
      local img_deadline=$(( SECONDS + 20 ))
      while [ "$SECONDS" -lt "$img_deadline" ]; do edge_ok && { log "caddy 이미지 갱신 recreate 후 edge 정상"; return 0; }; sleep 2; done
      warn "caddy recreate 후 edge 가 20s 내 200 아님 — soak 단계가 추가 감시."
      return 0
    fi
    log "Caddyfile 무변경(sha 일치) + 이미지 일치 — caddy 유지(blip 0)"; return 0
  fi
  log "Caddyfile 변경 감지(host=$(printf '%.12s' "$host_sha") != caddy=$(printf '%.12s' "$cont_sha")) — 검증 후 recreate"
  # recreate 전 adapt 검증(깨진 config 로 caddy 를 죽이지 않도록). throwaway 컨테이너에서 검증.
  if [ "$DRY_RUN" -ne 1 ]; then
    if ! docker run --rm -e WEB_PUBLIC_HOST="$WEB_PUBLIC_HOST" -e WEB_TLS_CERT_FILE=/c/f -e WEB_TLS_KEY_FILE=/c/k \
         -v "$PWD/$CADDYFILE:/etc/caddy/Caddyfile:ro" caddy:2 caddy adapt --config /etc/caddy/Caddyfile >/dev/null 2>&1; then
      die "새 Caddyfile 이 caddy adapt 실패 — recreate 중단(기존 caddy 유지). Caddyfile 문법 점검."
    fi
  fi
  run "${DC[@]}" up -d --no-deps --force-recreate caddy || die "caddy recreate 실패."
  # edge 회복 대기(짧은 recreate blip 후)
  local deadline=$(( SECONDS + 20 ))
  while [ "$SECONDS" -lt "$deadline" ]; do edge_ok && { log "caddy recreate 후 edge 정상"; return 0; }; sleep 2; done
  warn "caddy recreate 후 edge 가 20s 내 200 아님 — soak 단계가 추가 감시."
}

# ── post-cutover soak (부하 노출 후 안정성 + crash-loop 감시 → 자동 롤백) ────────
soak_or_rollback() {  # $1 = deployed sha
  local sha="$1" deadline=$(( SECONDS + SOAK_SECONDS )) rc_a rc_b base_a base_b
  local edge_fail_total=0   # 하드닝: flapping(200/503 교대) 이미지는 '연속 3회'를 영원히 못 채움 — 누적 기준 병행
  step "post-cutover soak (${SOAK_SECONDS}s) — edge + RestartCount 감시"
  [ "$DRY_RUN" -eq 1 ] && { log "[dry-run] soak skip"; return 0; }
  base_a="$(restart_count web-a)"; base_b="$(restart_count web-b)"
  while [ "$SECONDS" -lt "$deadline" ]; do
    if ! edge_ok; then
      # 하드닝(2026-07-11): 단발 edge 실패로 롤백하지 않는다 — 동시 부하/업스트림 헬스체크
      # 창의 일시 blip 이 정상 이미지를 롤백시킨 false-positive 실측. 2s 간격 연속 3회
      # 실패일 때만 결함으로 확증한다.
      local edge_fail=1 probe
      for probe in 2 3; do
        sleep 2
        if edge_ok; then edge_fail=0; break; else edge_fail="$probe"; fi
      done
      edge_fail_total=$(( edge_fail_total + 1 ))
      if [ "$edge_fail" = "0" ] && [ "$edge_fail_total" -lt "$EDGE_FLAP_MAX" ]; then
        # 회복했어도 blip 원인이 replica 재시작(crash-loop 1회차)일 수 있다 — continue 전에
        # RestartCount 즉시 재검(패널 적발: deadline 만료와 겹치면 재시작 검사가 영영 스킵).
        rc_a="$(restart_count web-a)"; rc_b="$(restart_count web-b)"
        if [ "${rc_a:-0}" -gt "${base_a:-0}" ] || [ "${rc_b:-0}" -gt "${base_b:-0}" ]; then
          warn "edge blip 회복했으나 RestartCount 증가(web-a:$base_a→$rc_a web-b:$base_b→$rc_b) — crash-loop. 롤백."
          auto_rollback "$sha"; return 1
        fi
        warn "edge 일시 blip(연속 3회 미만 회복, 누적 ${edge_fail_total}) — soak 계속."
        continue
      fi
      if [ "$edge_fail" = "0" ] && [ "$edge_fail_total" -ge "$EDGE_FLAP_MAX" ]; then
        warn "edge 실패 누적 ${edge_fail_total}회(비연속 flapping) — 결함 이미지 의심. 롤백 판정 진행."
      fi
      # edge 연속 3회 실패 — 의존성(DB) 문제인지 이미지 문제인지 구분(thrash 방지).
      if dependency_down; then
        warn "edge 비정상이지만 DB 의존성 down 으로 판단 — 이미지 롤백은 무의미(thrash 금지). 현 상태 유지 + 경보."
        return 0
      fi
      warn "edge /healthz 비정상 + 의존성 정상 → 이미지 결함 의심. last-good 롤백 시도."
      auto_rollback "$sha"; return 1
    fi
    rc_a="$(restart_count web-a)"; rc_b="$(restart_count web-b)"
    if [ "${rc_a:-0}" -gt "${base_a:-0}" ] || [ "${rc_b:-0}" -gt "${base_b:-0}" ]; then
      warn "replica RestartCount 증가(web-a:$base_a→$rc_a web-b:$base_b→$rc_b) — crash-loop 의심(restart:unless-stopped 가 은폐). 롤백."
      auto_rollback "$sha"; return 1
    fi
    sleep 5
  done
  log "soak 통과 — 배포 안정."
}

dependency_down() {  # 0 = DB(mysql/pg) 미가용으로 판단 (롤백 무의미)
  if [ "$DRY_RUN" -eq 1 ]; then return 1; fi
  ! ( "${DC_PROD[@]}" exec -T web-a python /app/scripts/healthcheck_web.py >/dev/null 2>&1 \
      || "${DC_PROD[@]}" exec -T web-b python /app/scripts/healthcheck_web.py >/dev/null 2>&1 )
}

auto_rollback() {  # $1 = 실패한 sha
  local good; good="$(lastgood_sha)"
  step "자동 롤백 → last-good=${good:-<none>}"
  [ -n "$good" ] || { err "last-good sha 기록 없음 — 수동 개입 필요. 현 상태 유지."; return 1; }
  if ! docker image inspect "$IMAGE_REPO:last-good" >/dev/null 2>&1; then
    err "last-good 이미지($IMAGE_REPO:last-good) 가 로컬에 없음 — 빠른 롤백 불가. 수동 개입 필요."; return 1
  fi
  # 워커 핀은 현행 유지(auto_rollback 은 web 결함 대응 — 워커는 이 시점 미접촉).
  local agent_pin=""
  docker image inspect "$AGENT_IMAGE_REPO:current" >/dev/null 2>&1 && agent_pin="$AGENT_IMAGE_REPO:current"
  write_pin_overlay "$IMAGE_REPO:last-good" "$agent_pin"; set_dc_prod
  local svc; for svc in "${REPLICAS[@]}"; do
    recreate_replica "$svc" "$good" || warn "$svc 롤백 recreate 문제 — 계속."
  done
  # 하드닝(2026-07-11): 롤백 recreate 직후 단발 프로브는 uvicorn 워밍업/Caddy 업스트림
  # 헬스체크 창과 겹쳐 false "수동 개입" 판정을 낸다(실측 — 판정 수 초 뒤 정상 회복).
  # 최대 60s(3s 간격) 회복 대기 후에만 수동 개입을 선언한다.
  local rb_deadline=$(( SECONDS + 60 )) rb_ok=1
  while [ "$SECONDS" -lt "$rb_deadline" ]; do
    if edge_ok; then rb_ok=0; break; fi
    sleep 3
  done
  if [ "$rb_ok" -eq 0 ]; then log "롤백 후 edge 정상."; else err "롤백 후에도 edge 비정상(60s 대기 후) — 수동 개입 필요."; fi
  state_set current "$good"
  # 리뷰 M-2: ":current 태그 = 현재 배포본" 불변식 복원 — 미복원 시 다음 배포의 last-good
  # 회전이 실패 이미지를 last-good 으로 오염시켜 2연속 실패에서 롤백 불능이 된다.
  if [ "$DRY_RUN" -ne 1 ]; then docker tag "$IMAGE_REPO:last-good" "$IMAGE_REPO:current" 2>/dev/null || true; fi
}

# ── 워커(insight/ask) 롤아웃 (feature-0020) ─────────────────────────────────────
# 워커는 큐 기반 + graceful SIGTERM(insight `_INSIGHT_SHUTDOWN` 루프경계 종료 — feature-0015
# 구현·stop_grace 30s / ask `_SHUTDOWN` + lease requeue·stop_grace 70s) + 멱등 쓰기라 단일
# 인스턴스 순차 recreate 로도 사용자 체감 무중단이다. 구 worker_divergence_warn(WARN-only,
# 수동 재빌드 안내 — "insight SIGTERM 핸들러 없음" 서술은 feature-0015 이후 stale)을 스파인
# 자동 롤아웃으로 대체한다(2026-07-13 attach-user-version 회고의 '워커 코드 미반영' 마찰 해소).
container_health() {  # $1=svc → healthy|starting|unhealthy|running|restarting|exited|none
  local cid; cid="$(replica_cid "$1")"
  [ -n "$cid" ] || { echo none; return 0; }
  docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || echo none
}

worker_commit() {  # $1=svc → 컨테이너의 GIT_COMMIT (실패 시 빈 값)
  "${DC_PROD[@]}" exec -T "$1" printenv GIT_COMMIT 2>/dev/null | tr -d '[:space:]' || true
}

# 워커 기동 실패 시 **원인을 화면에 남긴다**. 2026-08-13 배포에서 `ext-tool-mcp 상태=none` 만
# 출력한 채 워커군 전체가 롤백됐는데, 실제 원인은 컨테이너 로그 1줄
# (`ModuleNotFoundError: No module named 'mcp'`)이었다. 그 1줄이 없으면 운영자는 롤백된
# 컨테이너를 뒤져야 하고, 롤백이 이미 이미지를 바꾼 뒤라 원인 로그가 사라지기도 한다.
dump_service_logs() {  # $1=svc — 진단 전용(실패해도 배포 판정에 영향 없음)
  local svc="$1"
  [ "$DRY_RUN" -eq 1 ] && return 0
  err "  ↳ $svc 최근 로그 20줄:"
  "${DC[@]}" logs --tail 20 --no-color "$svc" 2>&1 | sed 's/^/      /' >&2 || true
}

wait_worker_healthy() {  # $1=svc $2=timeout_s $3=기대 sha("" = commit 검증 생략) → 0 성공
  local svc="$1" want="${3:-}" deadline=$(( SECONDS + $2 )) st got rc
  [ "$DRY_RUN" -eq 1 ] && return 0
  while [ "$SECONDS" -lt "$deadline" ]; do
    st="$(container_health "$svc")"
    rc="$(restart_count "$svc")"
    if [ "${rc:-0}" -gt 0 ]; then
      err "$svc RestartCount=$rc — 신규 컨테이너 crash-loop(restart 정책이 은폐 가능). 결함 판정."
      return 1
    fi
    case "$st" in
      healthy)
        got="$(worker_commit "$svc")"
        if [ -z "$want" ] || [ "$got" = "$want" ]; then log "  $svc healthy (GIT_COMMIT=${got:-?})"; return 0; fi
        err "$svc healthy 이지만 GIT_COMMIT=$got (기대=$want) — 핀/빌드 불일치."; return 1 ;;
      exited|dead|none)
        err "$svc 상태=$st — 기동 실패."; dump_service_logs "$svc"; return 1 ;;
    esac
    sleep 5
  done
  err "$svc 가 ${2}s 내 healthy 도달 실패(최종 상태=$(container_health "$svc"))."
  dump_service_logs "$svc"
  return 1
}

# ── ask-worker surge 롤아웃 (feature-0020 zd-ask-rollout) ─────────────────────
# **왜 ask-worker 만 다른가**: 종전엔 본체 교체 전에 전역 quiesce(진행 중 사용자 run 이
# 시스템 전체에서 0)를 기다렸다. 그 설계의 근거는 gateway 와 같았다 — "붙어 있는 것을 옮길 수
# 없으니 붙어 있는 게 없을 때 바꾼다". 그런데 그 전제는 ask-worker 에 **성립하지 않는다**:
#   - gateway 는 HTTP 소켓에 in-flight 가 붙어 있어 프로세스 간 이전이 불가능하다.
#   - ask-worker 는 **PG 큐 소비자**다. 신규 job 은 소켓이 아니라 `ask_jobs` 에서 오고, claim 은
#     `FOR UPDATE SKIP LOCKED` + lease_epoch fencing 이라 다중 인스턴스가 exactly-once 다.
# 즉 "신규는 surge 가 받고 본체는 자기 in-flight 만 완주" 가 성립한다. 그러면 정적 창을 기다릴
# 이유 자체가 사라진다.
#
# 그 차이가 실제로 얼마나 컸는가(2026-08-14 라이브 실측 — 본 변경의 계기):
#   유입 7~10분 간격 · run p50 81s/p95 691s → 상한 900s 안에 전역 정적 창이 **생기지 않는다**.
#   ask-worker 가 배포되지 못했고, 순차 롤아웃이라 그 **뒤 워커(ops-scheduler·ext-tool-mcp)까지
#   연쇄로** 구버전에 묶였다. 배포가 부분 완료로 끝나고 재실행해도 같은 자리에서 다시 막혔다.
#   설계 문서는 "조용한 시간에 재실행" 을 전제했지만, 그것은 사람이 창을 노려야 한다는 뜻이고
#   그 사이 보안 게이트 같은 시급한 변경이 라이브에 도달하지 못한다.
#
# 반환 규약(호출자가 롤백 여부를 가른다 — 이 구분이 없으면 무관한 실패에 멀쩡한 워커를 되돌린다):
#   0 = 교체 완료 / 1 = **신 이미지 결함**(본체가 신 이미지로 못 뜸 → 워커군 롤백 대상)
#   2 = 본체 무접촉 중단(surge 준비 실패 등 — 구 워커가 계속 서빙, 롤백 불필요)
# ⚠ `ps -aq` 다(`ps -q` 아님). compose v2 의 `ps -q` 는 **running 만** 반환한다 — 라이브 실측
# (2026-08-14 자가 검증): stop 직후 `ps -q` = 빈 값, `ps -aq` = cid. leaked surge 는 대개
# "stop 은 됐는데 rm 이 실패한" 형태로 남으므로, `ps -q` 로 찾으면 **정확히 그 형태를 놓친다**
# (그 컨테이너는 `up -d` 로 되살아나 큐에서 다시 일한다). 존재 여부는 상태와 무관해야 한다.
ask_surge_cid() { "${DC_SURGE_PROD[@]}" ps -aq "$ASK_WORKER_SURGE" 2>/dev/null | head -1; }

ask_surge_health() {
  local cid; cid="$(ask_surge_cid)"
  [ -n "$cid" ] || { echo none; return 0; }
  docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || echo none
}

wait_ask_surge_healthy() {  # $1 = timeout_s → 0 성공
  local deadline=$(( SECONDS + $1 )) st none_streak=0
  [ "$DRY_RUN" -eq 1 ] && return 0
  while [ "$SECONDS" -lt "$deadline" ]; do
    st="$(ask_surge_health)"
    [ "$st" = "healthy" ] && return 0
    case "$st" in
      exited|dead) err "$ASK_WORKER_SURGE 상태=$st — 기동 실패."; dump_service_logs "$ASK_WORKER_SURGE"; return 1 ;;
      none)
        none_streak=$(( none_streak + 1 ))
        [ "$none_streak" -ge 5 ] && { err "$ASK_WORKER_SURGE 컨테이너 미검출 연속 ${none_streak}회 — 기동 즉사 판정."; dump_service_logs "$ASK_WORKER_SURGE"; return 1; } ;;
      *) none_streak=0 ;;
    esac
    sleep 3
  done
  err "$ASK_WORKER_SURGE 가 ${1}s 내 healthy 도달 실패(최종=$(ask_surge_health))."
  dump_service_logs "$ASK_WORKER_SURGE"
  return 1
}

# 그 컨테이너가 **자기 이름으로 claim 한** running job 수. worker_id 는
# `ask-worker[<role>]-<hostname>-<pid>` 이고 hostname 은 컨테이너 hostname 이다.
# 조회 불가는 0 이 아니라 unknown — 여기서 0 으로 읽으면 "다 끝났다" 는 거짓 안심이 된다.
ask_container_hostname() {  # $1 = svc → 컨테이너 hostname | 빈 값(부재/조회 불가)
  # `ps -aq` — stopped 도 포함해야 한다. drain **후** 조회가 이 함수의 주 용도이고, 그 시점
  # 컨테이너는 정지 상태라 `ps -q` 로는 안 보인다(라이브 실측 2026-08-14).
  local cid
  cid="$("${DC_SURGE_PROD[@]}" ps -aq "$1" 2>/dev/null | head -1)"
  [ -n "$cid" ] || return 0
  docker inspect -f '{{.Config.Hostname}}' "$cid" 2>/dev/null | tr -d '[:space:]'
}

# 그 **인스턴스가 자기 이름으로 claim 한** running job 수. worker_id 는
# `ask-worker[<role>]-<hostname>-<pid>` 이고 hostname 은 컨테이너 hostname 이다.
# 조회 불가는 0 이 아니라 unknown — 여기서 0 으로 읽으면 "다 끝났다" 는 거짓 안심이 된다.
ask_running_jobs_for_host() {  # $1 = hostname → 정수 | "unknown"
  [ -n "$1" ] || { echo unknown; return 0; }
  _ask_jobs_count "claimed_by LIKE '%-${1}-%'"
}

# surge/본체를 **완주 예산 안에서** 내린다. 컨테이너는 SIGTERM 을 받으면 신규 claim 을 멈추고
# 자기 in-flight 만 마친 뒤 스스로 종료한다 — 정상 경로에서는 이 호출이 예산을 다 쓰지 않는다.
# 예산을 다 쓰면 docker 가 SIGKILL 하므로, 그 사실을 **조용히 넘기지 않고 보고**한다.
drain_stop_ask() {  # $1 = svc, $2 = 라벨 → 0 완주 종료 / 1 예산 초과 또는 잔존 run
  local svc="$1" label="$2" host before after t0 elapsed
  [ "$DRY_RUN" -eq 1 ] && { log "[dry-run] drain-stop $svc (예산 ${ASK_DRAIN_TIMEOUT}s)"; return 0; }
  # ⚠ hostname 을 **stop 전에** 확보한다. 초판은 stop 후에 컨테이너로 다시 조회했는데,
  # `ps -q` 가 running 만 반환하므로 그 시점엔 빈 값이 나와 **`after` 가 항상 0** 이었다
  # (라이브 자가 검증 2026-08-14에서 적발). 그러면 "보유 N→0 — 끊긴 run 없음" 이 관측이 아니라
  # 상수가 된다 — 정확히 이 저장소가 반복해서 경계해 온 vacuous pass 다.
  host="$(ask_container_hostname "$svc")"
  before="$(ask_running_jobs_for_host "$host")"
  step "drain-stop: $label — 신규 claim 중지 후 진행 중 run 완주 대기(예산 ${ASK_DRAIN_TIMEOUT}s, 현재 보유 ${before})"
  t0=$SECONDS
  "${DC_SURGE_PROD[@]}" stop -t "$ASK_DRAIN_TIMEOUT" "$svc" >/dev/null 2>&1 || warn "$label stop 명령이 비정상 종료 — 상태로 판정한다."
  elapsed=$(( SECONDS - t0 ))
  after="$(ask_running_jobs_for_host "$host")"
  if [ "$elapsed" -ge "$ASK_DRAIN_TIMEOUT" ]; then
    warn "$label: drain 예산(${ASK_DRAIN_TIMEOUT}s) 소진 — 남은 run 은 SIGKILL 됐고 lease 반납/role-reclaim 으로 재큐된다(사용자에겐 재실행)."
    QUIESCE_REPORT="${QUIESCE_REPORT}${QUIESCE_REPORT:+ · }${label}=DRAIN-TIMEOUT(보유 ${before}→${after})"
    QUIESCE_FORCED=$(( QUIESCE_FORCED + 1 ))
    return 1
  fi
  # 정상 종료했는데도 그 인스턴스 소유 running 이 남아 있으면, 완주도 반납도 못 한 run 이다
  # (SIGKILL 이나 lease 반납 실패). role-reclaim 이 곧 회수하지만 **사용자에겐 재실행**이므로
  # "끊긴 run 없음" 으로 보고해서는 안 된다. `unknown` 도 조용함으로 읽지 않는다.
  case "$after" in
    0) log "  $label: ${elapsed}s 만에 완주 종료(보유 ${before}→0) — 끊긴 run 없음."
       QUIESCE_REPORT="${QUIESCE_REPORT}${QUIESCE_REPORT:+ · }${label}=drained(${elapsed}s)"
       return 0 ;;
    unknown)
       warn "$label: ${elapsed}s 에 종료했으나 잔존 run 을 **관측하지 못했다**(보유 ${before}→unknown). 조용함으로 읽지 않는다."
       QUIESCE_REPORT="${QUIESCE_REPORT}${QUIESCE_REPORT:+ · }${label}=drained-unverified(${elapsed}s)"
       return 1 ;;
    *) warn "$label: ${elapsed}s 에 종료했으나 그 인스턴스 소유 running 이 ${after}건 남았다 — 완주도 반납도 못 한 run 이다(role-reclaim 이 회수하지만 사용자에겐 재실행)."
       QUIESCE_REPORT="${QUIESCE_REPORT}${QUIESCE_REPORT:+ · }${label}=CUT(보유 ${before}→${after})"
       QUIESCE_FORCED=$(( QUIESCE_FORCED + 1 ))
       return 1 ;;
  esac
}

# 직전 배포가 정리 전에 죽었으면 surge 가 남아 **구 이미지로 사용자 job 을 계속 처리**한다
# (gateway 의 leaked surge 와 같은 부류이나, 이쪽은 DNS 가 아니라 큐라 더 조용히 지속된다).
sweep_leaked_ask_surge() {
  [ "$DRY_RUN" -eq 1 ] && return 0
  local leaked; leaked="$(ask_surge_cid)"
  [ -n "$leaked" ] || return 0
  warn "leaked ask-worker surge 감지(직전 배포 잔존) — 본체 healthy 확인 후 drain 정리."
  if [ "$(container_health "$ASK_WORKER_SERVICE")" = "healthy" ]; then
    drain_stop_ask "$ASK_WORKER_SURGE" "leaked ask surge" || true
    run "${DC_SURGE_PROD[@]}" rm -f "$ASK_WORKER_SURGE" || true
    log "leaked ask surge 정리 완료."
  else
    warn "본체 비정상 — leaked surge 유지(유일 처리 주체 가능성). 수동 확인 필요."
  fi
}

rollout_ask_worker_via_surge() {  # $1 = 대상 sha → 0 성공 / 1 이미지 결함 / 2 본체 무접촉 중단
  local sha="$1"
  step "ask-worker 무중단 롤아웃 (surge 교대 — 전역 정적 대기 없음)"
  # 1) surge 기동(신 이미지 핀) + healthy. 실패 시 **본체 무접촉** — 구 워커가 계속 처리한다.
  if ! run "${DC_SURGE_PROD[@]}" up -d --no-deps --no-build "$ASK_WORKER_SURGE" \
     || ! wait_ask_surge_healthy "$WORKER_READY_TIMEOUT"; then
    run "${DC_SURGE_PROD[@]}" rm -sf "$ASK_WORKER_SURGE" || true
    err "surge 기동 실패 — 본체 무접촉 유지(구 ask-worker 가 계속 처리). 새 이미지 점검 후 재실행(멱등)."
    return 2
  fi
  stamp_sanctioned_recreate "$ASK_WORKER_SURGE"
  log "surge healthy — 이 시점부터 신규 job 은 surge(신 코드)가 가져간다."
  # 2) 본체 drain — 신규는 surge 가 받으므로 본체는 자기 in-flight 만 마치면 된다.
  #    예산 초과(강제 종료)는 배포를 중단시키지 않는다: 그 run 들은 lease 반납/role-reclaim 으로
  #    재큐되고 surge 가 이어받는다(= 종전 동작과 동일한 최악값). 다만 보고에는 남긴다.
  drain_stop_ask "$ASK_WORKER_SERVICE" "ask-worker 본체" || true
  # 3) 본체를 신 이미지로 재생성.
  log "recreate $ASK_WORKER_SERVICE → $AGENT_IMAGE_REPO:$sha"
  if ! run "${DC_PROD[@]}" up -d --no-deps --no-build --force-recreate "$ASK_WORKER_SERVICE" \
     || ! wait_worker_healthy "$ASK_WORKER_SERVICE" "$WORKER_READY_TIMEOUT" "$sha"; then
    err "ask-worker 본체가 신 이미지로 기동 실패 — surge 가 임시로 처리 중(의도적 유지)."
    err "  주의: surge 는 restart:no 라 호스트 재부팅 시 소멸한다. 롤백 후 정리가 필요하다."
    return 1
  fi
  stamp_sanctioned_recreate "$ASK_WORKER_SERVICE"
  # 4) surge 정리 — 교체 창에 surge 로 들어간 run 도 같은 완주 예산을 받는다(대칭).
  drain_stop_ask "$ASK_WORKER_SURGE" "ask-worker surge" || true
  run "${DC_SURGE_PROD[@]}" rm -f "$ASK_WORKER_SURGE" || warn "surge rm 문제 — 다음 배포의 leaked sweep 이 정리한다."
  log "ask-worker 무중단 교체 완료(진행 중 run 을 기다린 것이 아니라, 받는 쪽을 먼저 세웠다)."
  return 0
}

deploy_workers() {  # $1 = 대상 sha, $2 = pin overlay 의 web image ref(롤백 시 유지) → 0 성공.
  local sha="$1" web_img="$2" svc st got rc
  local -a deferred=()        # 본체 무접촉으로 미교체된 서비스(롤백 대상 아님)
  step "워커 롤아웃 (${WORKERS[*]} — one-at-a-time, ask-worker 는 surge 교대)"
  sweep_leaked_ask_surge
  for svc in "${WORKERS[@]}"; do
    # 멱등 skip: 이미 대상 sha + healthy 면 무접촉(인터럽트된 배포 재개 지원).
    if [ "$DRY_RUN" -ne 1 ]; then
      st="$(container_health "$svc")"; got="$(worker_commit "$svc")"
      if [ "$st" = "healthy" ] && [ "$got" = "$sha" ]; then
        log "$svc 이미 $sha + healthy — skip(멱등)."; continue
      fi
    fi
    if [ "$svc" = "$ASK_WORKER_SERVICE" ]; then
      rc=0; rollout_ask_worker_via_surge "$sha" || rc=$?
      case "$rc" in
        0) : ;;
        2)
          # ⚠ **연쇄 차단을 끊는다**(2026-08-14 실측 결함): 종전엔 여기서 return 1 이라
          # ask-worker 하나가 못 바뀌면 그 뒤 ops-scheduler·ext-tool-mcp 까지 구버전에 묶였다.
          # 그 서비스들은 사용자 run 과 무관하고 ask-worker 와 의존 관계도 없다 — 같이 막을
          # 이유가 없다. 미교체 사실은 아래 완결 판정이 **끝까지 들고 가서** 보고한다.
          warn "$svc 미교체(본체 무접촉) — 나머지 워커는 계속 롤아웃한다."
          deferred+=("$svc"); continue ;;
        *)
          err "$svc 롤아웃 실패(신 이미지 결함 의심) — 워커군 last-good 롤백. (web 은 기존 서빙 유지 — expand/contract 게이트가 혼합 버전 안전을 보장. CONVENTIONS §12)"
          rollback_workers "$web_img"; return 1 ;;
      esac
      continue
    fi
    log "recreate $svc → $AGENT_IMAGE_REPO:$sha"
    if ! run "${DC_PROD[@]}" up -d --no-deps --no-build --force-recreate "$svc" \
       || ! wait_worker_healthy "$svc" "$WORKER_READY_TIMEOUT" "$sha"; then
      err "$svc 롤아웃 실패 — 워커군 last-good 롤백 시도. (web 은 기존 서빙 유지 — expand/contract 게이트가 혼합 버전 안전을 보장. CONVENTIONS §12)"
      rollback_workers "$web_img"
      return 1
    fi
    stamp_sanctioned_recreate "$svc"
  done
  # feature-0045: 브리지 MCP 표면은 여기서 다루지 않는다 — **엣지 전환보다 먼저** 세워야
  # 하므로 web 롤링 직후(reconcile_caddy 앞)로 옮겼다(main 참조). 완결 판정에는 포함된다.

  # ── 완결 판정 (feature-0020 zd-ask-rollout) ────────────────────────────────
  # `agent_current` 는 "워커가 이 sha 로 돌고 있다" 는 주장이다. 부분 롤아웃에서 그것을 기록하면
  # 다음 배포의 멱등 skip(build_agent_image)이 **그 주장을 믿고 빌드를 건너뛴다** — 미교체
  # 컨테이너가 조용히 영구 stale 이 되는 경로다. 실제로 이 결함은 라이브에 있었다(2026-08-14:
  # insight 만 e545796f 인데 state 는 95f5ea0f). 그래서 **실제 컨테이너를 다시 읽어** 판정한다.
  if ! verify_workers_at_sha "$sha"; then
    err "워커 롤아웃 **부분 완료** — 아래 미도달 서비스가 남았다. agent_current 를 기록하지 않는다(다음 배포가 멱등하게 이어서 완료한다)."
    [ "${#deferred[@]}" -gt 0 ] && err "  미교체(무접촉): ${deferred[*]} — 원인 해소 후 재실행하면 이어서 완료된다."
    return 1
  fi
  state_set agent_current "$sha"
  log "워커 롤아웃 완료 — ${WORKERS[*]} = $AGENT_IMAGE_REPO:$sha"
}

# 모든 워커가 실제로 대상 sha 로 healthy 한지 **컨테이너에서 직접** 확인. state 파일이나
# 스크립트 진행 상황이 아니라 라이브 상태가 완결의 근거다("성공 보고 ≠ 실제 배포" — LRN-20260811T1557).
verify_workers_at_sha() {  # $1 = sha → 0 전부 도달
  local sha="$1" svc st got ok=0
  [ "$DRY_RUN" -eq 1 ] && return 0
  step "워커 완결 판정 (서비스별 GIT_COMMIT 실측)"
  # feature-0045: MCP replica 도 같은 agent 이미지를 쓰므로 완결 판정에 포함한다. 빠지면
  # "배포는 됐는데 개인 AI 가 붙는 표면만 구코드" 가 조용히 지나간다.
  for svc in "${WORKERS[@]}" "${MCP_REPLICAS[@]}"; do
    st="$(container_health "$svc")"; got="$(worker_commit "$svc")"
    if [ "$st" = "healthy" ] && [ "$got" = "$sha" ]; then
      log "  $svc = $sha (healthy)"
    else
      err "  $svc = ${got:-?} (상태=$st) — 기대 $sha"
      ok=1
    fi
  done
  return "$ok"
}

# ── 브리지 MCP 표면 롤링 (feature-0045) ───────────────────────────────────────
# 개인 AI 가 붙어 있는 `/api/ai/mcp` 의 upstream 을 **한 번에 하나씩** 교체한다. 종전에는 이
# 서비스가 WORKERS 안에 있어 `up -d --force-recreate` 한 방으로 통째로 끊겼다.
#
# web 롤링과 다른 점 두 가지:
#  · 앱 드레인이 없다. 이 프로세스는 상태를 들지 않고(stateless) 요청을 web 으로 중계할 뿐이라,
#    문을 닫는 대신 **stop_grace(130s)** 로 진행 중 중계가 완주하게 한다.
#  · 엣지 후보 복귀를 admin API 로 확인하지 않는다. 이 라우트는 passive 격리만 쓰므로
#    컨테이너 healthy 가 곧 후보 자격이다(Caddyfile `/api/ai/mcp` 블록 주석 참조).
rollout_mcp_replicas() {  # $1 = 대상 sha → 0 성공 / 1 실패
  local sha="$1" svc other st got
  step "브리지 MCP 표면 롤링 (${MCP_REPLICAS[*]} — one-at-a-time, 항상 ≥1 후보)"
  if [ "$DRY_RUN" -eq 1 ]; then
    for svc in "${MCP_REPLICAS[@]}"; do log "[dry-run] recreate $svc → $AGENT_IMAGE_REPO:$sha"; done
    return 0
  fi
  # 최초 전환(구 단일 서비스에서 올라오는 배포)이면 두 replica 가 아예 없다 — 동시에 올린다.
  local missing=0
  for svc in "${MCP_REPLICAS[@]}"; do
    [ -n "$("${DC_PROD[@]}" ps -q "$svc" 2>/dev/null)" ] || missing=$(( missing + 1 ))
  done
  if [ "$missing" -eq "${#MCP_REPLICAS[@]}" ]; then
    log "MCP replica 부재(최초 전환) — ${MCP_REPLICAS[*]} 동시 기동."
    run "${DC_PROD[@]}" up -d --no-deps --no-build --force-recreate "${MCP_REPLICAS[@]}" \
      || { err "MCP replica 초기 기동 실패."; return 1; }
    for svc in "${MCP_REPLICAS[@]}"; do
      wait_worker_healthy "$svc" "$WORKER_READY_TIMEOUT" "$sha" || return 1
    done
    return 0
  fi
  for svc in "${MCP_REPLICAS[@]}"; do
    st="$(container_health "$svc")"; got="$(worker_commit "$svc")"
    if [ "$st" = "healthy" ] && [ "$got" = "$sha" ]; then
      log "$svc 이미 $sha + healthy — skip(멱등)."; continue
    fi
    # fail-closed: 상대가 healthy 가 아니면 이쪽을 내리지 않는다(내리면 MCP 전면 단절).
    other=""
    local cand; for cand in "${MCP_REPLICAS[@]}"; do [ "$cand" != "$svc" ] && other="$cand"; done
    # ⚠ `ps -q` 는 **running 만** 돌려준다 — 상대가 exited/crash 면 빈 문자열이라 가드가 통째로
    #   건너뛰어진다. 즉 "상대가 죽어 있을 때" 라는 **가장 위험한 경우에만** 보호가 사라진다.
    #   `ps -aq` 로 존재를 보고, 존재하는데 healthy 가 아니면 중단한다(predrain 과 같은 자세).
    if [ -n "$other" ] && [ -n "$("${DC_PROD[@]}" ps -aq "$other" 2>/dev/null)" ]; then
      if [ "$(container_health "$other")" != "healthy" ]; then
        err "$other 가 healthy 아님(상태=$(container_health "$other")) — $svc 를 내리면 MCP 후보가 0 이 된다(개인 AI 연결 전면 단절). 중단."
        err "  복구: docker compose -f docker-compose.yml up -d --no-deps $other  → healthy 확인 후 재실행(멱등)."
        return 1
      fi
    fi
    log "recreate $svc → $AGENT_IMAGE_REPO:$sha (상대 $other 가 서빙)"
    if ! run "${DC_PROD[@]}" up -d --no-deps --no-build --force-recreate "$svc" \
       || ! wait_worker_healthy "$svc" "$WORKER_READY_TIMEOUT" "$sha"; then
      err "$svc 롤아웃 실패 — 상대 replica 가 계속 서빙 중(MCP 연결 유지). 원인 해결 후 재실행(멱등)."
      return 1
    fi
    stamp_sanctioned_recreate "$svc"
  done
  log "MCP 표면 롤링 완료 — ${MCP_REPLICAS[*]} = $AGENT_IMAGE_REPO:$sha"
}

# 구 단일 서비스(`ext-tool-mcp`)의 잔존 컨테이너를 정리한다. compose 정의에서 사라졌으므로
# `up -d` 는 이 컨테이너를 건드리지 않는다 — 그대로 두면 **두 세대가 동시에 도는** 상태로
# 남고(포트는 안 겹치지만 구코드가 계속 web 을 두드린다), 다음 배포도 알아채지 못한다.
sweep_legacy_ext_tool_mcp() {
  [ "$DRY_RUN" -eq 1 ] && return 0
  local cid=""
  # ⚠ **이 조회는 실패한다.** 서비스가 compose 정의에서 사라졌으므로 `ps -aq <name>` 은
  #   `no such service` + **exit 1** 이다(라이브 실측 2026-08-27). `set -euo pipefail` 하에서
  #   그 명령 치환이 실패하면 배포 스크립트가 **그 자리에서 죽는다** — 실제로 첫 전환 배포가
  #   MCP 롤아웃 직후 중단됐고 워커·gateway 가 구 코드로 남았다(그리고 호출측 파이프가 그
  #   exit 을 가려 '성공' 으로 보였다). 정리는 best-effort 이므로 실패를 흡수한다.
  cid="$("${DC_PROD[@]}" ps -aq "$MCP_LEGACY_SERVICE" 2>/dev/null | head -1 || true)"
  if [ -z "$cid" ]; then
    # compose 가 이름을 모르면 **라벨로** 찾는다 — 목적은 조회가 아니라 정리다. 프로젝트
    # 스코프를 함께 걸어 다른 compose 프로젝트의 동명 컨테이너를 건드리지 않는다.
    local proj; proj="$(basename "$REPO_ROOT")"
    cid="$(docker ps -aq \
             --filter "label=com.docker.compose.project=$proj" \
             --filter "label=com.docker.compose.service=$MCP_LEGACY_SERVICE" \
             2>/dev/null | head -1 || true)"
  fi
  [ -n "$cid" ] || return 0
  log "구 $MCP_LEGACY_SERVICE 컨테이너 정리(2-replica 로 대체됨)."
  run docker rm -f "$cid" >/dev/null 2>&1 || warn "구 $MCP_LEGACY_SERVICE 제거 실패 — 수동 확인 필요."
  return 0
}

# ── MCP 표면 롤아웃 단계 (feature-0045) ───────────────────────────────────────
# **엣지 전환(`reconcile_caddy`)보다 먼저** 돌아야 한다. Caddyfile 이 `ext-tool-mcp-a/b` 를
# 가리키도록 바뀌는데 그 컨테이너가 아직 없으면, 리로드 직후부터 DNS 미해석 → 502 다. 그 창은
# soak(90s) + 워커 롤아웃 전체로 이어진다 — "배포마다 AI 연결이 끊긴다" 를 고치는 배포가 바로
# 그 연결을 가장 길게 끊는 셈이 된다.
#
# 구 컨테이너 정리는 **신규가 healthy 해진 뒤**에 한다. 파괴를 생성보다 먼저 하면, 기동 실패가
# 곧 "구세대도 없고 신세대도 없는" 상태가 된다.
rollout_mcp_phase() {
  [ "$SCOPE" = "web" ] && { log "scope=web — MCP 표면 롤아웃 skip(agent 이미지 미빌드)."; return 0; }
  if ! rollout_mcp_replicas "$TARGET_SHA"; then
    err "MCP 표면 롤아웃 실패 — 엣지 전환을 하지 않는다(현 라우팅 유지)."
    err "  web 은 $TARGET_SHA 서빙 중이다(부분 완료). 원인 해결 후 재실행하면 이어서 완료된다(멱등)."
    exit 1
  fi
  sweep_legacy_ext_tool_mcp
}

rollback_workers() {  # $1 = pin overlay 에 유지할 web image ref
  local web_img="$1" good svc
  good="$(agent_lastgood_sha)"
  step "워커 롤백 → agent last-good=${good:-<none>}"
  if [ -z "$good" ] || ! docker image inspect "$AGENT_IMAGE_REPO:last-good" >/dev/null 2>&1; then
    err "agent last-good 이미지 없음 — 워커 자동 롤백 불가(수동 개입 필요). 첫 스파인 워커 배포 실패라면 구 repo-* 이미지는 로컬에 남아 있다 — 복구: docker compose -f docker-compose.yml up -d --no-deps <svc> (base file-set = repo-* 이미지 복귀)."
    return 1
  fi
  write_pin_overlay "$web_img" "$AGENT_IMAGE_REPO:last-good"; set_dc_prod
  # ⚠ surge 를 **먼저** 없앤다 — 롤백은 "신 코드를 라이브에서 뺀다" 는 뜻인데, surge 가 남아
  # 있으면 큐에서 신 코드가 계속 job 을 가져간다(DNS 가 아니라 큐라 겉보기로는 조용하다).
  # 롤백 경로이므로 완주를 기다리지 않는다(복구 우선 — rollback_workers 의 기존 비대칭과 동일).
  if [ "$DRY_RUN" -ne 1 ] && [ -n "$(ask_surge_cid)" ]; then
    warn "롤백: ask-worker surge 제거(신 코드 격리 우선 — surge 가 들고 있던 run 은 재큐된다)."
    run "${DC_SURGE_PROD[@]}" rm -sf "$ASK_WORKER_SURGE" || true
  fi
  # §18.8 패널 P1-5(부분 수용): 롤백에는 quiesce **게이트를 걸지 않는다** — 롤백은 복구 경로이고
  # 여기서 막으면 결함 있는 배포가 그대로 남는다(feature-0014 가 엣지 게이트를 롤백 경로에서
  # 비차단으로 둔 것과 같은 근거: "롤백은 완주가 우선"). 다만 **침묵하지는 않는다** — 무엇을
  # 끊고 가는지 수치로 남긴다. 정방향은 기다리고 롤백은 끊는다는 비대칭이 로그에 보여야 한다.
  if [ "$DRY_RUN" -ne 1 ]; then
    local _rb_smp; _rb_smp="$(quiesce_sample)"
    if quiesce_sample_is_quiet "$_rb_smp"; then
      log "롤백 전 관측: 진행 중 사용자 run 0 — 끊기는 요청 없음."
    else
      warn "롤백 전 관측: 진행 중 사용자 run 있음(fresh|stale|streams = $_rb_smp) — **롤백은 대기하지 않는다**(복구 우선). 해당 요청은 끊긴다."
      QUIESCE_REPORT="${QUIESCE_REPORT}${QUIESCE_REPORT:+ · }rollback=CUT($_rb_smp)"
      QUIESCE_FORCED=$(( QUIESCE_FORCED + 1 ))
    fi
  fi
  for svc in "${WORKERS[@]}"; do
    run "${DC_PROD[@]}" up -d --no-deps --no-build --force-recreate "$svc" || warn "$svc 롤백 recreate 문제 — 계속."
    wait_worker_healthy "$svc" "$WORKER_READY_TIMEOUT" "$good" || warn "$svc 롤백 후에도 비정상 — 수동 확인 필요."
  done
  state_set agent_current "$good"
  # 리뷰 M-2: current 태그 불변식 복원 (auto_rollback 과 동일 근거 — 오염 방지).
  if [ "$DRY_RUN" -ne 1 ]; then docker tag "$AGENT_IMAGE_REPO:last-good" "$AGENT_IMAGE_REPO:current" 2>/dev/null || true; fi
}

# ── bedrock-gateway 무중단 reconcile (feature-0020) — 드리프트 시에만 surge 교체 ──
# 단일 gateway(LLM 관문) 재배포 창의 요청 실패(SPOF)를 없앤다: 드리프트 감지 시에만
#   surge replica(profile deploy-surge, DNS alias `bedrock-gateway`) 기동 → healthy →
#   본체 recreate(신규 요청은 alias 로 surge 가 흡수, in-flight 는 stop_grace 120s drain)
#   → 본체 healthy → surge graceful 종료.
# steady-state 리소스 증가 0(평시 surge 미기동). 상시 2-replica HA 는 범위 밖(unit ANCHOR §2).
gateway_health() {  # $1=svc
  local cid; cid="$("${DC_SURGE[@]}" ps -q "$1" 2>/dev/null | head -1)"
  [ -n "$cid" ] || { echo none; return 0; }
  docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || echo none
}

wait_gateway_healthy() {  # $1=svc $2=timeout_s
  local svc="$1" deadline=$(( SECONDS + $2 )) st none_streak=0
  [ "$DRY_RUN" -eq 1 ] && return 0
  while [ "$SECONDS" -lt "$deadline" ]; do
    st="$(gateway_health "$svc")"
    [ "$st" = "healthy" ] && return 0
    case "$st" in
      exited|dead) err "$svc 상태=$st"; return 1 ;;
      none)
        # 리뷰 m-2: 즉사(exited→ps 미표시)면 none 이 지속 — 타임아웃까지 태우지 않고 조기 실패.
        none_streak=$(( none_streak + 1 ))
        [ "$none_streak" -ge 5 ] && { err "$svc 컨테이너 미검출 연속 ${none_streak}회 — 기동 즉사 판정."; return 1; } ;;
      *) none_streak=0 ;;
    esac
    sleep 3
  done
  err "$svc 가 ${2}s 내 healthy 도달 실패(최종=$(gateway_health "$svc"))."
  return 1
}

# 리뷰 M-1: 직전 배포가 surge 정리 전에 죽었으면(비정상 종료·수동 복구 누락) leaked surge 가
# DNS alias 로 stale config/이미지 트래픽을 계속 서빙한다(restart:no — 재부팅까지 잔존).
# 본체 healthy 일 때만 정리(본체 비정상이면 surge 가 유일 서빙 — 유지 + 경고).
sweep_leaked_surge() {
  [ "$DRY_RUN" -eq 1 ] && return 0
  local leaked; leaked="$("${DC_SURGE[@]}" ps -q "$GATEWAY_SURGE" 2>/dev/null | head -1)"
  [ -n "$leaked" ] || return 0
  warn "leaked surge replica 감지(직전 배포 잔존) — 본체 healthy 확인 후 정리."
  if wait_gateway_healthy "$GATEWAY_SERVICE" 30; then
    run "${DC_SURGE[@]}" stop "$GATEWAY_SURGE" || true
    run "${DC_SURGE[@]}" rm -f "$GATEWAY_SURGE" || true
    log "leaked surge 정리 완료."
  else
    warn "본체 비정상 — leaked surge 유지(유일 서빙 가능성). 수동 개입 필요."
  fi
}

# conv-audit FR-llm-transient-failure-kills-run (§18.8 패널 P1-3): gateway 를 recreate 하면
# 진행 중 LLM 호출은 구 컨테이너의 `stop_grace_period` 안에 끝나야 살아남는다. 운영자가 관리
# 콘솔/`.env` 에서 `AGENT_TIMEOUT_SEC` 를 grace 보다 크게 올리면 그 초과분은 **매 배포마다
# SIGKILL** 되는데, compose 값은 정적이라 아무도 그 드리프트를 알려주지 않는다. 배포 때마다
# 표면화한다(경고만 — 배포를 막지는 않는다. 앱 층 재시도가 backstop 이므로 치명이 아니다).
gateway_grace_drift_warn() {
  local grace_raw grace_sec to_sec
  grace_raw="$(sed -n '/^  bedrock-gateway:/,/^  [a-z]/p' docker-compose.yml \
                 | sed -n 's/^[[:space:]]*stop_grace_period:[[:space:]]*\([0-9]*\)s.*/\1/p' | head -1)"
  [ -n "$grace_raw" ] || return 0
  grace_sec="$grace_raw"
  to_sec="$(sed -n 's/^AGENT_TIMEOUT_SEC=\([0-9]*\).*/\1/p' .env 2>/dev/null | tail -1)"
  [ -n "$to_sec" ] || return 0
  if [ "$to_sec" -ge "$grace_sec" ] 2>/dev/null; then
    warn "gateway stop_grace_period=${grace_sec}s < AGENT_TIMEOUT_SEC=${to_sec}s — 이 배포에서 진행 중인"
    warn "  장시간 LLM 호출이 SIGKILL 될 수 있습니다(앱 층 일시 실패 재시도가 흡수하지만, 재시도"
    warn "  상한을 넘기면 사용자 요청이 실패합니다). compose grace 를 올리거나 타임아웃을 낮추세요."
  fi
}

deploy_gateway_reconcile() {
  step "bedrock-gateway reconcile (드리프트 시에만 surge 무중단 교체)"
  gateway_grace_drift_warn
  [ -f "$GATEWAY_CONFIG_FILE" ] || { warn "gateway config 없음($GATEWAY_CONFIG_FILE) — reconcile skip."; return 0; }
  local cid cfg_now cfg_rec cfg_run img_run img_local drift=""
  cid="$("${DC[@]}" ps -q "$GATEWAY_SERVICE" 2>/dev/null | head -1)"
  cfg_now="$(sha256sum "$GATEWAY_CONFIG_FILE" 2>/dev/null | awk '{print $1}')"
  if [ -z "$cid" ]; then
    log "gateway 미기동 — up -d $GATEWAY_SERVICE"
    run "${DC[@]}" up -d --no-deps "$GATEWAY_SERVICE" || { err "gateway 기동 실패."; return 1; }
    wait_gateway_healthy "$GATEWAY_SERVICE" "$GATEWAY_READY_TIMEOUT" || return 1
    state_set gateway_config_sha "$cfg_now"
    sweep_leaked_surge   # 리뷰 M-1
    return 0
  fi
  cfg_rec="$(state_get gateway_config_sha)"
  # 실행 중 프로세스가 로드했던 config 는 기록(state) 기준으로, bind inode-stale 은 컨테이너 내부
  # 파일 대조로 각각 판정한다(Caddyfile reconcile 과 동형 — merge 가 inode 를 갈아끼우는 함정).
  cfg_run="$(docker exec "$cid" cat /app/config.yaml 2>/dev/null | sha256sum 2>/dev/null | awk '{print $1}')"
  img_run="$(docker inspect -f '{{.Image}}' "$cid" 2>/dev/null || true)"
  img_local="$(docker image inspect "$(docker inspect -f '{{.Config.Image}}' "$cid" 2>/dev/null)" -f '{{.Id}}' 2>/dev/null || true)"
  if   [ "$FORCE_GATEWAY" -eq 1 ]; then drift="--force-gateway 지정"
  elif [ -n "$cfg_rec" ] && [ "$cfg_rec" != "$cfg_now" ]; then drift="litellm config 변경(기록 ${cfg_rec:0:12}≠현행 ${cfg_now:0:12})"
  elif [ -n "$cfg_run" ] && [ "$cfg_run" != "$cfg_now" ]; then drift="config bind inode-stale(컨테이너≠호스트)"
  elif [ -n "$img_run" ] && [ -n "$img_local" ] && [ "$img_run" != "$img_local" ]; then drift="이미지 태그 갱신(running≠local)"
  fi
  if [ -z "$drift" ]; then
    [ -z "$cfg_rec" ] && state_set gateway_config_sha "$cfg_now"
    sweep_leaked_surge   # 리뷰 M-1: 무드리프트 경로에서도 고아 surge 정리
    log "gateway 드리프트 없음 — 무접촉(blip 0)."
    return 0
  fi
  log "gateway 드리프트 감지: $drift → surge 무중단 교체 시작"
  # 1) surge 기동 + healthy 게이트. 실패 시 본체 무접촉(무중단 보존) — 새 이미지/설정 결함 의심.
  if ! run "${DC_SURGE[@]}" up -d --no-deps "$GATEWAY_SURGE" \
     || ! wait_gateway_healthy "$GATEWAY_SURGE" "$GATEWAY_READY_TIMEOUT"; then
    run "${DC_SURGE[@]}" rm -sf "$GATEWAY_SURGE" || true
    err "surge replica healthy 실패 — 본체 무접촉 유지(기존 gateway 가 계속 서빙). 새 이미지/설정 점검."
    return 1
  fi
  # 1b) **교체 전 후보 검증**(2026-08-26 신설, 적대 리뷰 [P1] 수용): surge 가 healthy 하다고
  #     대화가 되는 것은 아니다 — /health/liveliness 는 프로세스 생존만 본다. 구 gateway 를 지우기
  #     전에 **새 gateway 를 직접 태워** 대화 왕복을 확인한다. 실패하면 교체를 아예 하지 않으므로
  #     구 gateway 가 계속 서빙한다(= 무장애). 종전 설계는 교체·surge 제거 후에야 검사해서
  #     "발견했지만 이미 장애" 였다.
  #     대상 지정은 DNS alias 가 아니라 **surge 서비스명 직접 호출**로 한다(alias 는 본체와 surge 를
  #     함께 가리켜 어느 쪽이 응답했는지 보장할 수 없다).
  if [ "${DEPLOY_WEB_SKIP_CONV_SMOKE:-0}" != "1" ] && [ "$DRY_RUN" -ne 1 ]; then
    local smoke_bin="$REPO_ROOT/bin/smoke-conversation.sh"
    if [ ! -f "$smoke_bin" ]; then
      run "${DC_SURGE[@]}" rm -sf "$GATEWAY_SURGE" || true
      err "대화 스모크 스크립트 없음($smoke_bin) — 후보 검증 불가. 본체 무접촉 유지(구 gateway 서빙). ABORT."
      return 1
    fi
    step "gateway 후보(surge) 대화 스모크 — 통과해야 본체를 교체한다"
    if ! bash "$smoke_bin" --service ask-worker --gateway-url "http://${GATEWAY_SURGE}:8080/v1"; then
      run "${DC_SURGE[@]}" stop "$GATEWAY_SURGE" || true
      run "${DC_SURGE[@]}" rm -f "$GATEWAY_SURGE" || true
      err "후보 gateway 에서 대화가 성립하지 않는다 — **교체하지 않고 중단**한다(구 gateway 가 계속 서빙 = 무장애)."
      err "  새 이미지/설정이 대화 요청 계약을 깼을 가능성이 크다: docker compose logs $GATEWAY_SURGE --tail 80"
      return 1
    fi
    log "후보 gateway 대화 스모크 PASS — 본체 교체를 진행한다."
  fi

  # 2) 본체 recreate — 신규 요청은 DNS alias 로 surge 가 흡수한다. 하지만 **이미 본체 소켓에
  #    붙어 있는 in-flight 호출은 surge 로 옮길 수 없다** — HTTP 요청은 프로세스 간 이전이
  #    불가능하다. 종전엔 그 사실을 stop_grace 타이머로 덮었고(만료 시 SIGKILL), 그게 2026-08-12
  #    사고의 기전이다(구 컨테이너 SIGTERM 11:00:05 → SIGKILL 11:02:05 = 정확히 grace 120s).
  #    그래서 "옮긴다" 가 아니라 **"붙어 있는 게 없을 때 바꾼다"** 로 푼다 — quiesce 게이트가
  #    통과한 시점엔 진행 중 사용자 run 이 0 이므로 recreate 가 아무것도 죽이지 않는다.
  #    (게이트 통과 직후 새 run 이 시작되는 좁은 창은 상향된 stop_grace 가 흡수한다 — 두 층.)
  quiesce_gate "gateway recreate" || {
    err "gateway 교체 중단 — 현 본체가 계속 서빙(무중단 유지). surge 는 아래에서 정리한다."
    run "${DC_SURGE[@]}" stop "$GATEWAY_SURGE" || true
    run "${DC_SURGE[@]}" rm -f "$GATEWAY_SURGE" || true
    return 1
  }
  if ! run "${DC[@]}" up -d --no-deps --force-recreate "$GATEWAY_SERVICE" \
     || ! wait_gateway_healthy "$GATEWAY_SERVICE" "$GATEWAY_READY_TIMEOUT"; then
    err "gateway 본체 recreate 후 비정상 — surge 가 임시 서빙 중(의도적으로 유지). 수동 개입 필요. 주의: surge 는 restart:no 라 호스트 재부팅 시 소멸 — 방치 금지."
    return 1
  fi
  stamp_sanctioned_recreate "$GATEWAY_SERVICE"
  # 3) surge graceful 종료(진행 요청 drain 후 정리).
  run "${DC_SURGE[@]}" stop "$GATEWAY_SURGE" || warn "surge stop 문제 — rm 계속."
  run "${DC_SURGE[@]}" rm -f "$GATEWAY_SURGE" || true
  state_set gateway_config_sha "$cfg_now"
  log "gateway 무중단 교체 완료."
}

# ── asset 스탬프 검증 (ITEM-09 what#3: 빌드 주입 확인 — §13.1 v3.35.1 1순위) ────
# 소스는 ?v=dev placeholder 고정(수기 bump 폐지·병렬 충돌 표면 제거), Dockerfile 의
# inject_asset_stamp.py 가 content-hash 를 주입한다. baked 이미지에 placeholder 가
# 잔존하면 주입 누락 = 배포 후 캐시 무효화 상실이므로 하드 차단(구 asset_stamp_warn 대체).
asset_stamp_verify() {  # $1 = sha
  [ "$DRY_RUN" -eq 1 ] && return 0
  local leaked
  # 검증 범위 = 주입 재작성 대상과 동일(*.html/*.js, vendor/ 제외) — 문서(MAPPING.md 등)의
  # `?v=dev` prose 언급을 잔존으로 오탐하지 않는다(2026-07-12 첫 가동에서 실측된 false-ABORT).
  leaked="$(docker run --rm --entrypoint grep "$IMAGE_REPO:$1" -rl --include='*.html' --include='*.js' '?v=dev' /app/web/static 2>/dev/null | grep -v '/vendor/' | head -5 || true)"
  if [ -n "$leaked" ]; then
    die "정적 자산 ?v= 스탬프 주입 누락 — baked 이미지에 placeholder(?v=dev) 잔존: $(printf '%s' "$leaked" | tr '\n' ' '). Dockerfile 의 inject_asset_stamp.py RUN 확인. ABORT (스탬프 없이 배포하면 캐시 무효화 상실)."
  fi
  log "OK — baked 자산 스탬프 주입 확인(*.html/*.js 내 ?v=dev 잔존 0)."
}

# ── 대화 경로 스모크 (2026-08-26 신설 — healthz/soak 가 못 보는 공백) ─────────
# 왜: 게이트웨이 의존성 갱신으로 요청 조립 계약이 깨져 **모든 대화가 실패**했는데, 배포는 성공했고
#   /healthz 는 ok, soak 도 통과했다. 시스템이 자기 고장을 몰랐고 사용자 신고로만 발견됐다(≈20시간).
#   healthz/soak 는 "프로세스가 살아 있는가" 만 본다 — "대화가 되는가" 는 이 스모크가 본다.
# 이 함수는 **최종 확인**이다. gateway 의존성 결함은 앞단의 **교체 전 후보(surge) 스모크**가
#   이미 막는다(deploy_gateway_reconcile 1b) — 그쪽이 실패하면 교체 자체를 하지 않아 무장애다.
#   여기서 잡히는 것은 web/워커 이미지에서 비롯된 결함처럼 그 뒤에 남는 부류다.
# 판정: 실패면 **배포를 실패로 종결**한다(exit 1). 이미 web/워커는 새 SHA 를 서빙하므로 자동
#   롤백은 하지 않는다 — 사람이 로그를 보고 롤백/수정을 판단하도록 크게 표면화한다(조용한 성공 금지).
#   실패는 `conv_smoke_sha=failed-<sha>` 로 남아 **다음 실행이 no-op 으로 빠지지 않는다**.
# scope=web 은 ask-worker 를 롤아웃하지 않으므로 스킵한다(검증 대상 컨테이너가 이번 배포분이 아님).
conversation_smoke_or_fail() {
  [ "$DRY_RUN" -eq 1 ] && return 0
  if [ "$SCOPE" = "web" ]; then
    # 정직 표기(적대 리뷰 [P2]): 이 경로는 대화 왕복을 **검증하지 않았다**. 완료 문구가 스모크
    # 통과를 함의하지 않도록 상태를 남긴다(web 변경이 HTTP 대화 라우팅을 깼다면 여기서 안 잡힌다).
    state_set conv_smoke_sha "skipped-scope-web"
    warn "대화 스모크 skip — scope=web (ask-worker 미롤아웃). **대화 동작 미검증 상태로 종료된다.**"
    return 0
  fi
  if [ "${DEPLOY_WEB_SKIP_CONV_SMOKE:-0}" = "1" ]; then
    warn "대화 스모크 skip — DEPLOY_WEB_SKIP_CONV_SMOKE=1 (사람이 명시 해제. 대화 동작 미검증 상태로 종료)."
    return 0
  fi
  # 파일 이상은 **배포 결함**이므로 fail-closed(적대 리뷰 [P2]). 실행 비트는 보지 않는다 —
  # `bash "$smoke"` 로 호출하므로 읽기만 되면 되고, WSL/filemode 차이로 게이트가 조용히 빠지는 것을 막는다.
  local smoke="$REPO_ROOT/bin/smoke-conversation.sh"
  if [ ! -f "$smoke" ]; then
    err "대화 스모크 스크립트 없음: $smoke — 게이트를 건너뛰지 않는다(배포 결함으로 본다)."
    exit 1
  fi
  step "대화 경로 스모크 (배포본에서 실제 답변 1회 생성 확인)"
  if bash "$smoke" --service ask-worker; then
    # 적대 리뷰 [P1]: 스모크 성공을 별도로 기록한다. 이게 없으면 스모크 실패 후 같은 SHA 재실행이
    # no-op 분기(current/agent_current 일치)에서 exit 0 으로 **거짓 green** 이 된다.
    state_set conv_smoke_sha "$TARGET_SHA"
    return 0
  fi
  state_set conv_smoke_sha "failed-$TARGET_SHA"
  err "대화 스모크 FAIL — 배포본에서 답변이 생성되지 않는다. web/워커는 $TARGET_SHA 를 서빙 중이며"
  err "  healthz/soak 는 통과했으므로 **자동 감지되지 않는 장애**다(2026-08-26 실사례)."
  err "  조치: docker compose logs bedrock-gateway --tail 80 으로 provider 응답을 먼저 확인하고,"
  err "        원인이 이번 배포분이면 bin/deploy-web.sh 로 직전 last-good SHA 를 재배포한다."
  exit 1
}

# ── 배포 검증 체크리스트 (사용자 인수 전 — RUNBOOK §10) ──────────────────────
# "merge ≠ 배포 완료 / 백엔드 통과 ≠ 사용자 경로 통과" 마찰(2026-07-13
# attach-user-version 회고)을 매 배포마다 상시 표면화한다. output-only —
# 배포 로직·판정에 영향 없음. (워커 재빌드는 feature-0020 부터 스파인이 자동 수행.)
post_deploy_checklist() {
  [ "$DRY_RUN" -eq 1 ] && return 0
  cat >&2 <<'CKL'

=== 배포 검증 체크리스트 (사용자 인수 전 필수 — 상세: feature-0014 RUNBOOK §10) ===
 [1] 배포 완료: web-a·web-b 가 대상 SHA + soak 통과(위 로그). 이 시점 전에는 기능을
     "사용자 테스트 가능"으로 알리지 않는다 (merge ≠ 배포 완료 — 그 사이 창은 구코드).
 [2] 워커 롤아웃: 위 '워커 롤아웃 완료' 로그 확인(스파인이 자동 수행 — feature-0020).
     '--web-only' 로 돌렸다면 워커 코드 변경 여부를 판단해 전체 스코프로 재실행한다.
     ⚠ '부분 완료' 로 끝났다면 그것은 배포가 아니다 — 미도달 서비스가 로그에 나열된다.
       docker compose -f docker-compose.yml ps --format '{{.Service}}\t{{.Image}}'
     서비스별 이미지 태그가 모두 같은 SHA 인지 눈으로 확인한다(state 파일이 아니라 실물).
 [1b] 대화 스모크: 위 '대화 경로 스모크' PASS 로그 확인(2026-08-26 신설). 이 게이트가 없던
     시절, 게이트웨이 의존성 갱신으로 모든 대화가 죽었는데 healthz/soak 는 전부 green 이었고
     사용자 신고까지 약 20시간이 걸렸다. FAIL 이면 배포는 exit 1 로 끝난다(조용한 성공 없음).
 [2b] surge 잔존 확인(feature-0020 zd-ask-rollout): 교체가 끝나면 surge 는 없어야 한다.
       docker compose -f docker-compose.yml --profile deploy-surge ps -q ask-worker-surge
     비어 있지 않으면 정리에 실패한 것 — 그 컨테이너가 큐에서 계속 job 을 가져간다(조용하다).
     다음 배포의 leaked sweep 이 정리하지만, 그때까지 두 인스턴스가 함께 도는 상태다.
 [3] 캐시 무효화: 서빙 HTML 의 ?v= 스탬프가 바뀌었는가(위 asset 스탬프 OK). 사용자에게
     하드 리프레시(Ctrl+F5) 안내 — stale JS 로 구 동작이 관측되는 것을 방지.
 [4] 실 사용자 표면 검증: 백엔드 API 뿐 아니라 사용자가 실제 쓰는 경로(UI 업로드/클릭 등)를
     라이브 배포본에서 PB-0008 로 검증한다 (백엔드 fetch 만 타면 client-only 결함을 놓친다).
 [5] 무중단 실측(2026-08-11 신설): 이번 배포 창에 엣지가 실제로 무중단이었는지 확인한다.
     배포 스크립트의 soak 는 blip 을 관용하므로 "성공 보고 = 무중단" 이 아니다.
       docker compose -f docker-compose.yml logs caddy --since 10m \
         | grep -c 'no upstreams available'      # 기대 0
     0 이 아니면 롤링이 엣지 후보 복귀보다 빨랐다는 뜻 — 사용자에게는 그 시간만큼 전면 503
     이었다. bin/deploy-web.sh 의 wait_edge_available 로그와 Caddyfile 의 fail_duration 을
     함께 확인한다.
 [6] 완료 보고: [1]~[5] 통과 후에만 "배포·검증 완료"를 사용자에게 보고한다.
================================================================================
CKL
}

# ── 메인 흐름 ─────────────────────────────────────────────────────────────────
main() {
  preflight_privilege
  exec 9>"$LOCK_FILE"
  step "flock 획득 (전체 배포 직렬화, -w ${LOCK_WAIT_SECONDS}s)"
  if ! flock -w "$LOCK_WAIT_SECONDS" 9; then
    die "flock timeout(${LOCK_WAIT_SECONDS}s) — 다른 배포가 진행 중. (loser 비-0 종료 — coalesce 로 winner 가 origin/main HEAD 를 배포하므로 본 커밋이 이미 포함됐다면 안전)"
  fi
  # feature-0045: 드레인 누수 차단. `predrain` 은 이제 최대 180s 를 기다리므로 그 사이 중단될
  # 창이 넓다. EXIT 은 정상 종료도 타지만 `DRAINED_SVC` 는 recreate 성공 시 비워지므로 no-op 다.
  trap 'on_exit_cleanup' EXIT
  trap 'err "중단 신호 — 드레인 회수 후 종료한다."; exit 130' INT TERM

  if [ "$MODE" = "rollback" ]; then
    resolve_target_sha
    local good; good="$(lastgood_sha)"
    [ -n "$good" ] || die "last-good 없음 — 롤백 대상 불명."
    docker image inspect "$IMAGE_REPO:last-good" >/dev/null 2>&1 || die "last-good 이미지($IMAGE_REPO:last-good) 없음."
    write_pin_overlay "$IMAGE_REPO:last-good" ""; set_dc_prod
    preflight_fileset; preflight_tls
    local svc; for svc in "${REPLICAS[@]}"; do recreate_replica "$svc" "$good" || die "$svc 롤백 실패."; done
    # 하드닝(2026-07-11): recreate 직후 단발 프로브는 워밍업 창 오판 — auto_rollback 과 동일 60s 회복 대기.
    local rb_deadline=$(( SECONDS + 60 )) rb_ok=1
    while [ "$SECONDS" -lt "$rb_deadline" ]; do
      if edge_ok; then rb_ok=0; break; fi
      sleep 3
    done
    [ "$rb_ok" -eq 0 ] && log "롤백 완료 + edge 정상 ($good)." || die "롤백했으나 edge 비정상(60s 대기 후)."
    state_set current "$good"
    # feature-0020: 워커도 last-good 이 있으면 함께 롤백(web/워커 버전 정합).
    if [ "$SCOPE" != "web" ] && [ -n "$(agent_lastgood_sha)" ]; then
      rollback_workers "$IMAGE_REPO:last-good" || warn "워커 롤백 부분 실패 — 수동 확인."
    fi
    normalize_ownership; exit 0
  fi

  resolve_target_sha
  # coalesce no-op: 이미 배포된 것이 origin/main HEAD 면 재배포 불필요(멱등).
  local web_current agent_current conv_smoke
  web_current="$(current_deployed_sha)"; agent_current="$(state_get agent_current)"
  conv_smoke="$(state_get conv_smoke_sha)"
  # 적대 리뷰 [P1](2026-08-26): no-op 판정에 **대화 스모크 통과 여부**를 포함한다. 종전엔
  # current/agent_current 만 봐서, 스모크가 실패한 SHA 를 재실행하면 여기서 exit 0 이 나
  # "재시도하니 green" 이라는 거짓 신호가 됐다(결함은 그대로인데 배포는 성공으로 보임).
  if [ "$SCOPE" != "web" ] && [ "$conv_smoke" != "$TARGET_SHA" ] \
     && { [ "$web_current" = "$TARGET_SHA" ] || [ "$agent_current" = "$TARGET_SHA" ]; }; then
    log "이미 $TARGET_SHA 가 배포돼 있으나 **대화 스모크 미통과**(기록=${conv_smoke:-없음}) → no-op 하지 않고 검증까지 진행한다."
  elif [ "$FORCE_GATEWAY" -eq 0 ] && edge_ok; then
    case "$SCOPE" in
      all)     if [ "$web_current" = "$TARGET_SHA" ] && [ "$agent_current" = "$TARGET_SHA" ]; then
                 log "이미 web+워커 $TARGET_SHA 배포됨 + edge 정상 → no-op (멱등). (gateway/caddy 의 이미지-only 드리프트(re-pull)는 no-op 에서 미검사 — 필요 시 --force-gateway 또는 커밋 동반 배포.)"; normalize_ownership; exit 0; fi ;;
      web)     if [ "$web_current" = "$TARGET_SHA" ]; then
                 log "이미 web $TARGET_SHA 배포됨 + edge 정상 → no-op (멱등)."; normalize_ownership; exit 0; fi ;;
      workers) if [ "$agent_current" = "$TARGET_SHA" ]; then
                 log "이미 워커 $TARGET_SHA 배포됨 → no-op (멱등)."; normalize_ownership; exit 0; fi ;;
    esac
  fi

  preflight_fileset
  preflight_tls

  # pin overlay 는 모든 DC_PROD 사용의 전제 — 먼저 기록. (--workers-only 는 web 을 현행
  # 안정 태그로 핀: web 은 미접촉이라 inert, overlay 정합만 유지.)
  local web_img="$IMAGE_REPO:$TARGET_SHA"
  if [ "$SCOPE" = "workers" ] && docker image inspect "$IMAGE_REPO:current" >/dev/null 2>&1; then
    web_img="$IMAGE_REPO:current"
  fi
  write_pin_overlay "$web_img" "$AGENT_IMAGE_REPO:$TARGET_SHA"
  set_dc_prod

  # feature-0045: **web_skip 판정보다 먼저** 잔존 드레인을 청소한다. 직전 배포가 중단되며
  # 남긴 lame-duck 은 `/readyz` 200 · `/healthz` 200 · `container_health=healthy` 라 어느
  # 신호에도 안 잡히고, 같은 sha 재배포는 `web_skip=1` 로 롤링을 통째로 건너뛴다 — 그러면
  # 그 replica 는 **다음 새 sha 가 나올 때까지 무기한 LB 밖**이다(실질 용량 절반, 무증상).
  clear_stale_drain

  # web 이 이미 대상 SHA + 양 replica ready 면 web 단계 skip(인터럽트된 배포 재개 멱등성).
  local web_skip=0
  if [ "$SCOPE" = "workers" ]; then
    web_skip=1
  elif [ "$web_current" = "$TARGET_SHA" ] && [ "$DRY_RUN" -ne 1 ]; then
    local _ra _rb
    _ra="$(replica_readyz web-a 2>/dev/null | awk '{print $2}' || true)"
    _rb="$(replica_readyz web-b 2>/dev/null | awk '{print $2}' || true)"
    if [ "$_ra" = "$TARGET_SHA" ] && [ "$_rb" = "$TARGET_SHA" ]; then
      web_skip=1; log "web 이미 $TARGET_SHA + 양 replica ready — web 단계(빌드/마이그/롤링/soak) skip."
    fi
  fi

  if [ "$web_skip" -eq 0 ]; then
    # feature-0014-migrate-fresh-image: build 를 migrate 앞으로. migrate_phase 가 방금 빌드한
    # mysql-ai-web:<sha>(신규 마이그레이션 파일 포함)로 alembic 을 돌리게 한다. 과거엔 migrate 가
    # build 전에 실행돼 `docker compose run agent`(stale 이미지)로 head 를 오판, 신규 마이그를
    # 조용히 놓쳤다. build 는 swap(recreate) 전 단계라 이 순서에서도 expand-before-swap 불변 유지
    # (build→migrate→recreate). build 후 migrate 실패 시에도 last-good=이전본 유지(rollback 정합).
    build_image "$TARGET_SHA"
    # 워커 이미지도 swap 전 선빌드(fail-fast — agent 빌드 실패 시 어떤 컨테이너도 무접촉).
    [ "$SCOPE" = "web" ] || build_agent_image "$TARGET_SHA"
    migrate_phase
    asset_stamp_verify "$TARGET_SHA"

    step "one-at-a-time 롤링 (항상 ≥1 healthy upstream)"
    # 첫 배포(둘 다 없음)면 둘 다 올림. 아니면 하나씩.
    # ⚠ **조회 실패와 "정말 없음" 을 구분한다** — 둘을 빈 문자열로 합치면 일시적 compose 조회
    # 실패가 "초기 배포" 로 오인되어 **양 replica 를 동시에 recreate** 한다(= 전면 다운).
    # `if` 조건 안이라 set -e 도 막아주지 않는다(적대 검증 P1, 4R).
    _cid_a="$(replica_cid web-a)" || die "web-a 컨테이너 조회 실패 — 상태 불명으로 롤링을 시작하지 않는다(동시 recreate 위험). docker/compose 상태 확인 후 재실행."
    _cid_b="$(replica_cid web-b)" || die "web-b 컨테이너 조회 실패 — 상태 불명으로 롤링을 시작하지 않는다(동시 recreate 위험). docker/compose 상태 확인 후 재실행."
    if [ -z "$_cid_a" ] && [ -z "$_cid_b" ]; then
      log "초기 배포 — web-a, web-b 동시 기동."
      run "${DC_PROD[@]}" up -d --no-deps --no-build web-a web-b || die "초기 web 기동 실패."
      wait_ready web-a "$TARGET_SHA" || die "web-a 초기 ready 실패."
      wait_ready web-b "$TARGET_SHA" || die "web-b 초기 ready 실패."
    else
      # predrain 은 fail-closed 게이트다(상대가 엣지 후보로 복귀했는가) — 실패 시 어떤 replica 도
      # 내리지 않고 중단한다. 현 상태(구버전 2 replica)가 그대로 서빙되므로 사용자 영향 0.
      predrain web-a web-b || die "web-a 를 내릴 수 없다(상대 web-b 가 엣지 후보 아님) — 배포 중단, 현 상태 유지."
      # feature-0045: recreate 가 실패하면 **구 프로세스가 드레인된 채로 살아남는다**(문이 닫힌
      # replica). 그대로 두면 다음 배포가 상대를 내리는 순간 available upstream 이 0 이 된다.
      recreate_replica web-a "$TARGET_SHA" || { replica_release_drain web-a; die "web-a 배포 실패 — web-b(OLD) 가 계속 서빙 중. 수동 확인."; }
      predrain web-b web-a || die "web-b 를 내릴 수 없다(상대 web-a 가 엣지 후보 아님) — 배포 중단. web-a 는 이미 $TARGET_SHA, web-b 는 구버전으로 **혼합 서빙 중**(expand/contract 로 안전, CONVENTIONS §12). 원인 해결 후 재실행(멱등)."
      recreate_replica web-b "$TARGET_SHA" || { replica_release_drain web-b; err "web-b 배포 실패 — web-a(NEW) 가 서빙 중. web-b 만 롤백/재시도 권장."; auto_rollback "$TARGET_SHA"; exit 1; }
    fi

    state_set current "$TARGET_SHA"
    rollout_mcp_phase
    reconcile_caddy   # feature-0016: Caddyfile 변경 시에만 caddy recreate(inode-stale 대응) + 0020: 이미지 드리프트
    soak_or_rollback "$TARGET_SHA" || exit 1
    # feature-0045: web 롤링이 끝난 지점 = 브리지 축 손상이 확정되는 지점. 배포 꼬리까지
    # 미루면 이후 단계(워커·gateway·스모크)가 실패했을 때 끊긴 작업이 회수되지 않는다.
    reclaim_bridge_claims
  else
    if [ "$SCOPE" != "web" ]; then
      build_agent_image "$TARGET_SHA"
      # 리뷰 M-5: workers-only/재개 경로도 pending 마이그레이션을 놓치지 않도록 agent 이미지로
      # migrate 게이트+적용. expand 는 구 web 코드에도 안전(CONVENTIONS §12 전제)이라 적용이 옳다.
      migrate_phase "$AGENT_IMAGE_REPO:$TARGET_SHA"
    fi
    rollout_mcp_phase
    reconcile_caddy
  fi

  # feature-0020: 워커 + gateway 롤아웃 (web soak 통과 후 — 사용자 대면 경로 안정 확인 뒤 백그라운드 층).
  if [ "$SCOPE" != "web" ]; then
    deploy_workers "$TARGET_SHA" "$web_img" \
      || { err "워커 롤아웃 실패 — web 은 $TARGET_SHA 서빙 중(부분 완료, 혼합 버전은 expand/contract 로 안전). 원인 해결 후 재실행(멱등)."; exit 1; }
    deploy_gateway_reconcile \
      || { err "gateway reconcile 실패 — web/워커는 $TARGET_SHA 서빙 중(부분 완료). 위 로그로 수동 확인."; exit 1; }
  fi

  normalize_ownership
  conversation_smoke_or_fail
  step "배포 완료: $TARGET_SHA (scope=$SCOPE — web 롤링·워커·gateway reconcile + soak + 대화 스모크 통과)"
  quiesce_summary
  bridge_continuity_summary
  post_deploy_checklist
}

main "$@"
