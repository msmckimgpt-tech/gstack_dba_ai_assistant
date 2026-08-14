#!/usr/bin/env bash
# =============================================================================
# safe-recreate.sh — 배포 스파인 밖에서 서빙 컨테이너를 **안전하게** 재생성/재기동한다.
#
# 왜 필요한가 (CHG-20260812T200000):
#   2026-08-12 17:30, bedrock-gateway 가 `deploy-web.sh` **밖에서** recreate 되어 진행 중이던
#   대화가 죽었다(첨부 6건 · 라운드 1의 154초 추론 폐기). 근거: 그 시각 배포 lock mtime 은
#   13:00(직전 배포) 그대로였고 배포는 17:49·18:07 에 따로 돌았다 → 배포 경로가 아니다.
#   quiesce 게이트가 배포 스크립트 안에만 있으면 `docker compose up -d` · `make up` ·
#   단일 서비스 재기동 같은 **평범한 운영 동작 전부가 사각지대**가 된다.
#
#   이 스크립트는 그 경로를 위한 **인가된 진입점**이다 — 배포와 **같은 라이브러리**
#   (`bin/lib/quiesce.sh`)로 판정하므로 두 경로의 기준이 갈라지지 않는다.
#
# 무엇을 하는가:
#   1. 진행 중 사용자 run(ask_jobs running + web active_streams)이 0 이 되기를 기다린다.
#      상한까지 조용해지지 않거나 관측 불가면 **중단**(fail-closed) — 강행은 --force-busy.
#   2. 통과하면 `docker compose up -d --no-deps [--force-recreate] <svc>...` 를 수행한다.
#   3. 인가된 재생성으로 **스탬프를 남긴다** → `bin/recreate-audit.sh` 가 스탬프 없는(=우회)
#      재생성을 사후에 적발할 수 있다. raw `docker compose` 를 물리적으로 막을 수는 없으므로,
#      막을 수 없는 것은 **보이게** 만든다.
#
# Usage:
#   sudo -E bin/safe-recreate.sh ask-worker                  # 조용해지면 recreate
#   sudo -E bin/safe-recreate.sh bedrock-gateway web-a       # 여러 서비스(순차)
#   sudo -E bin/safe-recreate.sh --no-force-recreate mysql   # 설정 변경분만 반영(up -d)
#   sudo -E bin/safe-recreate.sh --force-busy ask-worker     # 진행 중 요청을 끊고 강행
#   sudo -E bin/safe-recreate.sh --dry-run ask-worker
#
# 주의: web-a/web-b 를 **동시에** 넘기지 말 것 — 무중단 롤링은 `make deploy-web` 의 몫이다.
#       이 스크립트는 "한 서비스를 안전한 순간에 갈아끼운다" 만 보장한다.
#
# 주의(ask-worker, feature-0020 zd-ask-rollout): 이 경로는 여전히 **전역 정적을 기다린다**.
#       바쁜 시간대에는 그 창이 열리지 않을 수 있다(실측: 유입 7~10분 간격 + run p95 691s →
#       상한 900s 안에 정적 창 없음). 코드/이미지 변경을 반영하려는 것이라면 이 스크립트가
#       아니라 `make deploy-workers` 를 쓸 것 — 배포 스파인은 surge 를 먼저 세우고 본체를
#       drain 하므로 **기다리지 않고도** 진행 중 run 을 죽이지 않는다.
#       여기서 ask-worker 를 다루는 것이 맞는 경우는 "이미지 교체 없이 지금 이 컨테이너만
#       재기동" 같은 out-of-band 운영뿐이다.
# =============================================================================
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

log()  { printf '[safe-recreate] %s\n' "$*" >&2; }
warn() { printf '[safe-recreate] WARN: %s\n' "$*" >&2; }
err()  { printf '[safe-recreate] ERROR: %s\n' "$*" >&2; }
step() { printf '\n[safe-recreate] === %s ===\n' "$*" >&2; }
die()  { err "$*"; exit 1; }

DRY_RUN=0
FORCE_BUSY=0
FORCE_RECREATE=1
SERVICES=()

usage() { sed -n '2,34p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)            DRY_RUN=1; shift ;;
    --force-busy)         FORCE_BUSY=1; shift ;;
    --no-force-recreate)  FORCE_RECREATE=0; shift ;;
    -h|--help)            usage 0 ;;
    -*)                   err "알 수 없는 옵션: $1"; usage 2 ;;
    *)                    SERVICES+=("$1"); shift ;;
  esac
done
[ "${#SERVICES[@]}" -gt 0 ] || { err "재생성할 서비스를 지정하세요."; usage 2; }

# base file-set ONLY — dev override 를 머지하지 않는다(deploy-web.sh 와 동일 규약).
DC=(docker compose -f docker-compose.yml)
DC_PROD=("${DC[@]}")
REPLICAS=(web-a web-b)
replica_cid() { "${DC_PROD[@]}" ps -q "$1" 2>/dev/null | head -1; }

_QUIESCE_LIB="$(dirname "${BASH_SOURCE[0]}")/lib/quiesce.sh"
[ -r "$_QUIESCE_LIB" ] || die "quiesce 라이브러리 없음($_QUIESCE_LIB) — 게이트 없이 재생성하지 않는다."
# shellcheck source=lib/quiesce.sh
. "$_QUIESCE_LIB"

STAMP_FILE="${SAFE_RECREATE_STAMP_FILE:-../artifacts/deploy/recreate-sanctioned.log}"

stamp_sanctioned() {  # $1 = svc
  [ "$DRY_RUN" -eq 1 ] && return 0
  mkdir -p "$(dirname "$STAMP_FILE")" 2>/dev/null || return 0
  printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "safe-recreate" >> "$STAMP_FILE" || true
}

# ── 서비스 존재 확인(오타로 조용히 no-op 되는 것 방지) ──────────────────────────
for svc in "${SERVICES[@]}"; do
  "${DC[@]}" config --services 2>/dev/null | grep -qx "$svc" \
    || die "compose 에 없는 서비스: $svc (오타?) — 아무 것도 하지 않았다."
done

# web replica 를 동시에 내리면 전면 다운이다 — 개수로 센다(무중단 롤링은 deploy-web.sh 의 몫).
_web_count=0
for svc in "${SERVICES[@]}"; do case "$svc" in web-a|web-b) _web_count=$((_web_count+1)) ;; esac; done
[ "$_web_count" -lt 2 ] || die "web-a/web-b 를 동시에 재생성하면 전면 다운이다 — 무중단 롤링은 'make deploy-web' 을 쓰세요."

step "대상: ${SERVICES[*]} (force-recreate=$FORCE_RECREATE, dry-run=$DRY_RUN)"

# ── 게이트: 진행 중 사용자 run 이 끝나기를 기다린다(배포와 동일 판정) ────────────
quiesce_gate "safe-recreate(${SERVICES[*]})" || die "재생성 중단 — 현재 컨테이너가 계속 서빙한다(무중단 유지). 조용한 시각에 재실행하거나 --force-busy."

for svc in "${SERVICES[@]}"; do
  _args=(up -d --no-deps)
  [ "$FORCE_RECREATE" -eq 1 ] && _args+=(--force-recreate)
  if [ "$DRY_RUN" -eq 1 ]; then
    log "[dry-run] ${DC[*]} ${_args[*]} $svc"
    continue
  fi
  log "recreate $svc"
  "${DC[@]}" "${_args[@]}" "$svc" || die "$svc 재생성 실패 — 위 로그 확인."
  stamp_sanctioned "$svc"
done

quiesce_summary
step "완료: ${SERVICES[*]}"
