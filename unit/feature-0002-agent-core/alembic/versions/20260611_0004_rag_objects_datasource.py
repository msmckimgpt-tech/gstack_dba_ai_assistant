"""rag_objects.datasource_key — RAG 객체 인덱스의 datasource 스코프 (TASK-0219).

데이터소스 추가(TASK-0205/0206)로 insight fact 키가 `{source}:ds:{ds_key}:{suffix}` 로 datasource-스코프
됐으나, RAG 객체 인덱스(public.rag_objects)는 이를 따라가지 못해 ds-스코프 객체가 누락/오염(`dswinsqldbo`)
됐다. datasource_key 컬럼을 추가해 객체-레벨 grounding 이 datasource 별로 정상 인덱싱·검색되게 한다.

object_key 자체에 ds 접두(`winsql:dbo.t`)를 보존하므로 기존 UNIQUE 제약 (conversation_id, scope_key,
object_type, object_key) 은 변경 불요(cross-ds 충돌 없음). datasource_key 는 검색 필터·가시성용.

revision 이 스키마 권위. 본 마이그는 컬럼 ADD + 필터 인덱스만(데이터 무손실, 안전).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_rag_objects_datasource"
down_revision: Union[str, None] = "0003_ask_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE public.rag_objects
    ADD COLUMN IF NOT EXISTS datasource_key character varying(64);

-- 검색 시 active datasource 로 필터(ds-스코프 객체 격리). NULL = 기본(no-ds) 객체.
CREATE INDEX IF NOT EXISTS ix_rag_objects_datasource
    ON public.rag_objects (datasource_key);
"""

DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS public.ix_rag_objects_datasource;
ALTER TABLE public.rag_objects DROP COLUMN IF EXISTS datasource_key;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
