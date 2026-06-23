"""sample_queries.embedding vector(1536) → vector(1024) 차원 정렬 (ITEM-02 fix).

0014 가 sample_queries.embedding 을 vector(1536) 로 만들었으나, 실제 임베딩 모델은
titan-embed v2 = **1024-dim**(AGENT_KB_EMBEDDING_DIM=1024, texts 정본=alembic 0001 의
vector(1024)). 1536 컬럼에 1024 벡터 INSERT 시 차원 불일치 런타임 실패 → 1024 로 정렬.

경로 B(로컬 1024-dim 임베딩, bge-m3 등) 전제. 컬럼이 **비어있어**(실 임베딩 0건 — titan 다운)
DROP+ADD 로 안전(데이터 손실 없음). ivfflat 인덱스는 컬럼과 함께 drop → 재생성.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0015_sample_queries_embed_dim_1024"
down_revision: Union[str, None] = "0014_sample_queries_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# TASK-0306: 멱등 가드. 종전엔 무조건 DROP+ADD 라 (이미 1024 인) 적재 임베딩을 손실시킬 수 있었다
# (라이브 split-brain 정합 시 위험으로 식별). 컬럼이 이미 vector(1024) 면 재생성을 skip(데이터 보존),
# 1536(또는 부재)일 때만 정렬 — fresh-install 의 1536→1024 정렬 동작은 그대로 유지된다.
UPGRADE_SQL = r"""
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid AND c.relname = 'sample_queries'
        WHERE a.attname = 'embedding' AND a.attnum > 0 AND NOT a.attisdropped
          AND format_type(a.atttypid, a.atttypmod) = 'vector(1024)'
    ) THEN
        DROP INDEX IF EXISTS ix_sample_queries_embedding_ivfflat;
        ALTER TABLE sample_queries DROP COLUMN IF EXISTS embedding;
        ALTER TABLE sample_queries ADD COLUMN embedding vector(1024);
        CREATE INDEX ix_sample_queries_embedding_ivfflat
            ON sample_queries USING ivfflat (embedding vector_cosine_ops) WITH (lists = 32)
            WHERE embedding IS NOT NULL;
    END IF;
END $$;
"""

DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS ix_sample_queries_embedding_ivfflat;
ALTER TABLE sample_queries DROP COLUMN IF EXISTS embedding;
ALTER TABLE sample_queries ADD COLUMN embedding vector(1536);
CREATE INDEX IF NOT EXISTS ix_sample_queries_embedding_ivfflat
    ON sample_queries USING ivfflat (embedding vector_cosine_ops) WITH (lists = 32)
    WHERE embedding IS NOT NULL;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
