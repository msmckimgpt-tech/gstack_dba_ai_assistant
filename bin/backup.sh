#!/usr/bin/env bash
# TASK-0130 (#5): 논리 백업 — 플랫폼 crown-jewel 데이터의 disaster recovery.
#
# 감사 DEEP_AUDIT_20260529.md #5: 백업이 사실상 없음(05-20 단일 11.9KB 덤프 1개). PG(agent_kb:
# 대화/KB/런타임 정본) + MySQL(agent_memory: RBAC/auth/첨부 메타) 를 정기 덤프한다. 고객
# product DB(수십 GB)는 고객 원본이라 제외 — 플랫폼 고유 데이터만 대상.
#
# 사용: bin/backup.sh   (repo/ 에서; host cron 또는 make backup 으로 스케줄)
# 산출: ../artifacts/backups/<timestamp>/{agent_kb.sql.gz, agent_memory.sql.gz}
# 보존: 최근 BACKUP_KEEP(기본 14) 개. PITR(WAL 아카이빙)은 후속 enhancement.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env.mysql ] && { set -a; . ./.env.mysql; set +a; }
[ -f .env.postgres ] && { set -a; . ./.env.postgres; set +a; }

TS="$(date +%Y%m%d_%H%M%S)"
OUT="../artifacts/backups/${TS}"
mkdir -p "$OUT"
PG_USER="${AGENT_KB_PG_USER:-postgres}"
PG_DB="${AGENT_KB_PG_DB:-agent_kb}"
PG_CONTAINER="${PG_CONTAINER:-repo-postgres-1}"
MYSQL_CONTAINER="${MYSQL_CONTAINER:-repo-mysql-1}"

echo "[backup] Postgres ${PG_DB} → agent_kb.sql.gz"
docker exec -e PGPASSWORD="${AGENT_KB_PG_PASSWORD:-}" "$PG_CONTAINER" \
  pg_dump -U "$PG_USER" -d "$PG_DB" --no-owner --clean --if-exists \
  | gzip > "$OUT/agent_kb.sql.gz"

echo "[backup] MySQL agent_memory → agent_memory.sql.gz"
docker exec "$MYSQL_CONTAINER" sh -c \
  "mysqldump -uroot -p'${MYSQL_ROOT_PASSWORD}' --single-transaction --routines --triggers --databases agent_memory" 2>/dev/null \
  | gzip > "$OUT/agent_memory.sql.gz"

echo "[backup] 완료 → $OUT"
ls -lah "$OUT" | sed 's/^/  /'

# 무결성 sanity (빈 덤프 차단)
for f in agent_kb agent_memory; do
  sz=$(stat -c%s "$OUT/$f.sql.gz" 2>/dev/null || echo 0)
  if [ "$sz" -lt 100 ]; then echo "[backup] 경고: $f.sql.gz 가 비정상적으로 작음 ($sz B)" >&2; fi
done

# 보존: 최근 N 개만
KEEP="${BACKUP_KEEP:-14}"
ls -1dt ../artifacts/backups/*/ 2>/dev/null | tail -n "+$((KEEP+1))" | xargs -r rm -rf
echo "[backup] 보존 정책 적용 (최근 ${KEEP}개 유지)"
