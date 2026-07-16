"""redteam_reviews — 축 인지 재도출(도구 재추론) 관측 컬럼 추가 (feature-0002).

0042 가 만든 agent_runtime.redteam_reviews 에 축 인지 라우팅(sql / max 강도 completeness
BLOCK 을 도구 재추론으로 승격)의 관측치 3개를 추가한다:
- rederive_applied     : 도구 재추론이 실제 발동했는지
- rederive_tool_rounds : 재추론에서 돈 도구 라운드 수(비용/지연 관측)
- rederive_axis        : 재도출로 승격된 BLOCK 축(예: "sql" / "sql,completeness")

live 안전: 순수 additive ALTER TABLE ADD COLUMN. PG11+ 에서 DEFAULT 동반 ADD COLUMN 은
메타데이터-only(테이블 재작성·풀 락 없음) → migrate-lint expand-safe. downgrade=DROP
(파생 관측치 소실 허용 — 0042 규약과 동형).

GRANT 불필요(중요): 0042 는 **신규 테이블**이라 DEPLOY TRAP 규약상 명시 GRANT 가 필요했지만,
ADD COLUMN 은 테이블의 기존 grant(agent_kb_rw INSERT / agent_kb_ro SELECT)를 그대로 상속한다.
신규 컬럼에 별도 GRANT 를 다시 걸 필요 없음(0008 트랩 과잉적용 금지).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0043_redteam_rederive_columns"
down_revision: Union[str, None] = "0042_redteam_reviews"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE agent_runtime.redteam_reviews
    ADD COLUMN IF NOT EXISTS rederive_applied     BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS rederive_tool_rounds INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS rederive_axis        VARCHAR(64);
"""

DOWNGRADE_SQL = r"""
ALTER TABLE agent_runtime.redteam_reviews
    DROP COLUMN IF EXISTS rederive_applied,
    DROP COLUMN IF EXISTS rederive_tool_rounds,
    DROP COLUMN IF EXISTS rederive_axis;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
