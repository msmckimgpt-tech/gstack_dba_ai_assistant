"""core_conversations.blocked_at / blocked_reason — 참조 제품 삭제 시 대화 차단 (TASK-0248).

`관리 콘솔 > 제품` 에서 제품을 삭제할 때, 그 제품을 pinned 한 대화를 삭제 거부(409/400) 대신
**차단(blocked)** 상태로 전환한다. 차단된 대화는 이력 열람은 가능하되 더 이상 진행(새 메시지
전송)할 수 없다. blocked_at 이 NULL 이 아니면 차단으로 간주하며, blocked_reason 은 사용자
안내 문구(예: "참조 제품이 삭제되어 더 이상 대화를 진행할 수 없습니다.")를 담는다.

데이터 무손실: 컬럼 ADD 만(기존 대화는 blocked_at = NULL = 미차단). web 컨테이너는 DML-only
role 이라 런타임 ALTER 가 불가하므로, 본 마이그레이션(superuser offline SQL)이 정본 적용 경로다.
부트스트랩 DDL(agent_runtime_schema.sql)에도 동일 컬럼 + 멱등 ALTER 를 반영했다.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_core_conv_blocked"
down_revision: Union[str, None] = "0004_rag_objects_datasource"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS blocked_at timestamptz;

ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS blocked_reason character varying(256);
"""

DOWNGRADE_SQL = r"""
ALTER TABLE agent_runtime.core_conversations DROP COLUMN IF EXISTS blocked_reason;
ALTER TABLE agent_runtime.core_conversations DROP COLUMN IF EXISTS blocked_at;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
