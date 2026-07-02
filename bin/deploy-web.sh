#!/usr/bin/env bash
# =============================================================================
# deploy-web.sh — feature-0014: web 무중단(zero-downtime) 롤링 배포 스파인.
#
# Caddy LB(web-a:8000 web-b:8000) 뒤에서 web replica 를 한 번에 하나씩 재시작해
# 항상 ≥1 healthy upstream 을 유지한다. 고병렬 자동배포(deploy_scope: included)에서
# 무인 실행되도록 직렬화·검증·자동 롤백을 모두 포함한다.
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
#  - worker(insight/ask) 미접촉 단언(--no-deps, web-a/web-b 만 지정)
#
# Usage:
#   sudo -E bin/deploy-web.sh                 # origin/main HEAD 로 롤링 배포
#   sudo -E bin/deploy-web.sh --rollback      # last-good 이미지로 롤백
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
IMAGE_KEEP="${DEPLOY_WEB_IMAGE_KEEP:-3}"

DRY_RUN=0
MODE="deploy"   # deploy | rollback

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

usage() { sed -n '2,55p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --rollback) MODE="rollback"; shift ;;
    --dry-run)  DRY_RUN=1; shift ;;
    --help|-h)  usage 0 ;;
    *) die2 "알 수 없는 인자: $1" ;;
  esac
done

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
  local cfg
  cfg="$("${DC[@]}" config 2>/dev/null)" || die "docker compose config 실패 (base file-set)."
  # web-a/web-b 섹션에 published 포트가 있으면 --scale/replica 충돌 → 차단.
  local web_block
  web_block="$(printf '%s\n' "$cfg" | awk '/^  web-[ab]:/{f=1} /^  [a-z]/&&!/web-[ab]/{if(f&&!/^  web-[ab]/)f=0} f{print}')"
  if printf '%s\n' "$web_block" | grep -qE 'published:'; then
    die "web-a/web-b 에 호스트 포트(published)가 있습니다. 프로덕션은 Caddy :443 단일 진입이어야 합니다 (dev override 가 머지되었는지 확인). :18080 직접 문은 폐기되었습니다."
  fi
  printf '%s\n' "$cfg" | grep -qE '^  web-a:' && printf '%s\n' "$cfg" | grep -qE '^  web-b:' \
    || die "web-a/web-b 서비스가 base compose 에 없습니다 (토폴로지 미적용)."
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
  if "${DC[@]}" ps caddy >/dev/null 2>&1; then
    local host_ca caddy_ca
    host_ca="$(sha256sum "$ROOT_CA" 2>/dev/null | awk '{print $1}')"
    caddy_ca="$("${DC[@]}" exec -T caddy cat /certs/rootCA.pem 2>/dev/null | sha256sum 2>/dev/null | awk '{print $1}')"
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

# ── migrate 게이트 + 적용 (expand 먼저, swap 전) ───────────────────────────────
migrate_phase() {
  step "마이그레이션: expand/contract 게이트 + 적용 (swap 전)"
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
    _mig_env=(env "MIGRATE_ALEMBIC_IMAGE=$IMAGE_REPO:$TARGET_SHA")
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
write_pin_overlay() {  # $1 = sha, $2 = image ref (default $IMAGE_REPO:$sha; rollback 은 :last-good 태그)
  local sha="$1" img="${2:-$IMAGE_REPO:$sha}"
  if [ "$DRY_RUN" -eq 1 ]; then log "[dry-run] write pin overlay → $img"; return 0; fi
  cat > "$PIN_FILE" <<YAML
# feature-0014 deploy-web.sh 자동 생성 — web-a/web-b 를 빌드 결과 이미지에 핀(롤백 즉시성).
services:
  web-a:
    image: ${img}
  web-b:
    image: ${img}
YAML
}

DC_PROD=()  # base + pin overlay
set_dc_prod() { DC_PROD=(docker compose -f docker-compose.yml -f "$PIN_FILE"); }

build_image() {  # $1 = sha
  local sha="$1"
  step "이미지 빌드 (build-once, GIT_COMMIT=$sha → $IMAGE_REPO:$sha)"
  write_pin_overlay "$sha"
  set_dc_prod
  # last-good 회전: 현재 :current 를 last-good 로 보존(빌드/스왑 성공 전에).
  local cur; cur="$(current_deployed_sha)"
  if [ -n "$cur" ]; then
    run bash -c "echo '$cur' > '$LASTGOOD_FILE'"; log "last-good = $cur"
    # :current → :last-good 태그 회전. sha 태그가 keep-N prune 으로 지워져도 last-good 이미지는
    # 이 안정 태그로 보존되어 롤백이 항상 가능(백엔드 리뷰 note).
    if [ "$DRY_RUN" -ne 1 ] && docker image inspect "$IMAGE_REPO:current" >/dev/null 2>&1; then
      docker tag "$IMAGE_REPO:current" "$IMAGE_REPO:last-good" || true
    fi
  fi
  # web-a 만 빌드하면 image:$sha 로 태깅됨 → web-b 가 동일 이미지 재사용(build-once).
  # feature-0017: build 게이트는 exit code 만 신뢰하지 않는다(snap-docker 의 metadata-file race —
  # docker 29.3.1/compose v5.1.1/buildx v0.31.1 가 `naming...done` 후 /tmp metadata 파일을 confinement
  # 다른 mount ns 에서 못 찾아 EXIT 1 을 반환하나 이미지는 정상 산출·태깅됨, dc-build 동일 우회).
  # 판정: 이미지 존재 + GIT_COMMIT 라벨==sha 로 정합 확인. EXIT≠0 은 **로그에 metadata-file race 마커가
  # 있을 때만** 양성 무시 — 진짜 빌드 실패(컴파일 에러 등, 마커 없음/이미지 부재)는 여전히 ABORT.
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] build web-a (GIT_COMMIT=$sha)"
  else
    local _blog _brc
    _blog="$(mktemp)"
    set +e +o pipefail
    GIT_COMMIT="$sha" "${DC_PROD[@]}" build web-a 2>&1 | tee "$_blog"
    _brc=${PIPESTATUS[0]}
    set -e -o pipefail
    local _img_commit
    _img_commit="$(docker image inspect "$IMAGE_REPO:$sha" --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | sed -n 's/^GIT_COMMIT=//p' | head -1)"
    if [ "$_brc" -eq 0 ] && [ "$_img_commit" = "$sha" ]; then
      :  # 정상 빌드
    elif [ "$_brc" -ne 0 ] && [ "$_img_commit" = "$sha" ] && \
         grep -qiE 'compose-build-metadataFile|metadataFile.*no such file|metadata file.*no such file' "$_blog"; then
      warn "compose build EXIT=$_brc 이나 이미지($IMAGE_REPO:$sha, GIT_COMMIT 일치) 정상 산출 — snap-docker metadata-file race 양성 무시(dc-build 동일 우회)."
    else
      log "--- build log tail ---"; tail -15 "$_blog" >&2; rm -f "$_blog"
      die "이미지 빌드 실패 — $IMAGE_REPO:$sha 부재 또는 GIT_COMMIT('$_img_commit')≠$sha (EXIT=$_brc, metadata-race 마커 없음). 진짜 빌드 실패 — ABORT."
    fi
    rm -f "$_blog"
  fi
  # 새 이미지를 안정 태그 :current 로 (다음 배포가 :last-good 로 회전).
  if [ "$DRY_RUN" -ne 1 ]; then docker tag "$IMAGE_REPO:$sha" "$IMAGE_REPO:current" || true; fi
  # keep-N prune (오래된 SHA 태그 정리)
  if [ "$DRY_RUN" -ne 1 ]; then
    docker images "$IMAGE_REPO" --format '{{.Tag}} {{.ID}}' 2>/dev/null \
      | grep -vE '^(current|last-good) ' | awk '{print $1}' | tail -n +"$((IMAGE_KEEP+1))" \
      | while read -r t; do [ -n "$t" ] && docker rmi "$IMAGE_REPO:$t" 2>/dev/null || true; done
  fi
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

predrain() {  # $1 = recreate 대상 svc, $2 = 상대(살아있어야 함) svc
  local target="$1" other="$2" deadline=$(( SECONDS + PREDRAIN_TIMEOUT )) n
  step "pre-drain: $other 건강 확인 + $target 진행 스트림 종료 대기"
  # 상대 replica 가 살아있어야 무중단. (초기 배포로 상대가 아직 없으면 skip.)
  if replica_cid "$other" >/dev/null 2>&1 && [ -n "$(replica_cid "$other")" ]; then
    replica_readyz "$other" >/dev/null 2>&1 || warn "$other 가 ready 아님 — $target recreate 시 순간 단일 upstream 위험."
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

recreate_replica() {  # $1 = svc, $2 = expected sha
  local svc="$1" want="$2"
  step "recreate $svc → $want (one-at-a-time)"
  run "${DC_PROD[@]}" up -d --no-deps --no-build --force-recreate "$svc" || return 1
  wait_ready "$svc" "$want" || { err "$svc 가 ${READY_TIMEOUT}s 내 ready+correct-commit 실패."; return 1; }
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
    log "Caddyfile 무변경(sha 일치) — caddy 유지(blip 0)"; return 0
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
  step "post-cutover soak (${SOAK_SECONDS}s) — edge + RestartCount 감시"
  base_a="$(restart_count web-a)"; base_b="$(restart_count web-b)"
  while [ "$SECONDS" -lt "$deadline" ]; do
    if ! edge_ok; then
      # edge 503/실패 — 의존성(DB) 문제인지 이미지 문제인지 구분(thrash 방지).
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
  write_pin_overlay "$good" "$IMAGE_REPO:last-good"; set_dc_prod
  local svc; for svc in "${REPLICAS[@]}"; do
    recreate_replica "$svc" "$good" || warn "$svc 롤백 recreate 문제 — 계속."
  done
  edge_ok && log "롤백 후 edge 정상." || err "롤백 후에도 edge 비정상 — 수동 개입 필요."
  echo "current=$good" > "$STATE_FILE"
}

# ── worker GIT_COMMIT divergence (web vs insight/ask) WARN — 자동수정 안 함 ──────
worker_divergence_warn() {
  [ "$DRY_RUN" -eq 1 ] && return 0
  local wsha isha asha
  wsha="$(replica_readyz web-a 2>/dev/null | awk '{print $2}' || true)"
  isha="$("${DC_PROD[@]}" exec -T insight-worker printenv GIT_COMMIT 2>/dev/null | tr -d '[:space:]' || true)"
  asha="$("${DC_PROD[@]}" exec -T ask-worker printenv GIT_COMMIT 2>/dev/null | tr -d '[:space:]' || true)"
  [ -n "$isha" ] && [ "$isha" != "$wsha" ] && warn "insight-worker GIT_COMMIT($isha) != web($wsha) — quiet-time 에 worker 재빌드 권장(insight-worker 는 SIGTERM 핸들러 없음 → idle 시 recreate)."
  [ -n "$asha" ] && [ "$asha" != "$wsha" ] && warn "ask-worker GIT_COMMIT($asha) != web($wsha) — quiet-time 재빌드 권장(ask-worker grace 70s, 안전)."
  return 0
}

# ── asset 스탬프 WARN (스큐 mitigation 아님 — sticky LB 가 담당) ─────────────────
asset_stamp_warn() {
  [ "$DRY_RUN" -eq 1 ] && return 0
  local changed
  changed="$(git diff --name-only "$BASE_BRANCH"...HEAD -- 'unit/feature-0003-agent-web-ui/src/static/*.js' 'unit/feature-0003-agent-web-ui/src/static/*.css' 2>/dev/null || true)"
  if [ -n "$changed" ]; then
    git diff "$BASE_BRANCH"...HEAD -- 'unit/feature-0003-agent-web-ui/src/static/*.html' 2>/dev/null | grep -q '?v=' \
      || warn "정적 자산이 바뀌었으나 HTML 의 ?v= 스탬프 변경이 안 보임. (스큐 자체는 Caddy sticky cookie LB 가 차단하지만, 캐시 강제무효화에는 스탬프 갱신 권장.)"
  fi
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
    write_pin_overlay "$good" "$IMAGE_REPO:last-good"; set_dc_prod
    preflight_fileset; preflight_tls
    local svc; for svc in "${REPLICAS[@]}"; do recreate_replica "$svc" "$good" || die "$svc 롤백 실패."; done
    edge_ok && log "롤백 완료 + edge 정상 ($good)." || die "롤백했으나 edge 비정상."
    echo "current=$good" > "$STATE_FILE"; normalize_ownership; exit 0
  fi

  resolve_target_sha
  # coalesce no-op: 이미 배포된 것이 origin/main HEAD 면 재배포 불필요(멱등).
  if [ "$(current_deployed_sha)" = "$TARGET_SHA" ] && edge_ok; then
    log "이미 $TARGET_SHA 배포됨 + edge 정상 → no-op (멱등)."; normalize_ownership; exit 0
  fi

  preflight_fileset
  preflight_tls
  # feature-0014-migrate-fresh-image: build 를 migrate 앞으로. migrate_phase 가 방금 빌드한
  # mysql-ai-web:<sha>(신규 마이그레이션 파일 포함)로 alembic 을 돌리게 한다. 과거엔 migrate 가
  # build 전에 실행돼 `docker compose run agent`(stale 이미지)로 head 를 오판, 신규 마이그를
  # 조용히 놓쳤다. build 는 swap(recreate) 전 단계라 이 순서에서도 expand-before-swap 불변 유지
  # (build→migrate→recreate). build 후 migrate 실패 시에도 last-good=이전본 유지(rollback 정합).
  build_image "$TARGET_SHA"
  migrate_phase
  asset_stamp_warn

  step "one-at-a-time 롤링 (항상 ≥1 healthy upstream)"
  # 첫 배포(둘 다 없음)면 둘 다 올림. 아니면 하나씩.
  if [ -z "$(replica_cid web-a)" ] && [ -z "$(replica_cid web-b)" ]; then
    log "초기 배포 — web-a, web-b 동시 기동."
    run "${DC_PROD[@]}" up -d --no-deps --no-build web-a web-b || die "초기 web 기동 실패."
    wait_ready web-a "$TARGET_SHA" || die "web-a 초기 ready 실패."
    wait_ready web-b "$TARGET_SHA" || die "web-b 초기 ready 실패."
  else
    predrain web-a web-b
    recreate_replica web-a "$TARGET_SHA" || die "web-a 배포 실패 — web-b(OLD) 가 계속 서빙 중. 수동 확인."
    predrain web-b web-a
    recreate_replica web-b "$TARGET_SHA" || { err "web-b 배포 실패 — web-a(NEW) 가 서빙 중. web-b 만 롤백/재시도 권장."; auto_rollback "$TARGET_SHA"; exit 1; }
  fi

  echo "current=$TARGET_SHA" > "$STATE_FILE"
  reconcile_caddy   # feature-0016: Caddyfile 변경 시에만 caddy recreate(inode-stale 대응)
  soak_or_rollback "$TARGET_SHA" || exit 1
  worker_divergence_warn
  normalize_ownership
  step "배포 완료: $TARGET_SHA (무중단 롤링 + soak 통과)"
}

main "$@"
