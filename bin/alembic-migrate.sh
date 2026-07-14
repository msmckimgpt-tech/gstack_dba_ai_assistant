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

# alembic 실행 컨텍스트. 기본은 agent 서비스(docker compose run). 단 MIGRATE_ALEMBIC_IMAGE 가
# 설정되면(배포가 방금 빌드한 mysql-ai-web:<sha> 를 넘김) 그 이미지로 docker run 한다 — 배포의
# `docker compose run agent` 가 stale agent 이미지(신규 마이그 파일 부재)를 써 신규 마이그레이션을
# "current==head, 적용 없음" 으로 조용히 놓치던 회귀를 차단한다(feature-0014-migrate-fresh-image).
# offline(--sql)·heads 는 DB 무연결이라 .env* 의 KB PG 설정만 있으면 된다(존재하는 파일만 주입).
_alembic_sh() {  # $1 = 컨테이너 안에서 실행할 alembic 명령 (예: "alembic heads")
  local inner="pip install -q --no-cache-dir alembic 'psycopg[binary]' sqlalchemy >/tmp/pa.log 2>&1 || { cat /tmp/pa.log; exit 1; }; $1"
  if [ -n "${MIGRATE_ALEMBIC_IMAGE:-}" ]; then
    local envargs=() f
    for f in .env .env.postgres .env.mysql; do [ -f "$f" ] && envargs+=(--env-file "$f"); done
    docker run --rm -w /app --entrypoint sh "${envargs[@]}" "$MIGRATE_ALEMBIC_IMAGE" -lc "$inner"
  else
    COMPOSE_BAKE=false docker compose run --rm --no-deps -w /app --entrypoint sh agent -lc "$inner"
  fi
}

# feature-0020 (AC-3): MIGRATE_ALEMBIC_IMAGE 미설정 직접 호출 stale-image 가드.
# `compose run agent` 는 마지막으로 빌드된 repo-agent 이미지를 쓴다 — working tree 에 신규
# 마이그레이션 파일이 있어도 stale 이미지엔 없어 upgrade 가 "current==head, 적용 없음" 으로
# 조용히 놓치고(2026-07-02 마이그 0030 실측 회귀와 동일 클래스 — deploy-web 경로는 fresh 이미지
# 주입으로 기수정), stamp 는 잘못된 head 로 기록한다. 변이 액션(upgrade|stamp)에 한해 선행
# 재빌드로 이미지를 working tree 와 정합시킨다. 생략은 MIGRATE_SKIP_REBUILD=1 명시로만.
# (top-level 1회 — _alembic_sh 는 $() 서브셸에서 호출되어 함수 내 once-플래그가 유지되지 않음.)
if [ -z "${MIGRATE_ALEMBIC_IMAGE:-}" ] && [ "${MIGRATE_SKIP_REBUILD:-0}" != "1" ] \
   && { [ "$ACTION" = "upgrade" ] || [ "$ACTION" = "stamp" ]; }; then
  echo "[alembic-migrate] MIGRATE_ALEMBIC_IMAGE 미설정 + ACTION=$ACTION — stale 이미지 방지 위해 agent 이미지 선행 재빌드(생략: MIGRATE_SKIP_REBUILD=1)." >&2
  # 리뷰 M-3: 빌드 실패를 WARN-continue 하면 stale 이미지가 그대로 남아 upgrade 는 stale head
  # 기준 "pending 없음"(exit 0)·stamp 는 옛 head 기록 — 본 가드가 봉인하려던 silent-miss 재현.
  # deploy-web build 게이트와 동형: exit≠0 은 snap-docker metadata-race 마커가 있을 때만 관용,
  # 아니면 하드 중단. GIT_COMMIT 도 주입해 이미지 각인(TASK-0126)을 보존한다.
  _bl="$(mktemp)"
  _gc="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  if ! GIT_COMMIT="$_gc" COMPOSE_BAKE=false docker compose build agent >"$_bl" 2>&1; then
    if grep -qiE 'compose-build-metadataFile|metadataFile.*no such file|metadata file.*no such file' "$_bl"; then
      echo "[alembic-migrate] WARN: compose build agent exit≠0 이나 metadata-race 마커 검출 — 이미지 정상 산출로 판단, 계속." >&2
    else
      tail -15 "$_bl" >&2; rm -f "$_bl"
      echo "[alembic-migrate] ERROR: agent 이미지 재빌드 실패(race 마커 없음) — stale 이미지로 $ACTION 을 진행하면 head 오판(silent-miss) 위험. 중단." >&2
      exit 1
    fi
  fi
  rm -f "$_bl"
fi

# alembic offline --sql 생성(DB 무연결). 성공 시 stdout=순수 SQL, 실패 시 non-zero rc 전파.
# (기존 `2>/dev/null` 만으로는 docker/pip/alembic 실패가 빈 SQL 로 삼켜져 upgrade 가 "pending 없음"
#  으로 false-green → swap 진행하던 silent-miss 클래스가 남았다. 이제 rc 를 살려 호출부가 die 한다.)
gen_sql() {  # $1 = alembic 인자 (예: "upgrade 0001:head")
  local out rc
  out="$(_alembic_sh "alembic $1 --sql" 2>/dev/null)" && rc=0 || rc=$?
  printf '%s' "$out"
  return "$rc"
}

case "$ACTION" in
  current)
    cur="$(live_current)"
    echo "live alembic_version = ${cur:-<none>}"
    ;;

  stamp)
    # 기존(이미 스키마 보유) DB 를 head 로 표시. alembic_version 멱등 보장.
    head_rev="$(_alembic_sh "alembic heads" 2>/dev/null | awk 'NF{print $1; exit}')"
    head_rev="${head_rev:-0001_baseline}"
    echo "stamp → ${head_rev}"
    psql_super <<SQL
-- TASK-0306: version_num 을 VARCHAR(128) 로 (alembic 기본 32 아님). 본 프로젝트 revision id
-- 가 길어(예: 0015_sample_queries_embed_dim_1024 = 34자) 32 를 초과 → 32 면 stamp/upgrade 시
-- 'value too long' 로 기록 실패(라이브에서 0015 stamp 가 이 사유로 막혔음). 기존 테이블이 32 면
-- 아래 ALTER 가 폭을 넓힌다(멱등·데이터 보존).
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(128) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128);
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
    if ! sql="$(gen_sql "$spec")"; then
      echo "마이그레이션 SQL 생성 실패 (docker/이미지/pip/alembic). ABORT — swap 안 함." >&2
      exit 1
    fi
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
