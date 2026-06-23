"""public.sample_queries + public.sample_feedback — 샘플쿼리 few-shot 저장소 + 피드백 flywheel
(ITEM-02+03).

ROADMAP dba-ai-nl2sql ITEM-02(저장소) + ITEM-03(성장 루프). NL↔SQL 샘플을 ds-scoped(scope_key)
+ 임베딩(vector(1536), titan-embed)으로 저장하고, approved∧active 만 질문 유사도 top-K 로
프롬프트 주입. sample_feedback 은 답변 👍/👎/"샘플 등록" 원천 → 승인 큐 경유로 sample_queries
승급(자동학습 금지 — poisoning 방어).

**DEPLOY TRAP (load-bearing — 0011/0013 동형)**: superuser 적용이라 명시 GRANT 필수.

신규 테이블 CREATE + 인덱스(ivfflat partial) + 트리거 + GRANT 만(기존 데이터 무손실, 멱등).
pgvector extension·set_updated_at()·pg_trgm 은 baseline 0001 에 존재.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014_sample_queries_feedback"
down_revision: Union[str, None] = "0013_kb_glossary_enum_dictionary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
CREATE TABLE IF NOT EXISTS sample_queries (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key     varchar(96)  NOT NULL DEFAULT 'common',
    nl_question   text         NOT NULL,
    sql           text         NOT NULL,
    domain        varchar(64)  NOT NULL DEFAULT '',
    weight        integer      NOT NULL DEFAULT 100,
    embedding     vector(1536),
    source_type   varchar(24)  NOT NULL DEFAULT 'manual',
    status        varchar(16)  NOT NULL DEFAULT 'active',
    approved      boolean      NOT NULL DEFAULT false,
    created_by    varchar(64),
    last_validated_at timestamptz,
    created_at    timestamptz  NOT NULL DEFAULT now(),
    updated_at    timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT ux_sample_queries_scope_nl UNIQUE (scope_key, nl_question)
);
CREATE INDEX IF NOT EXISTS ix_sample_queries_scope_appr
    ON sample_queries (scope_key, approved, status);
CREATE INDEX IF NOT EXISTS ix_sample_queries_embedding_ivfflat
    ON sample_queries USING ivfflat (embedding vector_cosine_ops) WITH (lists = 32)
    WHERE embedding IS NOT NULL;
DROP TRIGGER IF EXISTS trg_sample_queries_updated_at ON sample_queries;
CREATE TRIGGER trg_sample_queries_updated_at
    BEFORE UPDATE ON sample_queries
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS sample_feedback (
    id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scope_key          varchar(96)  NOT NULL DEFAULT 'common',
    conversation_id    varchar(128),
    run_id             varchar(64),
    nl_question        text         NOT NULL,
    generated_sql      text,
    vote               varchar(8)   NOT NULL DEFAULT 'up',
    suggested          boolean      NOT NULL DEFAULT false,
    status             varchar(16)  NOT NULL DEFAULT 'pending',
    promoted_sample_id bigint,
    created_by         varchar(64),
    created_at         timestamptz  NOT NULL DEFAULT now(),
    updated_at         timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_sample_feedback_status ON sample_feedback (status, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_sample_feedback_scope ON sample_feedback (scope_key);
DROP TRIGGER IF EXISTS trg_sample_feedback_updated_at ON sample_feedback;
CREATE TRIGGER trg_sample_feedback_updated_at
    BEFORE UPDATE ON sample_feedback
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

GRANT SELECT, INSERT, UPDATE, DELETE ON sample_queries, sample_feedback TO agent_kb_rw;
GRANT SELECT                        ON sample_queries, sample_feedback TO agent_kb_ro;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO agent_kb_rw;
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS sample_feedback;
DROP TABLE IF EXISTS sample_queries;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
