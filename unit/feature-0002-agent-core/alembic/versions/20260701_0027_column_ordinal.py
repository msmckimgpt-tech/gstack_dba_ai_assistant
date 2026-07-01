"""column_ordinal — column_descriptions.ordinal (feature-0016-metadata-graph graphux5).

그래프 뷰에서 Column(회색) 노드를 Table(청색) 노드 하단에 **실제 스키마 순서(ordinal)** 로 세로 정렬하기
위해, 관계형 SSOT 인 column_descriptions 에 컬럼 순서를 저장한다. AGE `metadata_kb` 그래프의 Column 정점은
이 값의 투영이며 metadata_graph.sync_column 이 전달한다(재생성 가능). UI(Cytoscape)·AI 가 동일 ordinal 공유.

- 비파괴 additive (ADD COLUMN nullable) — expand-safe (CONVENTIONS §12, migrate-lint 통과). contract 없음.
- 기존행 backfill: 부트스트랩 골격 저장은 dialect.describe_columns(= ORDER BY ORDINAL_POSITION)순으로 각
  컬럼을 순차 INSERT 하므로 삽입순(id ASC) ≈ DDL 순. 테이블 그룹별 row_number(ORDER BY id)로 근사 ordinal 을
  채운다(NULL 행만). 이후 부트스트랩 저장은 명시 ordinal 을 전송해 정확화(app.py POST /columns → upsert_column_desc).
- downgrade=DROP COLUMN (비파괴 역전).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0027_column_ordinal"
down_revision: Union[str, None] = "0026_relationship_reinforcement"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE column_descriptions ADD COLUMN IF NOT EXISTS ordinal integer;

-- 기존행 근사 backfill (NULL 만): 테이블 그룹 내 삽입순(id) → 1-based ordinal.
--   부트스트랩 저장이 DDL(ORDINAL_POSITION)순으로 순차 INSERT 하므로 삽입순 ≈ DDL순.
--   이후 부트스트랩 저장은 명시 ordinal 을 전송해 정확화한다(근사값을 덮어씀).
UPDATE column_descriptions AS cd
   SET ordinal = sub.rn
  FROM (
        SELECT id,
               row_number() OVER (
                   PARTITION BY scope_key, schema_name, table_name
                   ORDER BY id
               ) AS rn
          FROM column_descriptions
       ) AS sub
 WHERE cd.id = sub.id
   AND cd.ordinal IS NULL;
"""

DOWNGRADE_SQL = r"""
ALTER TABLE column_descriptions DROP COLUMN IF EXISTS ordinal;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
