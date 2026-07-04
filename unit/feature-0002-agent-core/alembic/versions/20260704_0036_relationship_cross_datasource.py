"""relationship_cross_datasource — table_relationships 크로스-데이터소스 지원 (feature-0016 crossds-rel, ADR-019).

Phase B(사용자 3대 개선 中 B): 서로 다른 데이터소스 간 관계를 표현. 엔드포인트별 datasource 키 2컬럼 추가 +
UNIQUE 를 7-col 로 진화(cross-ds edge 동일 scope/FQN·다른 ds 충돌 제거) + source CHECK 에 'manual' 추가.
크로스-ds 후보는 Phase C(ADR-018) 의미 시그니처 임베딩 유사도로 발굴(source='inferred', status='candidate') —
프로브 검증 불가(교차 엔드포인트 조인 불가)라 fetch_probe_candidates 가 src_ds=tgt_ds 만 대상(영구 candidate).
승격은 대화 JOIN 성공 또는 manual 큐레이션(source='manual' → trusted)만.

비파괴 추가 — FUNCTION.md §12 사전 승인 범위. 기존 intra-ds 행은 backfill 로 src_ds=tgt_ds=datasource_key →
7-col UNIQUE 가 5-col 유일성을 refine(신규 위반 불가). downgrade=cross-ds 행 제거 후 5-col UNIQUE·4값 CHECK 복원.
**적용 순서**: 0035(Phase C 임베딩) 선행 전제(크로스-ds 추론이 그 임베딩을 소비).

live 안전(14,889-row): ADD COLUMN 상수 DEFAULT '' 는 PG16 카탈로그 전용(attmissingval, O(1), rewrite 없음).
UNIQUE/CHECK DROP+ADD 는 backfill 후 위반 0(refine). migrate-lint escape 는 **Python 주석**으로 서명(아래 upgrade()).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0036_relationship_cross_datasource"
down_revision: Union[str, None] = "0035_rag_objects_semantic_cluster"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- 1) 엔드포인트별 datasource 키 (비파괴, 상수 default '' → 카탈로그 전용 변경, 14889-row rewrite 없음)
ALTER TABLE public.table_relationships
    ADD COLUMN IF NOT EXISTS source_datasource_key varchar(64) NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS target_datasource_key varchar(64) NOT NULL DEFAULT '';

-- 2) 백필: 기존 edge 는 전부 intra-ds → 양 끝점 = 행의 단일 datasource_key
UPDATE public.table_relationships
   SET source_datasource_key = datasource_key,
       target_datasource_key = datasource_key
 WHERE source_datasource_key = '' AND target_datasource_key = '';

-- 3) UNIQUE 진화: ds 두 컬럼을 키에 편입 → cross-ds edge(동일 scope/FQN·다른 ds) 충돌 제거.
--    intra-ds 행은 src_ds=tgt_ds 라 5-col 유일성 보존(refine, 신규 위반 불가).
ALTER TABLE public.table_relationships DROP CONSTRAINT IF EXISTS ux_table_relationships_edge;
ALTER TABLE public.table_relationships
    ADD CONSTRAINT ux_table_relationships_edge
    UNIQUE (scope_key, source_datasource_key, source_table_fqn, source_column,
            target_datasource_key, target_table_fqn, target_column);

-- 4) source CHECK 에 'manual'(사람 큐레이션 — cross-ds 승격 경로) 추가.
ALTER TABLE public.table_relationships DROP CONSTRAINT IF EXISTS ck_table_relationships_source;
ALTER TABLE public.table_relationships
    ADD CONSTRAINT ck_table_relationships_source
    CHECK (source IN ('fk_introspect', 'conversation', 'llm_insight', 'inferred', 'manual'));

-- 5) 엔드포인트별 ds 조회 인덱스(크로스-ds 추론/투영 scope 매핑).
CREATE INDEX IF NOT EXISTS ix_table_relationships_src_ds
    ON public.table_relationships (scope_key, source_datasource_key);
CREATE INDEX IF NOT EXISTS ix_table_relationships_tgt_ds
    ON public.table_relationships (scope_key, target_datasource_key);
-- NOTE: 기존 테이블 ADD COLUMN/CONSTRAINT 은 테이블-레벨 GRANT 자동 상속 → 신규 GRANT 불요(0026 규약).
"""

DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS public.ix_table_relationships_tgt_ds;
DROP INDEX IF EXISTS public.ix_table_relationships_src_ds;
-- 원복 전 cross-ds 행 제거 — 5-col UNIQUE 복원 시 충돌 방지(cross-ds 는 inferred/manual 뿐, 재추론 재생성 가능).
DELETE FROM public.table_relationships WHERE source_datasource_key <> target_datasource_key;
ALTER TABLE public.table_relationships DROP CONSTRAINT IF EXISTS ck_table_relationships_source;
ALTER TABLE public.table_relationships
    ADD CONSTRAINT ck_table_relationships_source
    CHECK (source IN ('fk_introspect', 'conversation', 'llm_insight', 'inferred'));
ALTER TABLE public.table_relationships DROP CONSTRAINT IF EXISTS ux_table_relationships_edge;
ALTER TABLE public.table_relationships
    ADD CONSTRAINT ux_table_relationships_edge
    UNIQUE (scope_key, source_table_fqn, source_column, target_table_fqn, target_column);
ALTER TABLE public.table_relationships
    DROP COLUMN IF EXISTS target_datasource_key,
    DROP COLUMN IF EXISTS source_datasource_key;
"""


def upgrade() -> None:
    # migrate-lint: allow drop_constraint — UNIQUE/CHECK 재정의는 컬럼추가 refine(intra-ds 위반0, backfill 후) + downgrade 원복 (서명: crossds-rel 2026-07-04)
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
