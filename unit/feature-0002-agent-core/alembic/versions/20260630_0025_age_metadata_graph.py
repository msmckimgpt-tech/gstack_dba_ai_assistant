"""age_metadata_graph — Apache AGE 그래프 백엔드 + metadata_kb 그래프 (feature-0016-metadata-graph).

사용자 결정(2026-06-30, A3): KB 전용 PG 에 Apache AGE(openCypher) 를 즉시 도입한다. 관계형 메타데이터
테이블을 SSOT 로 유지하고, AGE `metadata_kb` 그래프는 그 **투영(projection)** 으로 둔다(rebuild 가능).
8,122 테이블 규모에서 AI 컨텍스트 초과를 그래프 네비게이션(k-hop)으로 해소하고, UI·AI 가 동일 그래프를
공유해 정합을 보장하는 것이 목적(FUNCTION.md §1·§4).

본 마이그레이션은:
  1. `CREATE EXTENSION age` (확장 등록).
  2. `metadata_kb` 그래프 생성(멱등 — ag_graph 존재 검사).
  3. **모든 vlabel/elabel 사전 선언** — 동적 라벨 생성(runtime DDL)을 없애 GRANT 를 결정적으로 만든다.
     vlabel: Product · Datasource · Schema · Table · Column · GlossaryTerm
     elabel: USES · HAS_SCHEMA · HAS_TABLE · HAS_COLUMN · REFERENCES · RELATED_TERM · DESCRIBES
  4. GRANT (DEPLOY TRAP — 0024/0023 동형, superuser 적용이라 DEFAULT PRIVILEGES 미커버):
     - agent_kb_rw: 라벨 테이블 DML + ag_catalog 함수 EXECUTE (cypher write).
     - agent_kb_ro: 라벨 테이블 SELECT + ag_catalog 함수 EXECUTE (cypher read; 쓰기는 테이블 권한에서 차단).
     - ALTER DEFAULT PRIVILEGES 로 향후 라벨 테이블도 자동 커버.
  GRANT 는 role 존재 가드(throwaway/로컬 DB 안전) — prod 에선 항상 존재.

**적용 순서 의존성 (중요)**: 본 마이그레이션은 `age` 확장이 설치된 PG 이미지에서만 적용 가능하다.
운영 postgres/postgres-replica 가 커스텀 AGE 이미지(unit/feature-0016-metadata-graph/docker/Dockerfile.pg-age)
로 cutover 된 **이후** alembic 이 본 리비전을 적용해야 한다(TASK.md Phase 5 cutover 게이트). 현 pgvector/pgvector:pg16
이미지에서 적용 시 `CREATE EXTENSION age` 가 실패한다(설계상 — cutover 전 적용 금지).

**LOAD-BEARING — shared_preload_libraries='age' 필수 (Phase 0/1a 검증으로 확인)**: PostgreSQL 은
비superuser 의 `LOAD 'age'` 를 거부한다("access to library age is not allowed"). 따라서 앱 role
(agent_kb_rw/ro) 이 AGE 를 쓰려면 서버가 `age` 를 preload 해야 한다. 운영 compose 의 postgres·
postgres-replica `command:` 절에 `-c shared_preload_libraries='age'` (+기존 pgvector 관련 값과
병기 — 콤마 구분) 를 추가하고 **서버 재시작** 이 cutover 의 일부다(TASK.md T5.3).

**LOAD-BEARING — ALTER ROLE search_path (pgbouncer transaction-mode 안전, Phase 4 검증)**: AGE 의
agtype 연산자(`@>` 등 property 매칭)는 **schema-qualify 불가**하고 search_path 로만 해소된다. 앱은
pgbouncer(transaction pooling) 경유라 세션 `SET search_path` 가 풀링 트랜잭션 간 유지 안 될 수 있다.
그래서 본 마이그레이션이 `ALTER ROLE agent_kb_rw/ro SET search_path = ag_catalog, "$user", public`
로 **role 기본값**을 박아, startup·DISCARD ALL 후에도 자동 적용되게 한다(검증: DISCARD ALL 후 @> 동작).
modules/metadata_graph.py 는 추가로 `cypher`·`agtype` 를 `ag_catalog.` 정규화 + 방어적 `SET search_path`
(직접/superuser 연결용) 를 병행한다.

**create_vlabel/create_elabel 시그니처**: `(graph_name cstring, label_name cstring)` — `name` 아님.
literal 은 unknown→cstring 으로 암묵 캐스트되나 변수는 `::cstring` 명시 캐스트 필요. `create_graph`
는 `(name)`. (Phase 1a 에서 시그니처 확인.)

비파괴 추가(신규 확장·그래프·라벨) — FUNCTION.md §12 사전 승인 범위. downgrade=그래프 drop(관계형 SSOT 무영향).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0025_age_metadata_graph"
down_revision: Union[str, None] = "0024_table_relationships"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- 1) AGE 확장 + 세션 로드 + search_path
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- 2) metadata_kb 그래프 (멱등)
DO $mg$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM ag_catalog.ag_graph WHERE name = 'metadata_kb') THEN
        PERFORM ag_catalog.create_graph('metadata_kb');
    END IF;
END
$mg$;

-- 3) vlabel/elabel 사전 선언 (멱등 — 동적 라벨 생성 회피로 GRANT 결정성 확보)
DO $lbl$
DECLARE
    v text;
    gid oid;
BEGIN
    SELECT graphid INTO gid FROM ag_catalog.ag_graph WHERE name = 'metadata_kb';
    FOREACH v IN ARRAY ARRAY['Product','Datasource','Schema','Table','Column','GlossaryTerm']
    LOOP
        IF NOT EXISTS (SELECT 1 FROM ag_catalog.ag_label WHERE graph = gid AND name = v::name) THEN
            PERFORM ag_catalog.create_vlabel('metadata_kb'::cstring, v::cstring);
        END IF;
    END LOOP;
    FOREACH v IN ARRAY ARRAY['USES','HAS_SCHEMA','HAS_TABLE','HAS_COLUMN','REFERENCES','RELATED_TERM','DESCRIBES']
    LOOP
        IF NOT EXISTS (SELECT 1 FROM ag_catalog.ag_label WHERE graph = gid AND name = v::name) THEN
            PERFORM ag_catalog.create_elabel('metadata_kb'::cstring, v::cstring);
        END IF;
    END LOOP;
END
$lbl$;

-- 4) GRANT (role 존재 가드 — DEPLOY TRAP)
DO $grant$
BEGIN
    -- 공통: 스키마 USAGE + ag_catalog 함수 EXECUTE (cypher 등)
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_kb_rw') THEN
        GRANT USAGE ON SCHEMA ag_catalog, metadata_kb TO agent_kb_rw;
        GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA ag_catalog TO agent_kb_rw;
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA metadata_kb TO agent_kb_rw;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA metadata_kb TO agent_kb_rw;
        ALTER DEFAULT PRIVILEGES IN SCHEMA metadata_kb
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO agent_kb_rw;
        ALTER DEFAULT PRIVILEGES IN SCHEMA metadata_kb
            GRANT USAGE, SELECT ON SEQUENCES TO agent_kb_rw;
        -- LOAD-BEARING (pgbouncer transaction-mode): AGE 의 agtype 연산자(@> 등)는 search_path 로만
        -- 해소된다. role 기본 search_path 에 ag_catalog 를 넣어 풀링 세션 startup 마다(DISCARD ALL 후에도)
        -- 자동 적용 — 앱이 매 트랜잭션 SET 할 필요 없음. 기존 관계형(public) 경로는 영향 없음(이름 충돌 없음).
        ALTER ROLE agent_kb_rw SET search_path = ag_catalog, "$user", public;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_kb_ro') THEN
        GRANT USAGE ON SCHEMA ag_catalog, metadata_kb TO agent_kb_ro;
        GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA ag_catalog TO agent_kb_ro;
        GRANT SELECT ON ALL TABLES IN SCHEMA metadata_kb TO agent_kb_ro;
        ALTER DEFAULT PRIVILEGES IN SCHEMA metadata_kb
            GRANT SELECT ON TABLES TO agent_kb_ro;
        ALTER ROLE agent_kb_ro SET search_path = ag_catalog, "$user", public;
    END IF;
END
$grant$;
"""

DOWNGRADE_SQL = r"""
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
DO $dg$
BEGIN
    IF EXISTS (SELECT 1 FROM ag_catalog.ag_graph WHERE name = 'metadata_kb') THEN
        PERFORM ag_catalog.drop_graph('metadata_kb', true);
    END IF;
END
$dg$;
-- 확장 자체는 보존(다른 그래프가 있을 수 있음). 완전 제거는 수동: DROP EXTENSION age CASCADE;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
