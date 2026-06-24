"""public.table_descriptions + public.column_descriptions — 테이블/컬럼 설명 사전 (ITEM-11 Phase 2).

ROADMAP dba-ai-nl2sql ITEM-11 Phase 2(semantic-lite). 사람이 작성한 테이블·컬럼 의미 설명을
ds-scoped(scope_key, enum_dictionary 동일 컨벤션) 로 저장하고 두 경로로 주입한다:
  (B) _build_knowledge_context 가 질문 매칭 행을 grounding 섹션에 datamark 주입.
  (A) describe_table 가 native COLUMN_COMMENT 가 빈 컬럼을 KB 설명으로 오버레이
      (MSSQL 빈 comment gap — dialects.describe_columns row[6]='' 해소).

**DEPLOY TRAP (load-bearing — 0013 kb_glossary 동형)**: superuser 로 적용되므로 신규 테이블에
**명시 GRANT 를 넣지 않으면** ask-worker/web(agent_kb_rw)가 upsert 시 permission denied,
RO(agent_kb_ro) 읽기도 막힌다. 아래 GRANT 필수. agent_kb_schema.sql §8a/§10 과 정합.

신규 테이블 CREATE + 인덱스 + 트리거 + GRANT 만(기존 데이터 무손실, 안전·멱등 — IF NOT EXISTS).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017_table_column_descriptions"
down_revision: Union[str, None] = "0016_core_conv_is_group"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
CREATE TABLE IF NOT EXISTS table_descriptions (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key   varchar(96)  NOT NULL DEFAULT 'common',
    schema_name varchar(128) NOT NULL DEFAULT '',
    table_name  varchar(128) NOT NULL,
    description text         NOT NULL,
    source      varchar(24)  NOT NULL DEFAULT 'manual',
    created_by  varchar(64),
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ux_table_descriptions_scope_tbl
        UNIQUE (scope_key, schema_name, table_name)
);
CREATE INDEX IF NOT EXISTS ix_table_descriptions_scope ON table_descriptions (scope_key);
DROP TRIGGER IF EXISTS trg_table_descriptions_updated_at ON table_descriptions;
CREATE TRIGGER trg_table_descriptions_updated_at
    BEFORE UPDATE ON table_descriptions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS column_descriptions (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key   varchar(96)  NOT NULL DEFAULT 'common',
    schema_name varchar(128) NOT NULL DEFAULT '',
    table_name  varchar(128) NOT NULL,
    column_name varchar(128) NOT NULL,
    description text         NOT NULL,
    source      varchar(24)  NOT NULL DEFAULT 'manual',
    created_by  varchar(64),
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ux_column_descriptions_scope_col
        UNIQUE (scope_key, schema_name, table_name, column_name)
);
CREATE INDEX IF NOT EXISTS ix_column_descriptions_scope ON column_descriptions (scope_key);
CREATE INDEX IF NOT EXISTS ix_column_descriptions_col
    ON column_descriptions (scope_key, table_name, column_name);
DROP TRIGGER IF EXISTS trg_column_descriptions_updated_at ON column_descriptions;
CREATE TRIGGER trg_column_descriptions_updated_at
    BEFORE UPDATE ON column_descriptions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 명시 GRANT (DEPLOY TRAP — superuser 적용이라 DEFAULT PRIVILEGES 가 커버 못 함).
-- 역할 부재(미부트스트랩 환경)에서도 멱등하도록 존재할 때만 GRANT.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_kb_rw') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE
            ON table_descriptions, column_descriptions TO agent_kb_rw;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agent_kb_rw;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_kb_ro') THEN
        GRANT SELECT ON table_descriptions, column_descriptions TO agent_kb_ro;
    END IF;
END $$;
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS table_descriptions;
DROP TABLE IF EXISTS column_descriptions;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
