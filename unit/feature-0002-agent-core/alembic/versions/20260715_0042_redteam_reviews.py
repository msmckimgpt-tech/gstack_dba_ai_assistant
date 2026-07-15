"""redteam_reviews — 답변 자가 적대(red-team) 리뷰 판정 저장 (feature-0021).

assistant 최종 답변 초안에 대한 fresh-context 적대 리뷰(find→verify)의 판정·findings 를
기록한다. 쓰기 = agent 경로(modules/redteam.record_review, best-effort), 읽기 = 관리 콘솔
"AI 추론" 탭 (routers/admin_reasoning.py, RO 커서 페이징 — ai-ops 패턴).

**신규 테이블 GRANT 필수** (0008 DEPLOY TRAP 규약): superuser 로 적용되므로 명시 GRANT 가
없으면 agent(agent_kb_rw) INSERT / web RO(agent_kb_ro) SELECT 가 permission denied 로
조용히 실패한다.

live 안전: 신규 테이블 CREATE + 인덱스 + GRANT 만 (기존 데이터 무손실, 순수 additive —
migrate-lint expand-safe). downgrade = DROP (판정 이력 소실 허용 — 파생 관측 데이터).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0042_redteam_reviews"
down_revision: Union[str, None] = "0041_message_branching"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
CREATE TABLE IF NOT EXISTS agent_runtime.redteam_reviews (
    id                BIGSERIAL PRIMARY KEY,
    conversation_id   TEXT,
    run_id            TEXT,
    verdict           VARCHAR(16) NOT NULL,          -- pass | revise | error
    findings          JSONB,                          -- [{axis,severity,claim,evidence,fix_hint}]
    block_count       INTEGER NOT NULL DEFAULT 0,
    warn_count        INTEGER NOT NULL DEFAULT 0,
    verify_verdict    VARCHAR(16),                    -- 재검증(높음+) 결과. NULL=미수행
    revision_applied  BOOLEAN NOT NULL DEFAULT FALSE,
    model             VARCHAR(128),
    latency_ms        INTEGER,                        -- 리뷰 파이프라인 전체(리뷰+수정+재검증)
    reasoning_level   VARCHAR(16),
    is_group          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 최근 활동 keyset 페이징(id DESC)은 PK 로 충분. 대화별 조회 보조 인덱스만 추가.
CREATE INDEX IF NOT EXISTS ix_redteam_reviews_conversation
    ON agent_runtime.redteam_reviews (conversation_id, id DESC);

-- 명시 GRANT (0008 DEPLOY TRAP 규약 — superuser 적용이라 자동 상속 없음).
GRANT SELECT, INSERT ON agent_runtime.redteam_reviews TO agent_kb_rw;
GRANT USAGE, SELECT ON SEQUENCE agent_runtime.redteam_reviews_id_seq TO agent_kb_rw;
GRANT SELECT ON agent_runtime.redteam_reviews TO agent_kb_ro;
"""

DOWNGRADE_SQL = r"""
DROP TABLE IF EXISTS agent_runtime.redteam_reviews;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
