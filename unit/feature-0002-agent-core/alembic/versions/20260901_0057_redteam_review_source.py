"""redteam_reviews.source / task_id — 자가 검증의 **주체**를 기록 (feature-0043).

## 왜 컬럼이 필요한가

`redteam_reviews` 는 서버가 자기 답변을 검증하던 시절의 원장이다. 전환 뒤 검증하는 주체가
바뀌었다 — 답변을 만든 **개인 AI 러너**가 자기 답변을 5축으로 검증해 `submit_answer` 에
함께 싣는다. 두 주체의 판정이 한 테이블에 섞이는데, 구분이 없으면 관리 콘솔은 「전환 이전
서버 검증」과 「현행 외부 AI 자가 검증」을 같은 수로 합산해 보여 준다. 그 합계는 어느
질문에도 답하지 않는다(서버 검증은 더 이상 늘지 않고, 외부 검증은 러너마다 유무가 다르다).

`task_id` 는 그 판정을 **어느 브리지 작업이 낳았는가** 다. `run_id`(서버 요청 식별자)는
외부 경로에 존재하지 않으므로 그 칸을 재사용하면 두 세계의 식별자가 한 컬럼에서 섞인다 —
콘솔이 작업 원장과 조인할 수 없게 되고, 조인할 수 없으면 「이 답변의 검증 결과」를 그
답변 옆에 놓을 방법이 사라진다.

## 기본값이 'server' 인 이유

기존 행은 전부 서버가 쓴 것이다. NULL 을 허용하고 화면이 "미상" 으로 읽게 두면, 과거
기록 전체가 출처 불명이 되어 「전환 이전 기록」이라는 사실 자체를 잃는다.

live 안전: 컬럼 추가 + 인덱스 + GRANT 재확인만 (순수 additive — expand-safe, contract 없음).
downgrade = 컬럼 DROP (파생 관측 데이터라 소실 허용).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0057_redteam_review_source"
down_revision: Union[str, None] = "0056_llm_usage_cache_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE agent_runtime.redteam_reviews
    ADD COLUMN IF NOT EXISTS source  VARCHAR(16) NOT NULL DEFAULT 'server',
    ADD COLUMN IF NOT EXISTS task_id VARCHAR(64);

-- 콘솔이 '현행 외부 검증'만 최신순으로 뽑는 경로. source 를 선두에 둔다(그 축으로 먼저 좁힌다).
CREATE INDEX IF NOT EXISTS ix_redteam_reviews_source
    ON agent_runtime.redteam_reviews (source, id DESC);
-- 작업 원장(WebAiTasks)과의 조인 키. 외부 경로에서만 채워지므로 부분 인덱스로 좁힌다.
CREATE INDEX IF NOT EXISTS ix_redteam_reviews_task
    ON agent_runtime.redteam_reviews (task_id) WHERE task_id IS NOT NULL;

-- ── GRANT 재확인 (0008 DEPLOY TRAP 규약 — 컬럼 추가는 기존 GRANT 를 잇지만,
--    테이블이 다른 경로로 재생성된 배포에서 권한이 비어 있을 수 있어 멱등 재적용) ──
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_kb_rw') THEN
        GRANT SELECT, INSERT ON agent_runtime.redteam_reviews TO agent_kb_rw;
        GRANT USAGE, SELECT ON SEQUENCE agent_runtime.redteam_reviews_id_seq TO agent_kb_rw;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_kb_ro') THEN
        GRANT SELECT ON agent_runtime.redteam_reviews TO agent_kb_ro;
    END IF;
END $$;
"""

DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS agent_runtime.ix_redteam_reviews_task;
DROP INDEX IF EXISTS agent_runtime.ix_redteam_reviews_source;
ALTER TABLE agent_runtime.redteam_reviews
    DROP COLUMN IF EXISTS task_id,
    DROP COLUMN IF EXISTS source;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
