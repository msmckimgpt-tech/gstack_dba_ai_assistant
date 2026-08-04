#!/usr/bin/env bash
# feature-0039: 논리 백업 — **컨테이너 내부(ops-scheduler) 실행판**.
#
# `bin/backup.sh` (호스트 root cron + `docker exec`) 의 이관본이다. 로직·산출물·보존
# 정책은 동일하고 접속 경로만 바뀐다:
#   before: docker exec repo-postgres-1 pg_dump ...      (호스트 root, docker 소켓 필요)
#   after : pg_dump -h postgres ...                      (dbnet 네트워크 클라이언트)
#
# 산출: /artifacts/backups/<timestamp>/{agent_kb.sql.gz, agent_memory.sql.gz}
#       (= 호스트 ../artifacts/backups/<timestamp>/ — 경로 불변)
# 보존: **완료된** 백업 최근 BACKUP_KEEP(기본 14) 개.
#
# 백업 범위는 feature-0015 명시 범위를 그대로 승계한다:
#   ✓ agent_kb (PG)        — 대화/KB/런타임 정본(crown jewel).
#   ✓ agent_memory (MySQL) — 인증/RBAC/제품·데이터소스 설정/세션/첨부 메타.
#   ✗ per-conversation sandbox DB / 고객 product DB — 의도적 제외(원본 재생성 가능).
set -euo pipefail

# ── 접속 파라미터 ─────────────────────────────────────────────────────────────
# PG 는 **슈퍼유저 + postgres 직결**을 쓴다. 두 가지 이유:
#   (1) 호스트 시절 `docker exec ... pg_dump -U postgres` 와 동일 권한이어야 덤프 범위가
#       같다. 앱 롤(agent_kb_rw)로 뜨면 소유 밖 객체가 조용히 빠진다.
#   (2) pgbouncer(transaction pooling) 경유는 pg_dump 의 장수명 스냅샷 트랜잭션과
#       맞지 않는다 — 반드시 postgres 원본에 직결.
PGHOST_="${OPS_BACKUP_PG_HOST:-${AGENT_KB_PG_SUPERUSER_HOST:-postgres}}"
PGPORT_="${OPS_BACKUP_PG_PORT:-5432}"
PG_USER="${OPS_BACKUP_PG_USER:-${AGENT_KB_PG_SUPERUSER:-postgres}}"
PG_DB="${AGENT_KB_PG_DB:-agent_kb}"
export PGPASSWORD="${OPS_BACKUP_PG_PASSWORD:-${AGENT_KB_PG_SUPERPASSWORD:-}}"

MYSQL_HOST="${OPS_BACKUP_MYSQL_HOST:-${DB_HOST:-mysql}}"
MYSQL_PORT_="${OPS_BACKUP_MYSQL_PORT:-3306}"
MYSQL_USER="${OPS_BACKUP_MYSQL_USER:-root}"
MYSQL_PW="${OPS_BACKUP_MYSQL_PASSWORD:-${MYSQL_ROOT_PASSWORD:-}}"
# 서버가 self-signed 인증서라 클라이언트 검증을 끈다. dbnet 내부 트래픽이며, 이관 전
# 경로(컨테이너 내부 unix 소켓)는 애초에 TLS 가 없었다 — 보안 수준 저하 아님.
MYSQL_SSL_ARGS="${OPS_BACKUP_MYSQL_SSL_ARGS:---ssl-verify-server-cert=0}"

# 암호는 argv 대신 0600 defaults-file 로 넘긴다 — argv 는 같은 컨테이너의 `/proc/*/cmdline`
# 에 노출되고, `-p` 사용 시 클라이언트가 stderr 에 경고를 쏟아 진짜 오류를 가린다
# (이관 전 스크립트가 `2>/dev/null` 로 stderr 를 통째로 버리던 이유가 그 경고였다).
MY_CNF="$(mktemp /tmp/ops-backup-my.XXXXXX.cnf)"
chmod 600 "$MY_CNF"
cleanup() { rm -f "$MY_CNF"; }
trap cleanup EXIT
printf '[client]\nuser=%s\npassword=%s\nhost=%s\nport=%s\n' \
  "$MYSQL_USER" "$MYSQL_PW" "$MYSQL_HOST" "$MYSQL_PORT_" > "$MY_CNF"

OUT_ROOT="${OPS_BACKUP_OUT_ROOT:-/artifacts/backups}"
TS="$(date +%Y%m%d_%H%M%S)"
# 부분 산출물이 '완료된 백업' 으로 보이지 않게 `.partial` 에 쓰고 성공 시 rename 한다.
# (이관 전 스크립트는 최종 경로에 바로 써서, 반복 실패한 부분 디렉터리가 보존 회전을
#  잡아먹고 **정상 백업을 밀어내는** 경로가 있었다.)
STAGE="${OUT_ROOT}/${TS}.partial"
OUT="${OUT_ROOT}/${TS}"
mkdir -p "$STAGE"

echo "[backup] Postgres ${PG_DB}@${PGHOST_} → agent_kb.sql.gz"
pg_dump -h "$PGHOST_" -p "$PGPORT_" -U "$PG_USER" -d "$PG_DB" \
  --no-owner --clean --if-exists \
  | gzip > "$STAGE/agent_kb.sql.gz"

echo "[backup] MySQL agent_memory@${MYSQL_HOST} → agent_memory.sql.gz"
mysqldump --defaults-extra-file="$MY_CNF" $MYSQL_SSL_ARGS \
  --single-transaction --routines --triggers --databases agent_memory \
  | gzip > "$STAGE/agent_memory.sql.gz"

# 무결성 sanity (빈 덤프 차단) — 통과해야만 완료 경로로 승격한다.
rc=0
for f in agent_kb agent_memory; do
  sz=$(stat -c%s "$STAGE/$f.sql.gz" 2>/dev/null || echo 0)
  if [ "$sz" -lt 100 ]; then
    echo "[backup] 경고: $f.sql.gz 가 비정상적으로 작음 ($sz B)" >&2
    rc=1
  fi
done
if [ "$rc" -ne 0 ]; then
  echo "[backup] 무결성 검사 실패 — ${STAGE} 를 완료 처리하지 않습니다." >&2
  exit "$rc"
fi

mv "$STAGE" "$OUT"
echo "[backup] 완료 → $OUT"
ls -lah "$OUT" | sed 's/^/  /'

# 보존: **완료된** 백업만 세어 최근 N 개 유지. `.partial` 은 회전 대상에서 제외하고,
# 하루 지난 잔재만 따로 청소한다(진행 중인 다른 실행을 지우지 않도록 mtime 기준).
KEEP="${BACKUP_KEEP:-14}"
find "$OUT_ROOT" -mindepth 1 -maxdepth 1 -type d -name '*.partial' -mmin +1440 -exec rm -rf {} + 2>/dev/null || true
find "$OUT_ROOT" -mindepth 1 -maxdepth 1 -type d ! -name '*.partial' -printf '%T@ %p\n' 2>/dev/null \
  | sort -rn | tail -n "+$((KEEP+1))" | cut -d' ' -f2- | xargs -r rm -rf
echo "[backup] 보존 정책 적용 (완료 백업 최근 ${KEEP}개 유지)"
