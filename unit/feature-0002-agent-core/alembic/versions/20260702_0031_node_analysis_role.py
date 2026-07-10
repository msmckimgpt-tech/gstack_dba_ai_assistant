"""node_analysis_jobs.role — 그래프 노드 AI 능동 분석의 테이블 역할 분류 (feature-0016 node-role-viz).

요청(2026-07-02): 그래프 뷰에서 AI 능동 분석이 완료된 테이블 노드에 "이 테이블이 수행하는 역할"을
시각적 표식(역할색 칩 + 아이콘 + 범례)으로 명시한다. 그 역할 분류값을 저장하는 컬럼.

  - role: NODE_ROLES(node_analysis.py) 원소 — master|account|transaction|log|mapping|config|stats|etc.
          Table 노드의 done 잡에만 채워진다(Column/Schema/GlossaryTerm 은 NULL 유지).
  - 신규 분석은 LLM 계약(NODE_ANALYSIS_PROMPT "role")이 채우고, 기존 done 행은 insight-worker 틱의
    backfill_roles() 가 휴리스틱(테이블명·분석문 키워드)으로 1회 백필한다 — LLM 재호출 없음.

비파괴 ADD COLUMN — FUNCTION.md §12 사전 승인 범위(비파괴 추가만). downgrade=DROP COLUMN.
GRANT 는 테이블 단위(0028)라 신규 컬럼에 추가 GRANT 불필요.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0031_node_analysis_role"
down_revision: Union[str, None] = "0030_llm_usage_latency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE node_analysis_jobs ADD COLUMN IF NOT EXISTS role varchar(24);
"""

DOWNGRADE_SQL = r"""
ALTER TABLE node_analysis_jobs DROP COLUMN IF EXISTS role;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
