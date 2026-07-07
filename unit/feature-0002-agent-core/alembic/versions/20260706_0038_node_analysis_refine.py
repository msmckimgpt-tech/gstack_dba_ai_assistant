"""node_analysis_refine — DB 단위 분석 재귀 전개(per-seed 앵커) + 빈약 노드 back-refine (feature-0016 §55, REQ-20260706-graph-category-recursive-refine).

사용자 요구 ③: 큰 단위(DB) 'AI 능동 분석' 시 하위 전 노드 분석 + 관련 노드 재귀 + 빈약 노드 후속 보충
(refine). 이를 위해 node_analysis_jobs 에 2컬럼을 비파괴 추가한다:

  - `anchor_key` text NOT NULL DEFAULT '': 이 잡의 관련도 채점 기준 노드(ADR-003 앵커). ''(기본)=run 의
    root(기존 동작 그대로 — 단일 노드 분석 무회귀). 스키마(DB) 단위 run 은 시드마다 자기 자신을 앵커로
    기록해(=per-seed 앵커), 재귀 게이팅이 Schema 명칭이 아닌 각 테이블/루틴 기준으로 동작한다.
  - `pass_no` integer NOT NULL DEFAULT 0: refine 세대. 0=최초 분석. 빈약(thin) 분석 노드를 후속 재귀에서
    보충할 때 **행을 재-pending 하며 pass_no 를 +1** 한다 — UNIQUE(run_id,node_key) 를 바꾸지 않아
    mixed-version(구 워커 ON CONFLICT (run_id,node_key)) 롤링 창에서도 안전(추가 행 없음).

**live 안전**: 두 컬럼 모두 상수 DEFAULT → PG11+ 카탈로그 전용 변경(attmissingval, 테이블 rewrite 없음).
migrate-lint expand-safe(순수 additive). 기존 테이블 ADD COLUMN 은 GRANT 자동 상속(0026 규약).
downgrade=DROP(앵커·세대는 재구성 가능 메타 — 분석문 무손실).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0038_node_analysis_refine"
down_revision: Union[str, None] = "0037_conversation_member_visibility_window"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE public.node_analysis_jobs
    ADD COLUMN IF NOT EXISTS anchor_key text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS pass_no integer NOT NULL DEFAULT 0;
-- NOTE: UNIQUE(run_id,node_key) 불변 — refine 은 신규 행이 아니라 기존 done 행의 재-pending(pass_no+1).
-- NOTE: 기존 테이블 ADD COLUMN 은 테이블-레벨 GRANT 자동 상속 → 신규 GRANT 불요 (0026 규약).
"""

DOWNGRADE_SQL = r"""
ALTER TABLE public.node_analysis_jobs
    DROP COLUMN IF EXISTS pass_no,
    DROP COLUMN IF EXISTS anchor_key;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
