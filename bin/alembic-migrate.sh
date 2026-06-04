#!/usr/bin/env bash
# =============================================================================
# alembic-migrate.sh — TASK-0149 (#15): 라이브 agent_kb 에 alembic 마이그레이션 적용.
#
# 본 배포의 인증 모델상 Postgres superuser(postgres) 는 **컨테이너 로컬 trust 소켓**
# 으로만 접근 가능하다(agent 컨테이너에서 TCP scram 인증 불가 — 비밀번호 미공유).
# 따라서 privileged DDL 은 agent 컨테이너에서 alembic offline `--sql` 로 SQL 만 생성하고,
# 그 SQL 을 postgres 컨테이너의 로컬 소켓 superuser 로 적용한다(인증 변경 0).
#
# app(agent_kb_rw)은 의도적으로 DDL 권한이 없다(least-privilege) — 그래서 online
# alembic 을 app 유저로 돌리면 'permission denied for schema' 로 실패한다.
#
# 사용:
#   bin/alembic-migrate.sh upgrade   # 미적용 revision 을 head 까지 적용
#   bin/alembic-migrate.sh stamp     # 기존 스키마를 head 로 표시(DDL 0)
#   bin/alembic-migrate.sh current   # 라이브 현재 revision 조회
# =============================================================================
set -euo pipefail

ACTION="${1:-current}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PG_CONTAINER="${COMPOSE_PROJECT_NAME:-repo}-postgres-1"
KB_DB="$(grep -E '^AGENT_KB_PG_DB=' .env .env.postgres 2>/dev/null | head -1 | cut -d= -f2- || true)"
KB_DB="${KB_DB:-agent_kb}"

psql_super() {  # 로컬 소켓 trust superuser (비밀번호 불요)
  docker exec -i "$PG_CONTAINER" psql -U postgres -d "$KB_DB" -v ON_ERROR_STOP=1 "$@"
}

live_current() {
  psql_super -tAc "SELECT version_num FROM alembic_version LIMIT 1" 2>/dev/null | tr -d '[:space:]' || true
}

# agent 컨테이너에서 alembic offline --sql 생성(DB 무연결). 표준출력=순수 SQL.
gen_sql() {  # $1 = alembic 인자 (예: "upgrade 0001:head")
  COMPOSE_BAKE=false docker compose run --rm --no-deps -w /app --entrypoint sh agent -lc \
    "pip install -q --no-cache-dir alembic 'psycopg[binary]' sqlalchemy >/tmp/pa.log 2>&1 || { cat /tmp/pa.log; exit 1; }; alembic $1 --sql" 2>/dev/null
}

case "$ACTION" in
  current)
    cur="$(live_current)"
    echo "live alembic_version = ${cur:-<none>}"
    ;;

  stamp)
    # 기존(이미 스키마 보유) DB 를 head 로 표시. alembic_version 멱등 보장.
    head_rev="$(COMPOSE_BAKE=false docker compose run --rm --no-deps -w /app --entrypoint sh agent -lc "pip install -q alembic 'psycopg[binary]' sqlalchemy >/dev/null 2>&1; alembic heads" 2>/dev/null | awk 'NF{print $1; exit}')"
    head_rev="${head_rev:-0001_baseline}"
    echo "stamp → ${head_rev}"
    psql_super <<SQL
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO alembic_version (version_num)
SELECT '${head_rev}'
WHERE NOT EXISTS (SELECT 1 FROM alembic_version);
GRANT SELECT ON alembic_version TO agent_kb_rw;
SELECT 'stamped='||version_num FROM alembic_version;
SQL
    ;;

  upgrade)
    cur="$(live_current)"
    if [ -z "$cur" ]; then
      echo "alembic_version 없음 — 먼저 'stamp' 로 baseline 표시(또는 fresh DB 면 upgrade head 전체 적용)."
      spec="upgrade head"
    else
      spec="upgrade ${cur}:head"
    fi
    sql="$(gen_sql "$spec")"
    # BEGIN/COMMIT/주석/빈줄 외 실제 statement 가 있는지 확인
    if [ -z "$(printf '%s\n' "$sql" | grep -ivE '^\s*(BEGIN|COMMIT|--|UPDATE alembic_version|$)')" ]; then
      echo "적용할 pending 마이그레이션 없음 (current=${cur} == head)."
      exit 0
    fi
    echo "=== 적용할 SQL (preview) ==="
    printf '%s\n' "$sql" | head -40
    echo "=== postgres 로컬 소켓 superuser 로 적용 ==="
    printf '%s\n' "$sql" | psql_super
    echo "적용 완료. live current:"
    live_current
    ;;

  *)
    echo "usage: $0 {current|stamp|upgrade}" >&2
    exit 2
    ;;
esac
