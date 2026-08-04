#!/usr/bin/env bash
# =============================================================================
# feature-0039: 백업 복원 가능성 정기 리허설 — **컨테이너 내부(ops-scheduler) 실행판**.
#
# `bin/restore-rehearsal.sh` (호스트 root cron + `docker exec`) 의 이관본. 검증 로직은
# 동일하고 접속 경로만 네트워크 클라이언트로 바뀐다.
#
# 백업은 '복원될 때만' 백업이다. 최신 ops_backup.sh 산출물을 **throwaway DB**
# (agent_kb_rehearsal_<ts> / agent_memory_rehearsal_<ts>)로 복원해 객체 수를 검증하고
# 즉시 DROP 한다. **프로덕션 DB(agent_kb / agent_memory)는 절대 건드리지 않는다.**
#
# 사용: ops_restore_rehearsal.sh [--backup <dir>]   (기본: 최신 /artifacts/backups/*)
# Exit: 0 복원 검증 PASS / 1 FAIL / 2 usage.
# =============================================================================
set -euo pipefail

PGHOST_="${OPS_BACKUP_PG_HOST:-${AGENT_KB_PG_SUPERUSER_HOST:-postgres}}"
PGPORT_="${OPS_BACKUP_PG_PORT:-5432}"
PG_USER="${OPS_BACKUP_PG_USER:-${AGENT_KB_PG_SUPERUSER:-postgres}}"
export PGPASSWORD="${OPS_BACKUP_PG_PASSWORD:-${AGENT_KB_PG_SUPERPASSWORD:-}}"

MYSQL_HOST="${OPS_BACKUP_MYSQL_HOST:-${DB_HOST:-mysql}}"
MYSQL_PORT_="${OPS_BACKUP_MYSQL_PORT:-3306}"
MYSQL_USER="${OPS_BACKUP_MYSQL_USER:-root}"
MYSQL_PW="${OPS_BACKUP_MYSQL_PASSWORD:-${MYSQL_ROOT_PASSWORD:-}}"
MYSQL_SSL_ARGS="${OPS_BACKUP_MYSQL_SSL_ARGS:---ssl-verify-server-cert=0}"

OUT_ROOT="${OPS_BACKUP_OUT_ROOT:-/artifacts/backups}"
BACKUP_DIR=""

while [ $# -gt 0 ]; do case "$1" in
  --backup) BACKUP_DIR="${2:?}"; shift 2 ;;
  --help|-h) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "unknown arg: $1" >&2; exit 2 ;;
esac; done

log() { printf '[restore-rehearsal] %s\n' "$*" >&2; }

# 암호는 argv 대신 0600 defaults-file 로 (ops_backup.sh 와 동일 근거 — /proc 노출 + 경고 소음).
MY_CNF="$(mktemp /tmp/ops-rehearsal-my.XXXXXX.cnf)"
chmod 600 "$MY_CNF"
printf '[client]\nuser=%s\npassword=%s\nhost=%s\nport=%s\n' \
  "$MYSQL_USER" "$MYSQL_PW" "$MYSQL_HOST" "$MYSQL_PORT_" > "$MY_CNF"

pg() { psql -h "$PGHOST_" -p "$PGPORT_" -U "$PG_USER" "$@"; }
my() { mysql --defaults-extra-file="$MY_CNF" $MYSQL_SSL_ARGS "$@"; }

# 완료되지 않은 `.partial` 산출물을 리허설 대상으로 고르지 않는다(ops_backup.sh 의 staging).
[ -n "$BACKUP_DIR" ] || BACKUP_DIR="$(find "$OUT_ROOT" -mindepth 1 -maxdepth 1 -type d ! -name '*.partial' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2- || true)"
[ -n "$BACKUP_DIR" ] && [ -d "$BACKUP_DIR" ] || { log "복원할 백업이 없습니다 (${OUT_ROOT}). 먼저 백업을 실행하세요."; exit 1; }
log "대상 백업: $BACKUP_DIR"

TS="$(date +%s)"
PG_TMP="agent_kb_rehearsal_${TS}"
MY_TMP="agent_memory_rehearsal_${TS}"
rc=0

cleanup() {
  pg -d postgres -v ON_ERROR_STOP=0 \
    -c "DROP DATABASE IF EXISTS ${PG_TMP} WITH (FORCE);" >/dev/null 2>&1 || true
  my -e "DROP DATABASE IF EXISTS \`${MY_TMP}\`" >/dev/null 2>&1 || true
  rm -f "$MY_CNF"
}
trap cleanup EXIT

# ── PG (crown jewel) — throwaway DB 로 전량 복원 + 객체 검증 ────────────────────
if [ -f "$BACKUP_DIR/agent_kb.sql.gz" ]; then
  log "PG: ${PG_TMP} 생성 + agent_kb.sql.gz 복원"
  pg -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${PG_TMP};" >/dev/null
  # ── AGE 사전 프로비저닝 (feature-0039 에서 발견·수정한 5주 묵은 리허설 결함) ──
  # `pg_dump --clean` 산출물의 `DROP EXTENSION IF EXISTS age;` 는 **빈 DB 에서**
  # `ERROR: schema "ag_catalog" does not exist` 로 실패한다. AGE 가
  # shared_preload_libraries 로 올라온 서버에서는 그 utility 훅이 ag_catalog 를 무조건
  # 조회해 `IF EXISTS` 가 단락되지 않기 때문이다. 그 결과 feature-0016 AGE cutover
  # (2026-06-30) 이후 주간 리허설의 PG 구간이 계속 FAIL 했다(cron.log 07-05·12·19·26 실측).
  # 실제 DR 에서도 복원 대상 DB 는 AGE 가 설치된 상태여야 하므로, 리허설도 그 baseline 을
  # 재현한다 — 프로덕션 DB 는 여전히 미접촉(임시 DB 전용).
  if ! pg -d "$PG_TMP" -q -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS age;" >/dev/null 2>&1; then
    log "! AGE 확장 사전 생성 실패 — cutover 전 환경이면 정상(계속 진행)"
  fi
  # ON_ERROR_STOP=1: 복원 중 per-statement 오류를 즉시 실패시켜 '부분 복원'을 탐지(검증 리허설의 핵심).
  if gunzip -c "$BACKUP_DIR/agent_kb.sql.gz" \
     | pg -d "$PG_TMP" -q -v ON_ERROR_STOP=1 >/tmp/rr_pg.log 2>&1; then
    tbls="$(pg -d "$PG_TMP" -tAc \
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
  my -e "CREATE DATABASE \`${MY_TMP}\`" >/dev/null 2>&1
  if gunzip -c "$BACKUP_DIR/agent_memory.sql.gz" \
     | sed -E '/^CREATE DATABASE/d; /^USE `?agent_memory`?/d' \
     | my "${MY_TMP}" >/tmp/rr_my.log 2>&1; then
    tbls="$(my -N -e "SELECT count(*) FROM information_schema.tables WHERE table_schema='${MY_TMP}'" 2>/dev/null | tr -d '[:space:]')"
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
