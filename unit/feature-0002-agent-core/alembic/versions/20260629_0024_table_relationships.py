"""table_relationships — 테이블 관계(FK·join) edge 저장소 (feature-0013 relationship-diagrams).

요청(2026-06-29): assistant 가 flow/관계 질문에 mermaid 다이어그램으로 사용자 DB 구조를 답하려면
"관계 데이터" 가 확보되어야 한다. 본 테이블이 introspection(information_schema/sys.foreign_keys)과
대화 학습(실행된 JOIN)의 단일 수렴점이다.

edge = (source_table.source_column → target_table.target_column). 출처(source):
  - fk_introspect: insight worker 가 데이터소스 FK 메타에서 수집(confidence 1.0).
  - conversation : 대화 중 실제 실행된 JOIN 에서 학습(confidence 0.4, FK 미선언 관계 보충).
  - llm_insight  : (예약) LLM 스키마 인사이트 join_hints.

비파괴 추가(신규 테이블) — FUNCTION.md §13 사전 승인 범위. downgrade=DROP.

**DEPLOY TRAP (load-bearing — 0023/0011 동형)**: superuser 로 적용되므로 신규 테이블에 명시 GRANT 를
넣지 않으면 ask-worker/web/insight(agent_kb_rw)가 upsert 시 permission denied. 아래 GRANT 필수.
agent_kb_schema.sql 과 정합.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0024_table_relationships"
down_revision: Union[str, None] = "0023_glossary_role_autoreg"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
CREATE TABLE IF NOT EXISTS table_relationships (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key         varchar(96)  NOT NULL DEFAULT 'common',
    datasource_key    varchar(64)  NOT NULL DEFAULT '',
    source_schema     varchar(128) NOT NULL DEFAULT '',
    source_table      varchar(128) NOT NULL,
    source_column     varchar(128) NOT NULL,
    target_schema     varchar(128) NOT NULL DEFAULT '',
    target_table      varchar(128) NOT NULL,
    target_column     varchar(128) NOT NULL,
    -- schema.table 정규화 키 (UNIQUE/조회용 — schema 빈 경우 table 만)
    source_table_fqn  varchar(257) NOT NULL,
    target_table_fqn  varchar(257) NOT NULL,
    constraint_name   varchar(128) NOT NULL DEFAULT '',
    cardinality       varchar(24)  NOT NULL DEFAULT '',
    source            varchar(24)  NOT NULL DEFAULT 'fk_introspect',
    confidence        real         NOT NULL DEFAULT 1.0,
    source_run_id     varchar(64),
    created_at        timestamptz  NOT NULL DEFAULT now(),
    updated_at        timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ck_table_relationships_source
        CHECK (source IN ('fk_introspect', 'conversation', 'llm_insight')),
    CONSTRAINT ux_table_relationships_edge
        UNIQUE (scope_key, source_table_fqn, source_column, target_table_fqn, target_column)
);
CREATE INDEX IF NOT EXISTS ix_table_relationships_src
    ON table_relationships (scope_key, source_table_fqn);
CREATE INDEX IF NOT EXISTS ix_table_relationships_tgt
    ON table_relationships (scope_key, target_table_fqn);
DROP TRIGGER IF EXISTS trg_table_relationships_updated_at ON table_relationships;
CREATE TRIGGER trg_table_relationships_updated_at
    BEFORE UPDATE ON table_relationships
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── 명시 GRANT (DEPLOY TRAP — superuser 적용이라 DEFAULT PRIVILEGES 가 커버 못 함) ──
GRANT SELECT, INSERT, UPDATE, DELETE ON table_relationships TO agent_kb_rw;
GRANT SELECT                         ON table_relationships TO agent_kb_ro;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agent_kb_rw;
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS table_relationships;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
