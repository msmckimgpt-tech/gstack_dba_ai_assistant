"""db_objects — 역할 기반 DB 객체 SSOT + AGE DbObject 라벨 (feature-0040 db-object-explorer).

요청(2026-08-12, REQ-20260812-db-object-explorer): assistant 가 DB 내부 구조를 탐색할 때
**트리거·이벤트·SQL Agent 작업 등 실제 객체**를 탐색하는 도구가 없다 → 도구를 제공하고,
**그래프 뷰에서도 그 객체들을 배치·참조·분석**할 수 있게 한다.

  1. `db_objects` (관계형 SSOT, ADR-DBOBJ-0001): insight-worker 가 데이터소스의 카탈로그를
     **역할 축**(view/trigger/schedule/alias/generator — `modules/db_object_roles.py`)으로
     introspect 해 upsert 한다. `routine_objects`(0034) 의 자매 테이블이며 같은 규약을 따른다:
     schema_name 은 스키마-slot(ADR-007: MySQL=schema / MSSQL=DB명),
     referenced_tables 는 정의 파싱으로 얻은 [{fqn, kind}] (kind ∈ read|write).

     **`routine` 은 이 테이블에 넣지 않는다** — 0034 의 `routine_objects` 가 이미 소유하며,
     잘 검증된 서브시스템을 새 테이블로 이관하는 것은 회귀 위험만 크고 얻는 것이 없다.
     taxonomy 는 6역할 전부를 선언하되 저장은 두 테이블로 나뉜다(db_object_roles.OWNED_ELSEWHERE).

     **UNIQUE 키에 `sql_schema` 포함 (routine_objects 대비 개선)**: MSSQL 은 저장 slot 이 DB명
     이라 `(scope, schema_name, name)` 만으로는 같은 DB 안 서로 다른 SQL 스키마의 동명 객체
     (`dbo.v_stat` / `report.v_stat`)가 충돌한다. routine_objects 는 이 한계를 수용했지만
     (기존 데이터 호환), 신규 테이블에는 처음부터 실 SQL 스키마를 키에 넣어 구조적으로 막는다.
     MySQL 은 schema==DB 라 `sql_schema=''` 로 두면 종전과 동일하게 동작한다.

  2. AGE `metadata_kb` 라벨 사전 선언(0025/0034 동형 — 런타임 동적 라벨 생성 금지):
     vlabel `DbObject` + elabel
       - `HAS_OBJECT`  (Schema→DbObject)   — 소속
       - `OBJECT_USES` (DbObject→Table)    — 정의가 참조하는 테이블(read/write)
       - `OBJECT_ON`   (DbObject→Table)    — **소유 관계**(트리거가 걸린 테이블, 별칭의 대상)
     `OBJECT_ON` 을 `OBJECT_USES` 와 분리하는 이유: 트리거가 "T 에 걸려 있다" 는 것과 "T 를
     읽는다" 는 그래프에서 의미가 다르다. 하나로 합치면 트리거 노드가 대상 테이블과 사용
     테이블 사이에서 구분 불가가 되어, 사용자가 "이 테이블에 뭐가 걸려 있나" 를 물었을 때
     답할 수 없다.

비파괴 추가(신규 테이블·라벨) — FUNCTION.md §12 사전 승인 범위. downgrade=DROP(관계형 SSOT 는
재-introspect 로 재생성 가능, 그래프 라벨은 투영이라 무손실).

**DEPLOY TRAP (0034/0028/0025 동형)**: superuser 적용이라 신규 테이블에 명시 GRANT 필수
(agent_kb_rw/ro). AGE 라벨 테이블은 0025 의 ALTER DEFAULT PRIVILEGES 로 커버되나
belt-and-suspenders 로 재-GRANT. **적용 순서**: 0025(AGE cutover) 선행 — 그래프 미생성 시
라벨 선언은 graceful skip.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0054_db_objects"
down_revision: Union[str, None] = "0053_domain_summaries"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- ── 1) 역할 기반 DB 객체 관계형 SSOT ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS db_objects (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key         varchar(96)  NOT NULL DEFAULT 'common',
    datasource_key    varchar(96)  NOT NULL DEFAULT '',
    schema_name       varchar(256) NOT NULL,              -- 저장 slot (MySQL=schema / MSSQL=DB명)
    sql_schema        varchar(256) NOT NULL DEFAULT '',   -- 실 SQL 스키마 (MySQL=''·MSSQL='dbo' 등)
    object_role       varchar(32)  NOT NULL,              -- view|trigger|schedule|alias|generator
    object_name       varchar(256) NOT NULL,
    object_type       varchar(32)  NOT NULL DEFAULT '',   -- 방언 구체 타입 (VIEW/DML_TRIGGER/EVENT/AGENT_JOB/…)
    owner_object      varchar(512) NOT NULL DEFAULT '',   -- 트리거의 대상 테이블 · 별칭의 대상 객체
    description       text         NOT NULL DEFAULT '',
    attributes        jsonb        NOT NULL DEFAULT '{}'::jsonb,   -- 역할별 속성(시점/이벤트/주기/상태…)
    definition_hash   varchar(64)  NOT NULL DEFAULT '',
    referenced_tables jsonb        NOT NULL DEFAULT '[]'::jsonb,
    source_run_id     varchar(64),
    created_at        timestamptz  NOT NULL DEFAULT now(),
    updated_at        timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ux_db_objects_ident
        UNIQUE (scope_key, schema_name, sql_schema, object_role, object_name),
    CONSTRAINT ck_db_objects_role
        CHECK (object_role IN ('view', 'trigger', 'schedule', 'alias', 'generator'))
);
CREATE INDEX IF NOT EXISTS ix_db_objects_scope_schema
    ON db_objects (scope_key, schema_name);
CREATE INDEX IF NOT EXISTS ix_db_objects_updated
    ON db_objects (updated_at);
-- 그래프 뷰의 역할 필터(kind 토글)가 역할 축으로 조회하므로 보조 인덱스를 둔다.
CREATE INDEX IF NOT EXISTS ix_db_objects_role
    ON db_objects (scope_key, object_role);
-- "이 테이블에 뭐가 걸려 있나" (트리거 owner 역인덱스) — 상세 패널·그래프 OBJECT_ON 조회.
CREATE INDEX IF NOT EXISTS ix_db_objects_owner
    ON db_objects (scope_key, schema_name, owner_object)
    WHERE owner_object <> '';

DROP TRIGGER IF EXISTS trg_db_objects_updated_at ON db_objects;
CREATE TRIGGER trg_db_objects_updated_at
    BEFORE UPDATE ON db_objects
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── 2) AGE metadata_kb 라벨 선언 (0025/0034 동형·멱등, 그래프 존재 가드) ────
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
DO $lbl$
DECLARE
    v text;
    gid oid;
BEGIN
    SELECT graphid INTO gid FROM ag_catalog.ag_graph WHERE name = 'metadata_kb';
    IF gid IS NULL THEN
        RETURN;   -- 그래프 미생성(AGE cutover 전) — 라벨 선언 skip(0025 재적용 시 함께 생성)
    END IF;
    FOREACH v IN ARRAY ARRAY['DbObject']
    LOOP
        IF NOT EXISTS (SELECT 1 FROM ag_catalog.ag_label WHERE graph = gid AND name = v::name) THEN
            PERFORM ag_catalog.create_vlabel('metadata_kb'::cstring, v::cstring);
        END IF;
    END LOOP;
    FOREACH v IN ARRAY ARRAY['HAS_OBJECT','OBJECT_USES','OBJECT_ON']
    LOOP
        IF NOT EXISTS (SELECT 1 FROM ag_catalog.ag_label WHERE graph = gid AND name = v::name) THEN
            PERFORM ag_catalog.create_elabel('metadata_kb'::cstring, v::cstring);
        END IF;
    END LOOP;
END
$lbl$;

-- ── 3) GRANT (DEPLOY TRAP — 0034/0028/0025 동형, role 존재 가드) ────────────
DO $grant$
DECLARE
    has_mkb boolean := EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'metadata_kb');
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_kb_rw') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON db_objects TO agent_kb_rw;
        IF has_mkb THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA metadata_kb TO agent_kb_rw;
        END IF;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_kb_ro') THEN
        GRANT SELECT ON db_objects TO agent_kb_ro;
        IF has_mkb THEN
            GRANT SELECT ON ALL TABLES IN SCHEMA metadata_kb TO agent_kb_ro;
        END IF;
    END IF;
END
$grant$;
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS db_objects;
-- AGE 라벨은 보존(투영 데이터 무손실 — 완전 제거는 수동: ag_catalog.drop_label).
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
