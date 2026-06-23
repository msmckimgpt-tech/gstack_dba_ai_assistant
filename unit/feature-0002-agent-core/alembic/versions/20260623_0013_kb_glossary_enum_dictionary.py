"""public.kb_glossary + public.enum_dictionary — 용어사전 + ENUM 코드사전 (ITEM-10).

ROADMAP dba-ai-nl2sql ITEM-10(semantic-lite). 도메인 용어 정의·컬럼 열거형 코드↔라벨
매핑을 ds-scoped(scope_key, fact_entries 동일 컨벤션) 로 저장하고, _build_knowledge_context
가 질문/스키마 매칭 시 프롬프트에 datamark 주입한다.

**DEPLOY TRAP (load-bearing — 0011 llm_provider_health 동형)**: superuser 로 적용되므로
신규 테이블에 **명시 GRANT 를 넣지 않으면** ask-worker/web(agent_kb_rw)가 upsert 시
permission denied. 아래 GRANT 필수. agent_kb_schema.sql §8/§10 과 정합.

신규 테이블 CREATE + 인덱스 + 트리거 + GRANT 만(기존 데이터 무손실, 안전·멱등).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_kb_glossary_enum_dictionary"
down_revision: Union[str, None] = "0012_group_conversation_members"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
CREATE TABLE IF NOT EXISTS kb_glossary (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key   varchar(96)  NOT NULL DEFAULT 'common',
    term        varchar(128) NOT NULL,
    definition  text         NOT NULL,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ux_kb_glossary_scope_term UNIQUE (scope_key, term)
);
CREATE INDEX IF NOT EXISTS ix_kb_glossary_scope ON kb_glossary (scope_key);
CREATE INDEX IF NOT EXISTS ix_kb_glossary_term_trgm ON kb_glossary USING gin (term gin_trgm_ops);
DROP TRIGGER IF EXISTS trg_kb_glossary_updated_at ON kb_glossary;
CREATE TRIGGER trg_kb_glossary_updated_at
    BEFORE UPDATE ON kb_glossary
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS enum_dictionary (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key   varchar(96)  NOT NULL DEFAULT 'common',
    schema_name varchar(128) NOT NULL DEFAULT '',
    table_name  varchar(128) NOT NULL,
    column_name varchar(128) NOT NULL,
    code        varchar(128) NOT NULL,
    label       text         NOT NULL,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ux_enum_dictionary_scope_col_code
        UNIQUE (scope_key, schema_name, table_name, column_name, code)
);
CREATE INDEX IF NOT EXISTS ix_enum_dictionary_scope ON enum_dictionary (scope_key);
CREATE INDEX IF NOT EXISTS ix_enum_dictionary_col
    ON enum_dictionary (scope_key, table_name, column_name);
DROP TRIGGER IF EXISTS trg_enum_dictionary_updated_at ON enum_dictionary;
CREATE TRIGGER trg_enum_dictionary_updated_at
    BEFORE UPDATE ON enum_dictionary
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- 명시 GRANT (DEPLOY TRAP — superuser 적용이라 DEFAULT PRIVILEGES 가 커버 못 함).
GRANT SELECT, INSERT, UPDATE, DELETE ON kb_glossary, enum_dictionary TO agent_kb_rw;
GRANT SELECT                        ON kb_glossary, enum_dictionary TO agent_kb_ro;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agent_kb_rw;
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS kb_glossary;
DROP TABLE IF EXISTS enum_dictionary;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
