"""rag_objects_semantic_cluster — 메타데이터 객체 의미 임베딩·클러스터 (feature-0016 semantic-embed, ADR-013 / DECISIONS ADR-016).

ADR-013 의 "백엔드 시맨틱 클러스터링(컬럼 시그니처·설명 임베딩)" 후속 initiative(Phase C). 프론트 affix
휴리스틱(ADR-013)의 서버측 상위 신호를 만든다. 테이블별 **시그니처 텍스트**(테이블명+설명+컬럼명+역할)를
기존 `texts` 저장소(dedup by text_hash)에 적재 → 기존 embedding 데몬이 bge-m3 1024d 로 자동 임베딩 →
insight-worker 가 scope 별 kNN+union-find 클러스터링 → 결과를 rag_objects 에 역기록.

비파괴 추가(rag_objects 에 nullable 3컬럼 + 인덱스 2개) — FUNCTION.md §12 사전 승인 범위. 기존 pgvector RAG
경로(texts HNSW·kb_retrieval)·category_* 무영향. downgrade=DROP(클러스터는 재계산 가능·무손실).

  - `signature_text_hash` character(64): 테이블 시그니처 텍스트의 sha256 (texts join 키 + 변경감지 키).
  - `semantic_cluster_id` integer: scope 내 의미 클러스터 id (NULL=미클러스터/싱글턴 → 프론트 affix 폴백).
  - `semantic_cluster_label` varchar(128): 클러스터 사람-라벨(commonAffix 서버 포트).

**live 안전(14,889-row rag_objects)**: 세 컬럼 모두 nullable·default 없음 → PG16 카탈로그 전용 변경
(attmissingval, O(1), 테이블 rewrite 없음). 인덱스는 plain CREATE INDEX(수만 행 수십 ms). migrate-lint
expand-safe(순수 additive — ADD COLUMN IF NOT EXISTS + CREATE INDEX, DROP 은 DOWNGRADE 한정).
**적용 순서**: 0025(AGE cutover)·0034(routine) 선행 전제. 신규 컬럼은 기존 테이블 GRANT 자동 상속(0026 규약).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0035_rag_objects_semantic_cluster"
down_revision: Union[str, None] = "0034_routine_objects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- 1) 시그니처 해시 + 의미 클러스터 (비파괴, nullable·no-default → 카탈로그 전용 변경, 14889-row rewrite 없음)
ALTER TABLE public.rag_objects
    ADD COLUMN IF NOT EXISTS signature_text_hash character(64),
    ADD COLUMN IF NOT EXISTS semantic_cluster_id integer,
    ADD COLUMN IF NOT EXISTS semantic_cluster_label character varying(128);

-- 2) 시그니처 백필 스캔(WHERE signature_text_hash IS NULL) + texts join 키. 소형 테이블 plain index.
CREATE INDEX IF NOT EXISTS ix_rag_objects_signature_hash
    ON public.rag_objects (signature_text_hash);

-- 3) 프론트 클러스터 read / scope 별 클러스터 집계 partial index (NULL=미클러스터 제외 → 인덱스 슬림).
CREATE INDEX IF NOT EXISTS ix_rag_objects_semantic_cluster
    ON public.rag_objects (scope_key, datasource_key, semantic_cluster_id)
    WHERE semantic_cluster_id IS NOT NULL;
-- NOTE: 기존 테이블 ADD COLUMN 은 테이블-레벨 GRANT 자동 상속 → 신규 GRANT 불요 (0026 규약).
"""

DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS public.ix_rag_objects_semantic_cluster;
DROP INDEX IF EXISTS public.ix_rag_objects_signature_hash;
ALTER TABLE public.rag_objects
    DROP COLUMN IF EXISTS semantic_cluster_label,
    DROP COLUMN IF EXISTS semantic_cluster_id,
    DROP COLUMN IF EXISTS signature_text_hash;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
