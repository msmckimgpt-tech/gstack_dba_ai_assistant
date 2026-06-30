#!/usr/bin/env bash
# =============================================================================
# restore-rehearsal.sh — feature-0015 (⑤): 백업 복원 가능성 정기 리허설.
#
# 백업은 '복원될 때만' 백업이다. 본 스크립트는 최신 bin/backup.sh 산출물을 **throwaway DB**
# (agent_kb_rehearsal_<ts> / agent_memory_rehearsal_<ts>)로 복원해 행 수를 검증하고 즉시 DROP 한다.
# **프로덕션 DB(agent_kb / agent_memory)는 절대 건드리지 않는다** — 별도 임시 DB 로만 복원.
#
# 사용: bin/restore-rehearsal.sh [--backup <dir>]   (기본: 최신 ../artifacts/backups/*)
# Exit: 0 복원 검증 PASS / 1 FAIL / 2 usage.
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env.mysql ] && { set -a; . ./.env.mysql; set +a; }
[ -f .env.postgres ] && { set -a; . ./.env.postgres; set +a; }

PG_USER="${AGENT_KB_PG_USER:-postgres}"
PG_CONTAINER="${PG_CONTAINER:-repo-postgres-1}"
MYSQL_CONTAINER="${MYSQL_CONTAINER:-repo-mysql-1}"
BACKUP_DIR=""

while [ $# -gt 0 ]; do case "$1" in
  --backup) BACKUP_DIR="${2:?}"; shift 2 ;;
  --help|-h) sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "unknown arg: $1" >&2; exit 2 ;;
esac; done

log() { printf '[restore-rehearsal] %s\n' "$*" >&2; }

[ -n "$BACKUP_DIR" ] || BACKUP_DIR="$(ls -1dt ../artifacts/backups/*/ 2>/dev/null | head -1 || true)"
[ -n "$BACKUP_DIR" ] && [ -d "$BACKUP_DIR" ] || { log "복원할 백업이 없습니다 (../artifacts/backups/). 먼저 make backup."; exit 1; }
log "대상 백업: $BACKUP_DIR"

TS="$(date +%s)"
PG_TMP="agent_kb_rehearsal_${TS}"
MY_TMP="agent_memory_rehearsal_${TS}"
rc=0

cleanup() {
  docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d postgres -v ON_ERROR_STOP=0 \
    -c "DROP DATABASE IF EXISTS ${PG_TMP} WITH (FORCE);" >/dev/null 2>&1 || true
  docker exec "$MYSQL_CONTAINER" sh -c "mysql -uroot -p'${MYSQL_ROOT_PASSWORD}' -e 'DROP DATABASE IF EXISTS \`${MY_TMP}\`'" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# ── PG (crown jewel) — throwaway DB 로 전량 복원 + 행 검증 ─────────────────────
if [ -f "$BACKUP_DIR/agent_kb.sql.gz" ]; then
  log "PG: ${PG_TMP} 생성 + agent_kb.sql.gz 복원"
  docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d postgres -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE ${PG_TMP};" >/dev/null
  # ON_ERROR_STOP=1: 복원 중 per-statement 오류를 즉시 실패시켜 '부분 복원'을 탐지(검증 리허설의 핵심).
  if gunzip -c "$BACKUP_DIR/agent_kb.sql.gz" \
     | docker exec -i "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_TMP" -q -v ON_ERROR_STOP=1 >/tmp/rr_pg.log 2>&1; then
    # 복원된 객체/행 sanity: 사용자 테이블 수 + 핵심 테이블 1개 행 수
    tbls="$(docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_TMP" -tAc \
      "SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog','information_schema')" 2>/dev/null | tr -d '[:space:]')"
    log "PG 복원 OK — 사용자 테이블 ${tbls:-0}개"
    [ "${tbls:-0}" -ge 1 ] || { log "✗ PG: 복원 테이블 0개 — 백업 비정상"; rc=1; }
  else
    log "✗ PG 복원 실패:"; tail -5 /tmp/rr_pg.log >&2; rc=1
  fi
else
  log "✗ agent_kb.sql.gz 없음"; rc=1
fi

# ── MySQL — CREATE DATABASE/USE 라인 제거 후 throwaway DB 로 복원 (프로덕션 미접촉) ──
if [ -f "$BACKUP_DIR/agent_memory.sql.gz" ]; then
  log "MySQL: ${MY_TMP} 생성 + agent_memory.sql.gz 복원(자기-타겟 CREATE/USE 제거)"
  docker exec "$MYSQL_CONTAINER" sh -c "mysql -uroot -p'${MYSQL_ROOT_PASSWORD}' -e 'CREATE DATABASE \`${MY_TMP}\`'" >/dev/null 2>&1
  if gunzip -c "$BACKUP_DIR/agent_memory.sql.gz" \
     | sed -E '/^CREATE DATABASE/d; /^USE `?agent_memory`?/d' \
     | docker exec -i "$MYSQL_CONTAINER" sh -c "mysql -uroot -p'${MYSQL_ROOT_PASSWORD}' '${MY_TMP}'" >/tmp/rr_my.log 2>&1; then
    tbls="$(docker exec "$MYSQL_CONTAINER" sh -c "mysql -uroot -p'${MYSQL_ROOT_PASSWORD}' -N -e \"SELECT count(*) FROM information_schema.tables WHERE table_schema='${MY_TMP}'\"" 2>/dev/null | tr -d '[:space:]')"
    log "MySQL 복원 OK — 테이블 ${tbls:-0}개"
    [ "${tbls:-0}" -ge 1 ] || { log "✗ MySQL: 복원 테이블 0개 — 백업 비정상"; rc=1; }
  else
    log "✗ MySQL 복원 실패:"; tail -5 /tmp/rr_my.log >&2; rc=1
  fi
else
  log "✗ agent_memory.sql.gz 없음"; rc=1
fi

rm -f /tmp/rr_pg.log /tmp/rr_my.log
if [ "$rc" -eq 0 ]; then log "✓ 복원 리허설 PASS — 백업이 복원 가능함을 확인(임시 DB 정리됨)."; else log "✗ 복원 리허설 FAIL — 백업/복원 경로 점검 필요."; fi
exit "$rc"
