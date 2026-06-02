#!/usr/bin/env bash
# TASK-0128 (#2): data-plane 최소권한 MySQL 유저 `agent_ro` 멱등 프로비저닝.
#
# 에이전트의 execute_sql/describe_* (LLM 작성 분석 SQL) 는 root 대신 본 유저로 고객 DB 에
# 접속한다 (db.connect() 가 database != MEMORY_DB 일 때 AGENT_DATA_DB_USER 로 분기).
# 권한: GRANT SELECT ON *.* MINUS agent_memory.* / mysql.* (partial_revokes).
#   - 모든 고객 product DB + information_schema 조회 가능 (신규 DB 추가 시 재grant 불필요)
#   - 쓰기/DDL/FILE/SUPER/GRANT 없음 → LLM SQL 이 prompt-injection 돼도 write/escalation 불가
#   - agent_memory(인증/RBAC) / mysql(자격증명) 은 DB 레이어에서 차단 (app sql_guard 와 이중 방어)
#
# 사용: bin/agent-ro-bootstrap.sh   (repo/ 에서 실행, .env.mysql 자동 로드)
# 재실행 안전 (idempotent). 신규 DB 볼륨 프로비저닝 시 1회 실행 필요.
set -euo pipefail
cd "$(dirname "$0")/.."

# .env.mysql 로드
if [ -f .env.mysql ]; then
  set -a; . ./.env.mysql; set +a
fi
: "${MYSQL_ROOT_PASSWORD:?MYSQL_ROOT_PASSWORD 필요}"
: "${AGENT_DATA_DB_USER:?AGENT_DATA_DB_USER 필요 (.env.mysql)}"
: "${AGENT_DATA_DB_PASSWORD:?AGENT_DATA_DB_PASSWORD 필요 (.env.mysql)}"

CONTAINER="${MYSQL_CONTAINER:-repo-mysql-1}"

docker exec -i "$CONTAINER" mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" <<SQL
SET PERSIST partial_revokes = ON;
CREATE USER IF NOT EXISTS '${AGENT_DATA_DB_USER}'@'%' IDENTIFIED BY '${AGENT_DATA_DB_PASSWORD}';
ALTER USER '${AGENT_DATA_DB_USER}'@'%' IDENTIFIED BY '${AGENT_DATA_DB_PASSWORD}';
GRANT SELECT ON *.* TO '${AGENT_DATA_DB_USER}'@'%';
REVOKE SELECT ON agent_memory.* FROM '${AGENT_DATA_DB_USER}'@'%';
REVOKE SELECT ON mysql.* FROM '${AGENT_DATA_DB_USER}'@'%';
FLUSH PRIVILEGES;
SQL

echo "[agent-ro-bootstrap] OK — ${AGENT_DATA_DB_USER} 프로비저닝 완료"
docker exec -i "$CONTAINER" mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" -N -e \
  "SHOW GRANTS FOR '${AGENT_DATA_DB_USER}'@'%';" 2>/dev/null || true
