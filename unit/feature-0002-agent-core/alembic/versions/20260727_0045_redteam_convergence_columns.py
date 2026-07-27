"""redteam_reviews — 반복 수정 수렴 관측 컬럼 추가 (feature-0021).

0042/0043 이 만든 agent_runtime.redteam_reviews 에, 결함이 해소될 때까지 반복하는
수정 루프(REDTEAM_REVISE_UNTIL_RESOLVED)의 관측치 4개를 추가한다:
- verify_findings        : **마지막 재검증이 여전히 문제 삼은 항목**(JSONB)
- unresolved_block_count : 답변 전달 시점에 해소되지 않은 BLOCK 수
- revision_rounds        : 실제로 돈 수정 라운드 수
- stop_reason            : 루프 종료 사유(resolved / aborted / no_progress / revise_failed /
                           verify_error / unverified / budget / backstop / review_error)

배경: 이전에는 `verify_verdict` 문자열 하나만 남아, 재검증이 'revise'(결함 잔존) 를 내도
**무엇이 남았는지 알 수 없었고** 관리 콘솔은 그 답변을 '개선된 답변 전달'로만 표시했다
(결함 잔존의 사실상 은폐). 라이브 실측에서 매우높음 강도 7건 중 4건이 이 상태로 전달됐다.

live 안전: 순수 additive ALTER TABLE ADD COLUMN. PG11+ 에서 DEFAULT 동반 ADD COLUMN 은
메타데이터-only(테이블 재작성·풀 락 없음) → migrate-lint expand-safe. downgrade=DROP
(파생 관측치 소실 허용 — 0042/0043 규약과 동형).

GRANT 불필요: ADD COLUMN 은 테이블의 기존 grant(agent_kb_rw INSERT / agent_kb_ro SELECT)를
그대로 상속한다 (0043 과 동일 판단 — 0008 트랩 과잉적용 금지).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0045_redteam_convergence_columns"
down_revision: Union[str, None] = "0044_conversation_folders"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE agent_runtime.redteam_reviews
    ADD COLUMN IF NOT EXISTS verify_findings        JSONB,
    ADD COLUMN IF NOT EXISTS unresolved_block_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS revision_rounds        INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS stop_reason            VARCHAR(32);
"""

DOWNGRADE_SQL = r"""
ALTER TABLE agent_runtime.redteam_reviews
    DROP COLUMN IF EXISTS verify_findings,
    DROP COLUMN IF EXISTS unresolved_block_count,
    DROP COLUMN IF EXISTS revision_rounds,
    DROP COLUMN IF EXISTS stop_reason;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
