"""core_conversations.archived_at / archived_by_account_id — 대화 삭제를 soft-archive 로 전환 (TASK-0273).

대화 "삭제" 동작을 hard-delete 대신 **보관(archive)** 으로 바꾼다. 보관된 대화는 (1) 소유 계정의
대화 목록에서 숨겨지고, (2) 새 메시지 진행이 차단되며(blocked 와 동형 동결), (3) 데이터·첨부는
보존되어 오용 방지 admin 조회(`conversation.archive.read.any`)·맥락 참조(fork)가 가능하다.
archived_at 이 NULL 이 아니면 보관으로 간주하고, archived_by_account_id 는 보관을 수행한 계정 id.

데이터 무손실: 컬럼 ADD 만(기존 대화 archived_at = NULL = 미보관). web 컨테이너는 DML-only role
이라 런타임 ALTER 불가 → 본 마이그레이션(superuser offline SQL)이 정본 적용 경로. 부트스트랩
DDL(agent_runtime_schema.sql)·app.py MySQL 폴백에도 동일 컬럼 멱등 ALTER 를 반영(TASK-0248 동형).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_core_conv_archived"
down_revision: Union[str, None] = "0006_datasource_health"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = r"""
ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS archived_at timestamptz;

ALTER TABLE agent_runtime.core_conversations
    ADD COLUMN IF NOT EXISTS archived_by_account_id bigint;

CREATE INDEX IF NOT EXISTS ix_core_conv_archived
    ON agent_runtime.core_conversations (archived_at);
"""

DOWNGRADE_SQL = r"""
DROP INDEX IF EXISTS agent_runtime.ix_core_conv_archived;
ALTER TABLE agent_runtime.core_conversations DROP COLUMN IF EXISTS archived_by_account_id;
ALTER TABLE agent_runtime.core_conversations DROP COLUMN IF EXISTS archived_at;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
