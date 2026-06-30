#!/usr/bin/env bash
# =============================================================================
# pg-restart.sh — feature-0016: Postgres primary 재시작을 near-zero RW 단절로 수행.
#
# pgbouncer(transaction-mode) 를 PAUSE 하면 진행 중 트랜잭션을 마치고 신규 client 쿼리를
# **에러 대신 큐잉**한다. 그 사이 PG primary 를 재시작(config/minor)하고, healthy 후 RESUME
# 하면 큐잉된 client 가 재연결된 PG 로 풀린다 → client 는 짧은 지연만(에러 없음).
#
# 적용 범위: PG config 변경(.env.postgres / postgresql.conf) 반영, minor 재시작. major 업그레이드/
# 데이터 호환 단계는 정비창 필요(본 래퍼 범위 밖). 단일 호스트라 HA 는 아님(가용성 한계 §feasibility).
#
# 안전: RESUME 을 trap 으로 보장(스크립트가 죽어도 pgbouncer 가 paused 로 남지 않음 — 그렇지 않으면
# 모든 RW 가 막힌다). PAUSE 는 --pause-timeout 으로 bound(긴 트랜잭션이 PAUSE 를 막으면 abort+RESUME).
#
# 사용:
#   sudo -E bin/pg-restart.sh                  # PAUSE → postgres recreate → wait healthy → RESUME
#   sudo -E bin/pg-restart.sh --action "docker compose -f docker-compose.yml restart postgres"
#   sudo -E bin/pg-restart.sh --dry-run
#   sudo -E bin/pg-restart.sh --check          # admin 접근만 확인(PAUSE 안 함)
# Exit: 0 성공 / 1 실패(이미 RESUME 됨) / 2 usage·preflight.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

PGB_CONTAINER="${PGB_CONTAINER:-repo-pgbouncer-1}"
PG_SERVICE="postgres"
DC=(docker compose -f docker-compose.yml)
PAUSE_TIMEOUT="${PG_RESTART_PAUSE_TIMEOUT:-30}"
HEALTH_TIMEOUT="${PG_RESTART_HEALTH_TIMEOUT:-90}"
ACTION="${DC[*]} up -d --no-deps --force-recreate ${PG_SERVICE}"
DRY_RUN=0; MODE="restart"

log()  { printf '[pg-restart] %s\n' "$*" >&2; }
die()  { log "ERROR: $*"; exit 1; }
die2() { log "ERROR: $*"; exit 2; }

while [ $# -gt 0 ]; do case "$1" in
  --action) ACTION="${2:?}"; shift 2 ;;
  --pause-timeout) PAUSE_TIMEOUT="${2:?}"; shift 2 ;;
  --dry-run) DRY_RUN=1; shift ;;
  --check) MODE="check"; shift ;;
  --help|-h) sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) die2 "unknown arg: $1" ;;
esac; done

# pgbouncer admin 콘솔에 컨테이너 내부 psql 로 명령 실행(비밀번호는 컨테이너 $DB_PASSWORD — 호스트 미노출).
pgb_admin() {  # $1 = SQL (PAUSE/RESUME/SHOW ...)
  docker exec "$PGB_CONTAINER" sh -c \
    'PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p 5432 -U "$DB_USER" -d pgbouncer -tAc "'"$1"'"' 2>&1
}

preflight() {
  docker inspect "$PGB_CONTAINER" >/dev/null 2>&1 || die2 "pgbouncer 컨테이너($PGB_CONTAINER) 없음."
  local out
  out="$(pgb_admin 'SHOW VERSION;' || true)"
  if ! printf '%s' "$out" | grep -qiE 'PgBouncer|pgbouncer'; then
    die2 "pgbouncer admin 콘솔 접근 실패. compose 의 pgbouncer ADMIN_USERS=\${AGENT_KB_PG_USER} 적용 후 pgbouncer recreate 필요. 응답: $(printf '%s' "$out" | head -1)"
  fi
  log "admin 콘솔 OK ($(printf '%s' "$out" | head -1))"
}

do_resume() {
  # 항상 호출(trap) — 멱등(이미 RESUME 면 무해). paused 로 남기지 않는 게 최우선.
  local r; r="$(pgb_admin 'RESUME;' 2>&1 || true)"
  log "RESUME: ${r:-(ok)}"
}

wait_pg_healthy() {
  local deadline=$(( SECONDS + HEALTH_TIMEOUT ))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if "${DC[@]}" ps "$PG_SERVICE" --format '{{.Health}}' 2>/dev/null | grep -q healthy; then
      log "postgres healthy"; return 0
    fi
    sleep 2
  done
  return 1
}

preflight
if [ "$MODE" = "check" ]; then
  log "--check: admin 접근 정상. (PAUSE/restart 미수행)"; exit 0
fi

if [ "$DRY_RUN" -eq 1 ]; then
  log "[dry-run] PAUSE → ($ACTION) → wait healthy → RESUME. (실제 미수행)"; exit 0
fi

# 여기부터 PAUSE — 반드시 RESUME 보장.
trap 'do_resume' EXIT INT TERM

log "PAUSE (transaction drain, timeout ${PAUSE_TIMEOUT}s) — 신규 RW 는 큐잉됨"
if ! timeout "$PAUSE_TIMEOUT" docker exec "$PGB_CONTAINER" sh -c \
     'PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p 5432 -U "$DB_USER" -d pgbouncer -tAc "PAUSE;"' >/dev/null 2>&1; then
  die "PAUSE 실패/timeout(${PAUSE_TIMEOUT}s) — 긴 트랜잭션이 drain 안 됨. 재시작 중단(트랩이 RESUME). 한가할 때 재시도."
fi
log "PAUSE 완료 — PG 재시작 수행: $ACTION"

if ! eval "$ACTION"; then
  die "postgres 재시작 액션 실패 — 트랩이 RESUME. PG 상태 점검 필요."
fi

if ! wait_pg_healthy; then
  die "postgres 가 ${HEALTH_TIMEOUT}s 내 healthy 안 됨 — 트랩이 RESUME(되나 PG 불안정). 수동 점검."
fi

do_resume
trap - EXIT INT TERM   # 정상 경로 — 위에서 RESUME 했으니 중복 방지

# 검증: pgbouncer 경유 RW 1-probe
verify="$(docker exec "$PGB_CONTAINER" sh -c 'PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -p 5432 -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT 1"' 2>&1 || true)"
if printf '%s' "$verify" | grep -q '^1$'; then
  log "✓ pg-restart 완료 — pgbouncer 경유 RW 정상(near-zero 단절). RESUME 됨."
  exit 0
else
  log "⚠ 재시작·RESUME 했으나 pgbouncer 경유 RW probe 실패: $(printf '%s' "$verify" | head -1). 수동 점검."
  exit 1
fi
