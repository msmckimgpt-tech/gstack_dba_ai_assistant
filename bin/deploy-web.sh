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
#  - post-cutover soak(RestartCount/edge 감시) + 자동 롤백; bad-image vs dependency-down 구분
#  - web 롤링 자체는 web-a/web-b 만 지정(--no-deps). 워커 롤아웃은 soak 통과 후
#    별도 phase 에서 수행(feature-0020 — 구 "worker 미접촉 + WARN-only" 를 대체)
#
# Usage:
#   sudo -E bin/deploy-web.sh                 # origin/main HEAD 로 전체 롤아웃(web+워커+gateway)
#   sudo -E bin/deploy-web.sh --web-only      # web(+caddy reconcile)만 — 기존 feature-0014 범위
#   sudo -E bin/deploy-web.sh --workers-only  # 워커+gateway 만 (마이그 없는 워커 코드/설정 변경 전용)
#   sudo -E bin/deploy-web.sh --force-gateway # gateway 드리프트 무관 surge 교체 강제
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
PREDRAIN_TIMEOUT="${DEPLOY_WEB_PREDRAIN_TIMEOUT:-90}"
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
WORKERS=(insight-worker ask-worker ops-scheduler)
AGENT_LASTGOOD_FILE="$STATE_DIR/deploy-agent.last-good"
WORKER_READY_TIMEOUT="${DEPLOY_WORKER_READY_TIMEOUT:-300}"    # insight 최악 unhealthy 확정(start 60s+60s×3=240s)보다 여유(리뷰 m-3 — 경계 동률 false-fail 방지)
GATEWAY_READY_TIMEOUT="${DEPLOY_GATEWAY_READY_TIMEOUT:-180}"
GATEWAY_SERVICE="bedrock-gateway"
GATEWAY_SURGE="bedrock-gateway-surge"
GATEWAY_CONFIG_FILE="unit/feature-0007-bedrock-llm-provider/src/config/litellm_config.yaml"

DRY_RUN=0
MODE="deploy"   # deploy | rollback
SCOPE="all"     # all | web | workers (feature-0020)
FORCE_GATEWAY=0

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

usage() { sed -n '2,48p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --rollback)      MODE="rollback"; shift ;;
    --dry-run)       DRY_RUN=1; shift ;;
    --web-only)      SCOPE="web"; shift ;;
    --workers-only)  SCOPE="workers"; shift ;;
    --force-gateway) FORCE_GATEWAY=1; shift ;;
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
    local host_ca caddy_ca
    host_ca="$(sha256sum "$ROOT_CA" 2>/dev/null | awk '{print $1}')"
    caddy_ca="$("${DC[@]}" exec -T caddy cat /certs/rootCA.pem 2>/dev/null | sha256sum 2>/dev/null | awk '{print $1}' || true)"
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
      local w; for w in "${WORKERS[@]}"; do printf '  %s:\n    image: %s\n' "$w" "$agent_img"; done
    fi
  } > "$PIN_FILE"
}

DC_PROD=()  # base + pin overlay
set_dc_prod() { DC_PROD=(docker compose -f docker-compose.yml -f "$PIN_FILE"); }

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
  # 대상의 진행 중 SSE/CSV 스트림이 끝날 때까지 대기(fetch/getReader 는 자동재접속 없음).
  while [ "$SECONDS" -lt "$deadline" ]; do
    n="$(replica_active_streams "$target")"
    [ "${n:-0}" -eq 0 ] 2>/dev/null && { log "  $target active_streams=0 — recreate 진행"; return 0; }
    log "  $target active_streams=$n — 종료 대기"
    sleep 3
  done
  warn "$target pre-drain timeout(${PREDRAIN_TIMEOUT}s) — 진행 스트림이 남았지만 계속 진행(해당 스트림은 끊김)."
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
  wait_ready "$svc" "$want" || { err "$svc 가 ${READY_TIMEOUT}s 내 ready+correct-commit 실패."; return 1; }
  # 선제 대기(비차단). 앱 ready 와 엣지 후보 복귀는 다른 층이라 여기서 미리 기다려 두면 다음
  # predrain 이 즉시 통과한다. **여기서 실패해도 배포를 끊지 않는다** — 이 replica 는 이미 올라와
  # 있고, 위험한 것은 "다음 replica 를 내리는 것" 이라 그 판단은 predrain 이 fail-closed 로 한다
  # (롤백 경로도 이 함수를 타므로 여기서 끊으면 롤백이 중단된다).
  wait_edge_available "$svc" || warn "$svc 엣지 복귀 미확인 — 다음 replica 를 내리기 전 predrain 이 재확인한다."
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
        err "$svc 상태=$st — 기동 실패."; return 1 ;;
    esac
    sleep 5
  done
  err "$svc 가 ${2}s 내 healthy 도달 실패(최종 상태=$(container_health "$svc"))."
  return 1
}

deploy_workers() {  # $1 = 대상 sha, $2 = pin overlay 의 web image ref(롤백 시 유지) → 0 성공.
  local sha="$1" web_img="$2" svc st got
  step "워커 롤아웃 (${WORKERS[*]} — one-at-a-time, graceful stop_grace 존중)"
  for svc in "${WORKERS[@]}"; do
    # 멱등 skip: 이미 대상 sha + healthy 면 무접촉(인터럽트된 배포 재개 지원).
    if [ "$DRY_RUN" -ne 1 ]; then
      st="$(container_health "$svc")"; got="$(worker_commit "$svc")"
      if [ "$st" = "healthy" ] && [ "$got" = "$sha" ]; then
        log "$svc 이미 $sha + healthy — skip(멱등)."; continue
      fi
    fi
    log "recreate $svc → $AGENT_IMAGE_REPO:$sha"
    if ! run "${DC_PROD[@]}" up -d --no-deps --no-build --force-recreate "$svc" \
       || ! wait_worker_healthy "$svc" "$WORKER_READY_TIMEOUT" "$sha"; then
      err "$svc 롤아웃 실패 — 워커군 last-good 롤백 시도. (web 은 기존 서빙 유지 — expand/contract 게이트가 혼합 버전 안전을 보장. CONVENTIONS §12)"
      rollback_workers "$web_img"
      return 1
    fi
  done
  state_set agent_current "$sha"
  log "워커 롤아웃 완료 — ${WORKERS[*]} = $AGENT_IMAGE_REPO:$sha"
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

deploy_gateway_reconcile() {
  step "bedrock-gateway reconcile (드리프트 시에만 surge 무중단 교체)"
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
  # 2) 본체 recreate — 신규 요청은 DNS alias 로 surge 가 흡수, in-flight 는 stop_grace drain.
  if ! run "${DC[@]}" up -d --no-deps --force-recreate "$GATEWAY_SERVICE" \
     || ! wait_gateway_healthy "$GATEWAY_SERVICE" "$GATEWAY_READY_TIMEOUT"; then
    err "gateway 본체 recreate 후 비정상 — surge 가 임시 서빙 중(의도적으로 유지). 수동 개입 필요. 주의: surge 는 restart:no 라 호스트 재부팅 시 소멸 — 방치 금지."
    return 1
  fi
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
  trap 'normalize_ownership' EXIT

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
  local web_current agent_current
  web_current="$(current_deployed_sha)"; agent_current="$(state_get agent_current)"
  if [ "$FORCE_GATEWAY" -eq 0 ] && edge_ok; then
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
      recreate_replica web-a "$TARGET_SHA" || die "web-a 배포 실패 — web-b(OLD) 가 계속 서빙 중. 수동 확인."
      predrain web-b web-a || die "web-b 를 내릴 수 없다(상대 web-a 가 엣지 후보 아님) — 배포 중단. web-a 는 이미 $TARGET_SHA, web-b 는 구버전으로 **혼합 서빙 중**(expand/contract 로 안전, CONVENTIONS §12). 원인 해결 후 재실행(멱등)."
      recreate_replica web-b "$TARGET_SHA" || { err "web-b 배포 실패 — web-a(NEW) 가 서빙 중. web-b 만 롤백/재시도 권장."; auto_rollback "$TARGET_SHA"; exit 1; }
    fi

    state_set current "$TARGET_SHA"
    reconcile_caddy   # feature-0016: Caddyfile 변경 시에만 caddy recreate(inode-stale 대응) + 0020: 이미지 드리프트
    soak_or_rollback "$TARGET_SHA" || exit 1
  else
    if [ "$SCOPE" != "web" ]; then
      build_agent_image "$TARGET_SHA"
      # 리뷰 M-5: workers-only/재개 경로도 pending 마이그레이션을 놓치지 않도록 agent 이미지로
      # migrate 게이트+적용. expand 는 구 web 코드에도 안전(CONVENTIONS §12 전제)이라 적용이 옳다.
      migrate_phase "$AGENT_IMAGE_REPO:$TARGET_SHA"
    fi
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
  step "배포 완료: $TARGET_SHA (scope=$SCOPE — web 롤링·워커·gateway reconcile + soak 통과)"
  post_deploy_checklist
}

main "$@"
