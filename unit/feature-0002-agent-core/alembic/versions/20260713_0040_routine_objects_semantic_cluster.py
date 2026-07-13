"""routine_objects_semantic_cluster — 함수·프로시저를 의미 클러스터링에 편입 (feature-0016 content-cluster, TASK 20260713T1059).

§55/0035(rag_objects semantic cluster)의 routine 판. 카테고리(sim-group) 밴드가 "컨텐츠 단위"로
묶이려면 루틴도 시그니처(이름+파라미터+반환형+touch 테이블+능동 분석문) 임베딩 → DB 단위 합동
클러스터링(테이블과 같은 cluster id 공간) 대상이어야 한다 — 지금은 routine_objects 에 컬럼이 없어
클러스터링 밖(이름 affix 그룹만)이라는 진단(RC3, cc_data_main 루틴 300 > 테이블 255).

비파괴 추가(nullable 3컬럼 + 인덱스 2, 0035 동형) — 기존 introspect/sync 경로 무영향.
downgrade=DROP(클러스터는 재계산 가능·무손실).

  - `signature_text_hash` character(64): 루틴 시그니처 텍스트 sha256 (texts join 키 + 변경감지 키).
  - `semantic_cluster_id` integer: DB(effective schema) 단위 합동 클러스터 id — rag_objects 와 공유 공간
    (NULL=미클러스터/싱글턴 → 프론트 affix 폴백).
  - `semantic_cluster_label` varchar(128): 클러스터 라벨(LLM 컨텐츠 라벨 or commonAffix 폴백).

**live 안전**: nullable·default 없음 → PG16 카탈로그 전용 변경(테이블 rewrite 없음, ~16k행).
migrate-lint expand-safe(순수 additive). 적용 순서: 0034(routine_objects)·0035 선행 전제.
신규 컬럼은 기존 테이블 GRANT 자동 상속(0026 규약).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0040_routine_objects_semantic_cluster"
down_revision: Union[str, None] = "0039_enum_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- 1) 시그니처 해시 + 의미 클러스터 (비파괴, nullable·no-default → 카탈로그 전용 변경, rewrite 없음)
ALTER TABLE public.routine_objects
    ADD COLUMN IF NOT EXISTS signature_text_hash character(64),
    ADD COLUMN IF NOT EXISTS semantic_cluster_id integer,
    ADD COLUMN IF NOT EXISTS semantic_cluster_label character varying(128);

-- 2) 시그니처 백필 스캔(WHERE signature_text_hash IS NULL) + texts join 키 (0035 동형).
CREATE INDEX IF NOT EXISTS ix_routine_objects_signature_hash
    ON public.routine_objects (signature_text_hash);

-- 3) 프론트 클러스터 read / scope 별 집계 partial index (NULL=미클러스터 제외 → 인덱스 슬림).
CREATE INDEX IF NOT EXISTS ix_routine_objects_semantic_cluster
    ON public.routine_objects (scope_key, datasource_key, semantic_cluster_id)
    WHERE semantic_cluster_id IS NOT NULL;
-- NOTE: 기존 테이블 ADD COLUMN 은 테이블-레벨 GRANT 자동 상속 → 신규 GRANT 불요 (0026 규약).
"""

DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS public.ix_routine_objects_semantic_cluster;
DROP INDEX IF EXISTS public.ix_routine_objects_signature_hash;
ALTER TABLE public.routine_objects
    DROP COLUMN IF EXISTS semantic_cluster_label,
    DROP COLUMN IF EXISTS semantic_cluster_id,
    DROP COLUMN IF EXISTS signature_text_hash;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
