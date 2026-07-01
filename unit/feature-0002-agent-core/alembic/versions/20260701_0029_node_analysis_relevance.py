"""node_analysis 앵커-상대 관련도 컬럼 (feature-0016 node-analysis-anchor).

요청(2026-07-01): 그래프뷰 "AI 능동 분석" 재귀가 **원래 분석 대상(루트)** 에 앵커되지 않고, 방문한
허브 노드(예: 일반 컬럼 UniqueID, 부모 Schema)를 새 중심으로 무관 노드까지 fan-out 하는 문제 해소.

해법의 저장소 지원: node_analysis_jobs 에 `relevance`(루트와의 관련도 0~1)를 영속화한다. 워커가
이웃을 재큐할 때 계산한 점수를 저장하고, claim 정렬을 `depth ASC, relevance DESC` 로 바꿔 예산을
**가장 관련 높은 노드에 우선 소비**한다(사용자 "낮은 우선순위로 판단" 요구의 영속 구현).

비파괴 추가(ADD COLUMN + INDEX만) — CONVENTIONS §12 expand-only. 기존 행은 DEFAULT 0.
downgrade=DROP. GRANT 는 테이블 단위라 신규 컬럼에 별도 부여 불필요(0028 이 이미 부여).

**DEPLOY 안전**: relevance 는 NOT NULL DEFAULT 0 이라 구버전 코드가 INSERT 시 컬럼 미지정해도 안전.
신버전 코드가 값을 기입한다(하위호환 — expand 단계, 코드 컷오버 후 관측).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0029_node_analysis_relevance"
down_revision: Union[str, None] = "0028_node_analysis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
-- 루트(원래 분석 대상)와의 관련도(0~1). 이웃 재큐 시 워커가 기입(구버전은 0 유지).
ALTER TABLE node_analysis_jobs
    ADD COLUMN IF NOT EXISTS relevance real NOT NULL DEFAULT 0;

-- claim 정렬 가속: pending 잡을 depth 얕은 순 + 관련도 높은 순으로 뽑는다.
--   기존 ix_..._status_created(FIFO)는 그대로 두고(다른 조회 경로), 관련도 우선 정렬 인덱스를 추가.
CREATE INDEX IF NOT EXISTS ix_node_analysis_jobs_claim_priority
    ON node_analysis_jobs (status, depth, relevance DESC, created_at);
"""

DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS ix_node_analysis_jobs_claim_priority;
ALTER TABLE node_analysis_jobs DROP COLUMN IF EXISTS relevance;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
