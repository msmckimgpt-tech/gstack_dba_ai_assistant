"""routine_objects — 함수·프로시저 SSOT + AGE Routine 라벨 + 분석 run 사용자 지침 (feature-0016 graph-funcproc-uxfix).

요청(2026-07-03, REQ-20260703-graph-funcproc-uxfix): 그래프 뷰에 **함수 & 프로시저 노드**를 구성하고
분석·관계(참조 테이블)도 함께 구성한다. + 'AI 능동 분석' hover 프롬프트 입력(사용자 지침)을 run 에 저장.

  1. `routine_objects` (관계형 SSOT, ADR-013): insight-worker 가 데이터소스의
     INFORMATION_SCHEMA.ROUTINES/PARAMETERS(MySQL·MSSQL 공통 뷰)를 introspect 해 upsert 한다.
     schema_name 은 스키마-slot 규약(ADR-007: MySQL=schema / MSSQL=DB명)을 따른다.
     referenced_tables 는 정의(definition) 파싱으로 추출한 [{fqn, kind}] — kind ∈ read|write.
  2. AGE `metadata_kb` 라벨 사전 선언(0025 동형 — 런타임 동적 라벨 생성 금지):
     vlabel `Routine` + elabel `HAS_ROUTINE`(Schema→Routine)·`ROUTINE_USES`(Routine→Table).
  3. `node_analysis_runs.user_prompt` (ADR-014): 'AI 능동 분석' hover 프롬프트로 입력한 사용자
     지침 — 앵커 토큰 합류 + LLM payload user_intent 로 주입된다.

비파괴 추가(신규 테이블·라벨·컬럼) — FUNCTION.md §12 사전 승인 범위. downgrade=DROP(관계형 SSOT
routine_objects 는 재-introspect 로 재생성 가능, 그래프 라벨은 투영이라 무손실).

**DEPLOY TRAP (0028/0025 동형)**: superuser 적용이라 신규 테이블에 명시 GRANT 필수(agent_kb_rw/ro).
AGE 라벨 테이블은 0025 의 ALTER DEFAULT PRIVILEGES 로 커버되나 belt-and-suspenders 로 재-GRANT.
**적용 순서**: 0025 가 선행(AGE cutover 완료 전제) — 본 리비전은 metadata_kb 그래프 존재를 가드한다.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0034_routine_objects"
down_revision: Union[str, None] = "0033_llm_usage_step_gap"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- ── 1) 함수·프로시저 관계형 SSOT ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS routine_objects (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key         varchar(96)  NOT NULL DEFAULT 'common',
    datasource_key    varchar(96)  NOT NULL DEFAULT '',
    schema_name       varchar(256) NOT NULL,
    routine_name      varchar(256) NOT NULL,
    routine_type      varchar(16)  NOT NULL DEFAULT 'procedure',
    description       text         NOT NULL DEFAULT '',
    params            text         NOT NULL DEFAULT '',
    returns           varchar(256) NOT NULL DEFAULT '',
    definition_hash   varchar(64)  NOT NULL DEFAULT '',
    referenced_tables jsonb        NOT NULL DEFAULT '[]'::jsonb,
    source_run_id     varchar(64),
    created_at        timestamptz  NOT NULL DEFAULT now(),
    updated_at        timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ux_routine_objects_ident UNIQUE (scope_key, schema_name, routine_name, routine_type),
    CONSTRAINT ck_routine_objects_type CHECK (routine_type IN ('function', 'procedure'))
);
CREATE INDEX IF NOT EXISTS ix_routine_objects_scope_schema
    ON routine_objects (scope_key, schema_name);
CREATE INDEX IF NOT EXISTS ix_routine_objects_updated
    ON routine_objects (updated_at);

DROP TRIGGER IF EXISTS trg_routine_objects_updated_at ON routine_objects;
CREATE TRIGGER trg_routine_objects_updated_at
    BEFORE UPDATE ON routine_objects
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── 2) AI 능동 분석 run 사용자 지침 (hover 프롬프트, ADR-014) ────────────────
ALTER TABLE node_analysis_runs ADD COLUMN IF NOT EXISTS user_prompt text;

-- ── 3) AGE metadata_kb 라벨 선언 (0025 동형·멱등, 그래프 존재 가드) ─────────
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
    FOREACH v IN ARRAY ARRAY['Routine']
    LOOP
        IF NOT EXISTS (SELECT 1 FROM ag_catalog.ag_label WHERE graph = gid AND name = v::name) THEN
            PERFORM ag_catalog.create_vlabel('metadata_kb'::cstring, v::cstring);
        END IF;
    END LOOP;
    FOREACH v IN ARRAY ARRAY['HAS_ROUTINE','ROUTINE_USES']
    LOOP
        IF NOT EXISTS (SELECT 1 FROM ag_catalog.ag_label WHERE graph = gid AND name = v::name) THEN
            PERFORM ag_catalog.create_elabel('metadata_kb'::cstring, v::cstring);
        END IF;
    END LOOP;
END
$lbl$;

-- ── 4) GRANT (DEPLOY TRAP — 0028/0025 동형, role 존재 가드) ─────────────────
--    metadata_kb 스키마 GRANT 는 스키마 존재 가드(§3 의 그래프 미생성 graceful 과 정합 —
--    drop_graph 후 재적용 등에서 'schema does not exist' hard-fail 방지, §18.8 패널 MINOR).
DO $grant$
DECLARE
    has_mkb boolean := EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'metadata_kb');
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_kb_rw') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON routine_objects TO agent_kb_rw;
        IF has_mkb THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA metadata_kb TO agent_kb_rw;
        END IF;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_kb_ro') THEN
        GRANT SELECT ON routine_objects TO agent_kb_ro;
        IF has_mkb THEN
            GRANT SELECT ON ALL TABLES IN SCHEMA metadata_kb TO agent_kb_ro;
        END IF;
    END IF;
END
$grant$;
"""

DOWNGRADE_SQL = r"""
ALTER TABLE node_analysis_runs DROP COLUMN IF EXISTS user_prompt;
DROP TABLE IF EXISTS routine_objects;
-- AGE 라벨은 보존(투영 데이터 무손실 — 완전 제거는 수동: ag_catalog.drop_label).
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
